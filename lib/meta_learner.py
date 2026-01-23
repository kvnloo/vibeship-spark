"""
Spark Meta-Learner: Learning about learning itself.

Inspired by MAML (Model-Agnostic Meta-Learning) and meta-learning research:
- Learn which learning strategies work best
- Identify when patterns stabilize vs remain noisy
- Prune outdated or low-confidence learnings
- Adjust confidence based on sample size and consistency
- Track learning velocity (how fast are we improving?)

This is the "learning to learn" layer - it optimizes the learning process itself.
"""

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime, timedelta
import statistics

from .mind_client import MindClient, Memory, ContentType, TemporalLevel


@dataclass
class LearningEvent:
    """A single learning event to track meta-patterns."""
    event_id: str
    timestamp: float
    learning_type: str  # tool, skill, agent, pattern, error
    source: str  # Which system generated this learning
    confidence: float
    was_useful: Optional[bool] = None  # Did this learning help later?
    usage_count: int = 0


@dataclass
class LearningTrend:
    """Trend analysis for a type of learning."""
    learning_type: str
    sample_count: int
    avg_confidence: float
    confidence_trend: float  # Positive = improving, negative = declining
    stability: float  # 0-1, how consistent is this learning
    velocity: float  # Learning rate - new patterns per session
    is_saturated: bool  # Has learning plateaued?


@dataclass
class PruneCandidate:
    """A learning that might be ready for pruning."""
    learning_id: str
    learning_type: str
    reason: str
    confidence: float
    age_days: float
    last_used: Optional[float] = None


@dataclass
class MetaInsight:
    """An insight about the learning process itself."""
    insight_type: str  # velocity, stability, saturation, effectiveness
    description: str
    confidence: float
    actionable: bool
    suggested_action: Optional[str] = None


class MetaLearner:
    """
    Learns about learning itself - the meta-optimization layer.

    Tracks:
    - Which types of learning are most effective
    - When learning patterns stabilize (saturation)
    - When to prune outdated learnings
    - Learning velocity (improvement rate)
    - Confidence calibration
    """

    # Thresholds for meta-analysis
    STABILITY_WINDOW = 10  # Number of samples for stability calculation
    SATURATION_THRESHOLD = 0.95  # Confidence level indicating saturation
    PRUNE_AGE_DAYS = 30  # Consider pruning learnings older than this
    PRUNE_CONFIDENCE_THRESHOLD = 0.3  # Prune low-confidence learnings
    MIN_SAMPLES_FOR_TREND = 5  # Minimum samples for trend analysis

    def __init__(self, mind_client: Optional[MindClient] = None):
        self.mind = mind_client or MindClient()

        # Learning event history
        self.learning_events: List[LearningEvent] = []
        self.events_by_type: Dict[str, List[LearningEvent]] = defaultdict(list)

        # Confidence history for trend tracking
        self.confidence_history: Dict[str, List[Tuple[float, float]]] = defaultdict(list)

        # Learning effectiveness tracking
        self.learning_usefulness: Dict[str, List[bool]] = defaultdict(list)

        # Meta-statistics
        self.total_learnings: int = 0
        self.pruned_count: int = 0
        self.meta_insights: List[MetaInsight] = []

        # Session tracking
        self.session_learning_counts: List[int] = []
        self.current_session_learnings: int = 0

    async def load_existing_data(self):
        """Load existing meta-learnings from Mind."""
        learnings = await self.mind.retrieve(
            query="META_LEARNING",
            limit=50,
            temporal_level=TemporalLevel.IDENTITY,
            content_type=ContentType.REFLECTION
        )

        for learning in learnings:
            metadata = learning.get("metadata", {})
            if metadata.get("pattern_type") == "meta_learning":
                # Restore meta-statistics
                self.total_learnings = max(
                    self.total_learnings,
                    metadata.get("total_learnings", 0)
                )

    def record_learning(
        self,
        learning_type: str,
        source: str,
        confidence: float,
        learning_id: Optional[str] = None
    ) -> LearningEvent:
        """
        Record a new learning event for meta-analysis.

        Called by other Spark components when they extract a learning.
        """
        event = LearningEvent(
            event_id=learning_id or f"{learning_type}:{datetime.now().timestamp()}",
            timestamp=datetime.now().timestamp(),
            learning_type=learning_type,
            source=source,
            confidence=confidence
        )

        self.learning_events.append(event)
        self.events_by_type[learning_type].append(event)
        self.confidence_history[learning_type].append((event.timestamp, confidence))

        self.total_learnings += 1
        self.current_session_learnings += 1

        return event

    def mark_learning_useful(self, learning_id: str, was_useful: bool):
        """Mark whether a learning was useful when applied."""
        for event in reversed(self.learning_events):
            if event.event_id == learning_id:
                event.was_useful = was_useful
                event.usage_count += 1
                self.learning_usefulness[event.learning_type].append(was_useful)
                break

    def end_session(self):
        """Mark end of a session for velocity tracking."""
        self.session_learning_counts.append(self.current_session_learnings)
        self.current_session_learnings = 0

    def analyze_learning_trends(self) -> Dict[str, LearningTrend]:
        """Analyze trends for each type of learning."""
        trends = {}

        for learning_type, events in self.events_by_type.items():
            if len(events) < self.MIN_SAMPLES_FOR_TREND:
                continue

            # Calculate average confidence
            confidences = [e.confidence for e in events]
            avg_confidence = statistics.mean(confidences)

            # Calculate confidence trend (regression slope)
            confidence_trend = self._calculate_trend(confidences)

            # Calculate stability (inverse of variance)
            if len(confidences) >= 2:
                variance = statistics.variance(confidences)
                stability = 1.0 / (1.0 + variance * 10)  # Normalize to 0-1
            else:
                stability = 0.5

            # Calculate velocity (learnings per session)
            recent_events = [
                e for e in events
                if e.timestamp > datetime.now().timestamp() - 7 * 24 * 3600
            ]
            velocity = len(recent_events) / max(len(self.session_learning_counts), 1)

            # Check for saturation
            is_saturated = (
                avg_confidence > self.SATURATION_THRESHOLD and
                stability > 0.8 and
                abs(confidence_trend) < 0.01
            )

            trends[learning_type] = LearningTrend(
                learning_type=learning_type,
                sample_count=len(events),
                avg_confidence=avg_confidence,
                confidence_trend=confidence_trend,
                stability=stability,
                velocity=velocity,
                is_saturated=is_saturated
            )

        return trends

    def _calculate_trend(self, values: List[float]) -> float:
        """Calculate linear trend (slope) of values."""
        if len(values) < 2:
            return 0.0

        n = len(values)
        x_mean = (n - 1) / 2
        y_mean = statistics.mean(values)

        numerator = sum((i - x_mean) * (v - y_mean) for i, v in enumerate(values))
        denominator = sum((i - x_mean) ** 2 for i in range(n))

        if denominator == 0:
            return 0.0

        return numerator / denominator

    def identify_prune_candidates(self) -> List[PruneCandidate]:
        """Identify learnings that should be pruned."""
        candidates = []
        now = datetime.now().timestamp()

        for event in self.learning_events:
            age_days = (now - event.timestamp) / (24 * 3600)

            # Candidate for pruning if:
            # 1. Old and low confidence
            if age_days > self.PRUNE_AGE_DAYS and event.confidence < self.PRUNE_CONFIDENCE_THRESHOLD:
                candidates.append(PruneCandidate(
                    learning_id=event.event_id,
                    learning_type=event.learning_type,
                    reason="Old and low confidence",
                    confidence=event.confidence,
                    age_days=age_days
                ))
                continue

            # 2. Never used and old
            if event.usage_count == 0 and age_days > self.PRUNE_AGE_DAYS / 2:
                candidates.append(PruneCandidate(
                    learning_id=event.event_id,
                    learning_type=event.learning_type,
                    reason="Never used",
                    confidence=event.confidence,
                    age_days=age_days
                ))
                continue

            # 3. Used but marked not useful multiple times
            if event.was_useful is False and event.usage_count >= 3:
                candidates.append(PruneCandidate(
                    learning_id=event.event_id,
                    learning_type=event.learning_type,
                    reason="Repeatedly not useful",
                    confidence=event.confidence,
                    age_days=age_days
                ))

        return candidates

    def generate_meta_insights(self) -> List[MetaInsight]:
        """Generate insights about the learning process itself."""
        insights = []
        trends = self.analyze_learning_trends()

        # Insight: Learning velocity
        if self.session_learning_counts:
            recent_velocity = statistics.mean(self.session_learning_counts[-5:]) if len(self.session_learning_counts) >= 5 else statistics.mean(self.session_learning_counts)
            overall_velocity = statistics.mean(self.session_learning_counts)

            if recent_velocity > overall_velocity * 1.5:
                insights.append(MetaInsight(
                    insight_type="velocity",
                    description=f"Learning velocity increased: {recent_velocity:.1f} vs {overall_velocity:.1f} learnings/session",
                    confidence=0.8,
                    actionable=False
                ))
            elif recent_velocity < overall_velocity * 0.5:
                insights.append(MetaInsight(
                    insight_type="velocity",
                    description=f"Learning velocity decreased: {recent_velocity:.1f} vs {overall_velocity:.1f} learnings/session",
                    confidence=0.8,
                    actionable=True,
                    suggested_action="Consider exploring new task types to discover new patterns"
                ))

        # Insight: Saturation detection
        for learning_type, trend in trends.items():
            if trend.is_saturated:
                insights.append(MetaInsight(
                    insight_type="saturation",
                    description=f"{learning_type} learning has saturated at {trend.avg_confidence:.0%} confidence",
                    confidence=trend.stability,
                    actionable=True,
                    suggested_action=f"Focus learning resources on other areas; {learning_type} is well understood"
                ))

        # Insight: Unstable learning
        for learning_type, trend in trends.items():
            if trend.stability < 0.3 and trend.sample_count >= 10:
                insights.append(MetaInsight(
                    insight_type="stability",
                    description=f"{learning_type} learning is unstable (stability: {trend.stability:.0%})",
                    confidence=0.7,
                    actionable=True,
                    suggested_action=f"Review {learning_type} learning criteria; patterns may be too broad"
                ))

        # Insight: Effectiveness by type
        for learning_type, usefulness in self.learning_usefulness.items():
            if len(usefulness) >= 5:
                useful_rate = sum(usefulness) / len(usefulness)
                if useful_rate < 0.3:
                    insights.append(MetaInsight(
                        insight_type="effectiveness",
                        description=f"{learning_type} learnings rarely useful ({useful_rate:.0%})",
                        confidence=0.8,
                        actionable=True,
                        suggested_action=f"Refine {learning_type} extraction criteria"
                    ))
                elif useful_rate > 0.8:
                    insights.append(MetaInsight(
                        insight_type="effectiveness",
                        description=f"{learning_type} learnings highly effective ({useful_rate:.0%})",
                        confidence=0.9,
                        actionable=False
                    ))

        # Insight: Prune candidates
        prune_candidates = self.identify_prune_candidates()
        if len(prune_candidates) > 10:
            insights.append(MetaInsight(
                insight_type="maintenance",
                description=f"{len(prune_candidates)} learnings ready for pruning",
                confidence=0.9,
                actionable=True,
                suggested_action="Run pruning to remove outdated or ineffective learnings"
            ))

        self.meta_insights = insights
        return insights

    def get_learning_effectiveness(self, learning_type: str) -> float:
        """Get effectiveness rate for a learning type."""
        usefulness = self.learning_usefulness.get(learning_type, [])
        if not usefulness:
            return 0.5  # Default to neutral
        return sum(usefulness) / len(usefulness)

    def get_recommended_confidence_threshold(self, learning_type: str) -> float:
        """
        Get recommended confidence threshold for a learning type.

        Based on historical effectiveness - if learnings of this type
        are often not useful, raise the threshold.
        """
        effectiveness = self.get_learning_effectiveness(learning_type)

        # If effectiveness is low, require higher confidence
        if effectiveness < 0.3:
            return 0.8
        elif effectiveness < 0.5:
            return 0.7
        elif effectiveness < 0.7:
            return 0.6
        else:
            return 0.5

    def should_learn(self, learning_type: str, proposed_confidence: float) -> bool:
        """
        Decide whether to accept a proposed learning.

        Uses meta-knowledge to filter low-quality learnings.
        """
        threshold = self.get_recommended_confidence_threshold(learning_type)

        # Check if this type is saturated
        trends = self.analyze_learning_trends()
        if learning_type in trends and trends[learning_type].is_saturated:
            # Require higher confidence for saturated types
            threshold = max(threshold, 0.9)

        return proposed_confidence >= threshold

    def calibrate_confidence(
        self,
        learning_type: str,
        raw_confidence: float
    ) -> float:
        """
        Calibrate confidence based on historical accuracy.

        If a learning type is often wrong, discount its confidence.
        """
        effectiveness = self.get_learning_effectiveness(learning_type)

        # Calibrate: multiply by effectiveness
        # If 80% of past learnings were useful, keep 80% of confidence
        calibrated = raw_confidence * (0.5 + effectiveness * 0.5)

        return min(1.0, max(0.0, calibrated))

    async def store_meta_learnings(self) -> int:
        """Store meta-learning insights in Mind."""
        memories = []

        # Store overall meta-statistics
        trends = self.analyze_learning_trends()

        meta_summary = (
            f"META_LEARNING Summary: "
            f"{self.total_learnings} total learnings across {len(trends)} types. "
            f"Pruned: {self.pruned_count}. "
            f"Types: {', '.join(f'{t}({d.avg_confidence:.0%})' for t, d in trends.items())}"
        )

        memories.append(Memory(
            content=meta_summary,
            temporal_level=TemporalLevel.IDENTITY,
            salience=0.9,
            content_type=ContentType.REFLECTION,
            metadata={
                "pattern_type": "meta_learning",
                "total_learnings": self.total_learnings,
                "pruned_count": self.pruned_count,
                "learning_types": list(trends.keys())
            }
        ))

        # Store actionable insights
        for insight in self.meta_insights:
            if insight.actionable:
                memories.append(Memory(
                    content=f"META_INSIGHT [{insight.insight_type}]: {insight.description}. Action: {insight.suggested_action}",
                    temporal_level=TemporalLevel.SEASONAL,
                    salience=insight.confidence,
                    content_type=ContentType.REFLECTION,
                    metadata={
                        "pattern_type": "meta_insight",
                        "insight_type": insight.insight_type
                    }
                ))

        if memories:
            return await self.mind.store_batch(memories)
        return 0

    def prune_learnings(self, candidates: Optional[List[PruneCandidate]] = None) -> int:
        """Execute pruning of identified candidates."""
        if candidates is None:
            candidates = self.identify_prune_candidates()

        pruned_ids = {c.learning_id for c in candidates}

        # Remove from learning events
        self.learning_events = [
            e for e in self.learning_events
            if e.event_id not in pruned_ids
        ]

        # Rebuild type index
        self.events_by_type.clear()
        for event in self.learning_events:
            self.events_by_type[event.learning_type].append(event)

        self.pruned_count += len(candidates)

        return len(candidates)

    def get_meta_stats(self) -> Dict[str, Any]:
        """Get meta-learning statistics."""
        trends = self.analyze_learning_trends()

        return {
            "total_learnings": self.total_learnings,
            "active_learnings": len(self.learning_events),
            "pruned_count": self.pruned_count,
            "learning_types": len(self.events_by_type),
            "trends": {
                t: {
                    "samples": d.sample_count,
                    "confidence": d.avg_confidence,
                    "stability": d.stability,
                    "saturated": d.is_saturated
                }
                for t, d in trends.items()
            },
            "effectiveness": {
                t: self.get_learning_effectiveness(t)
                for t in self.events_by_type.keys()
            },
            "prune_candidates": len(self.identify_prune_candidates()),
            "insights_count": len(self.meta_insights)
        }
