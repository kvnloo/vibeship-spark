"""
Spark Reasoning Tracker: Learn from the gap between prediction and reality.

This is where REAL self-improvement happens. Instead of just observing
"tool X worked", we capture:
1. What was I trying to achieve? (intent)
2. What did I predict would happen? (expectation)
3. What actually happened? (outcome)
4. Why was there a gap? (learning)

The delta between prediction and reality is where intelligence grows.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime
from enum import Enum
import hashlib

from .mind_client import MindClient, Memory, ContentType, TemporalLevel


class PredictionAccuracy(Enum):
    """How accurate was the prediction?"""
    CORRECT = "correct"           # Predicted outcome matched
    PARTIAL = "partial"           # Some aspects matched
    WRONG = "wrong"               # Prediction was incorrect
    SURPRISING = "surprising"     # Outcome was unexpected in a useful way


@dataclass
class Prediction:
    """A prediction about what will happen."""
    prediction_id: str
    session_id: str
    timestamp: float

    # What I'm doing
    tool_name: str
    intent: str                   # What am I trying to achieve?

    # What I expect
    expected_outcome: str         # What I think will happen
    expected_success: bool        # Do I think it will succeed?
    confidence: float             # 0.0 to 1.0 - how sure am I?

    # Why I think this
    reasoning: str                # Why do I expect this outcome?
    risk_factors: List[str] = field(default_factory=list)  # What could go wrong?

    # After the fact
    actual_outcome: Optional[str] = None
    actual_success: Optional[bool] = None
    accuracy: Optional[PredictionAccuracy] = None
    learning: Optional[str] = None  # What did we learn from the gap?


@dataclass
class ReasoningPattern:
    """A pattern learned from prediction accuracy."""
    pattern_type: str             # overconfidence, underconfidence, blind_spot, insight
    description: str
    conditions: List[str]         # When does this pattern apply?
    frequency: int                # How often has this occurred?
    confidence_delta: float       # Average gap between predicted and actual confidence
    examples: List[str] = field(default_factory=list)


class ReasoningTracker:
    """
    Track predictions and learn from the gap between expectation and reality.

    This is the introspection layer - learning from HOW I think, not just
    WHAT I do.
    """

    def __init__(self, mind_client: Optional[MindClient] = None):
        self.mind = mind_client or MindClient(timeout=2.0)
        self.active_predictions: Dict[str, Prediction] = {}
        self.completed_predictions: List[Prediction] = []
        self.patterns: List[ReasoningPattern] = []

        # Calibration tracking
        self.confidence_calibration: Dict[str, List[Tuple[float, bool]]] = {}
        # tool -> [(predicted_confidence, actual_success), ...]

        # Calibration factors (learned adjustments)
        # tool -> calibration_factor (multiply raw confidence by this)
        self.calibration_factors: Dict[str, float] = {}

    def record_prediction(
        self,
        session_id: str,
        tool_name: str,
        tool_input: Dict[str, Any],
        intent: str,
        expected_outcome: str,
        expected_success: bool = True,
        confidence: float = 0.7,
        reasoning: str = "",
        risk_factors: Optional[List[str]] = None
    ) -> str:
        """
        Record a prediction before taking an action.

        Call this BEFORE executing a tool to capture intent and expectation.
        Returns prediction_id for later resolution.
        """
        prediction_id = self._generate_id(session_id, tool_name, intent)

        prediction = Prediction(
            prediction_id=prediction_id,
            session_id=session_id,
            timestamp=datetime.now().timestamp(),
            tool_name=tool_name,
            intent=intent,
            expected_outcome=expected_outcome,
            expected_success=expected_success,
            confidence=confidence,
            reasoning=reasoning,
            risk_factors=risk_factors or []
        )

        self.active_predictions[prediction_id] = prediction
        return prediction_id

    def resolve_prediction(
        self,
        prediction_id: str,
        actual_outcome: str,
        actual_success: bool,
        error: Optional[str] = None
    ) -> Optional[str]:
        """
        Resolve a prediction with what actually happened.

        Returns a learning insight if the gap is significant.
        """
        if prediction_id not in self.active_predictions:
            return None

        prediction = self.active_predictions.pop(prediction_id)
        prediction.actual_outcome = actual_outcome
        prediction.actual_success = actual_success

        # Determine accuracy
        prediction.accuracy = self._assess_accuracy(prediction, error)

        # Track calibration
        self._track_calibration(prediction)

        # Generate learning from the gap
        learning = self._extract_learning(prediction, error)
        prediction.learning = learning

        self.completed_predictions.append(prediction)

        return learning

    def _generate_id(self, session_id: str, tool_name: str, intent: str) -> str:
        """Generate unique prediction ID."""
        data = f"{session_id}:{tool_name}:{intent}:{datetime.now().timestamp()}"
        return f"pred_{hashlib.md5(data.encode()).hexdigest()[:12]}"

    def _assess_accuracy(self, prediction: Prediction, error: Optional[str]) -> PredictionAccuracy:
        """Assess how accurate the prediction was."""
        # Success prediction accuracy
        if prediction.expected_success == prediction.actual_success:
            if prediction.confidence >= 0.7:
                return PredictionAccuracy.CORRECT
            else:
                # Low confidence but correct = surprising success
                return PredictionAccuracy.SURPRISING
        else:
            # Prediction was wrong
            if prediction.expected_success and not prediction.actual_success:
                # Expected success, got failure
                if prediction.confidence >= 0.8:
                    return PredictionAccuracy.WRONG  # Overconfident
                else:
                    return PredictionAccuracy.PARTIAL  # Had doubts
            else:
                # Expected failure, got success = pleasant surprise
                return PredictionAccuracy.SURPRISING

    def _track_calibration(self, prediction: Prediction):
        """Track confidence calibration per tool."""
        tool = prediction.tool_name
        if tool not in self.confidence_calibration:
            self.confidence_calibration[tool] = []

        self.confidence_calibration[tool].append(
            (prediction.confidence, prediction.actual_success)
        )

        # Keep last 50 predictions per tool
        if len(self.confidence_calibration[tool]) > 50:
            self.confidence_calibration[tool] = self.confidence_calibration[tool][-50:]

    def _extract_learning(self, prediction: Prediction, error: Optional[str]) -> Optional[str]:
        """Extract a learning from the prediction-outcome gap."""
        if prediction.accuracy == PredictionAccuracy.CORRECT:
            # Prediction was right - reinforce reasoning
            if prediction.confidence >= 0.8:
                return None  # Expected, nothing to learn
            else:
                return f"INSIGHT: {prediction.reasoning} - confirmed with {prediction.tool_name}"

        elif prediction.accuracy == PredictionAccuracy.WRONG:
            # Prediction was wrong - this is where we learn
            learning_parts = [f"MISCALCULATION with {prediction.tool_name}"]
            learning_parts.append(f"Expected: {prediction.expected_outcome[:50]}")
            learning_parts.append(f"Got: {prediction.actual_outcome[:50] if prediction.actual_outcome else 'failure'}")

            if prediction.risk_factors:
                # Check if any risk factor materialized
                if error:
                    error_lower = error.lower()
                    for risk in prediction.risk_factors:
                        if any(word in error_lower for word in risk.lower().split()):
                            learning_parts.append(f"Risk materialized: {risk}")
                            break

            if prediction.reasoning:
                learning_parts.append(f"Flawed reasoning: {prediction.reasoning[:50]}")

            return " | ".join(learning_parts)

        elif prediction.accuracy == PredictionAccuracy.SURPRISING:
            # Unexpected outcome - could be good or bad
            if prediction.actual_success:
                return f"POSITIVE_SURPRISE: {prediction.tool_name} succeeded despite low confidence ({prediction.confidence:.0%})"
            else:
                return f"NEGATIVE_SURPRISE: {prediction.tool_name} failed unexpectedly"

        return None

    def get_calibration_report(self, tool_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Get confidence calibration report.

        Shows how well-calibrated predictions are - are high confidence
        predictions actually more likely to succeed?
        """
        tools = [tool_name] if tool_name else list(self.confidence_calibration.keys())

        report = {}
        for tool in tools:
            if tool not in self.confidence_calibration:
                continue

            data = self.confidence_calibration[tool]
            if not data:
                continue

            # Group by confidence buckets
            buckets = {
                "low (0-0.5)": [],
                "medium (0.5-0.8)": [],
                "high (0.8-1.0)": []
            }

            for conf, success in data:
                if conf < 0.5:
                    buckets["low (0-0.5)"].append(success)
                elif conf < 0.8:
                    buckets["medium (0.5-0.8)"].append(success)
                else:
                    buckets["high (0.8-1.0)"].append(success)

            bucket_stats = {}
            for bucket_name, outcomes in buckets.items():
                if outcomes:
                    success_rate = sum(outcomes) / len(outcomes)
                    bucket_stats[bucket_name] = {
                        "count": len(outcomes),
                        "success_rate": success_rate
                    }

            # Calculate overall calibration score
            # Perfect calibration: high confidence = high success, low confidence = low success
            total_predictions = len(data)
            avg_confidence = sum(c for c, _ in data) / total_predictions
            actual_success_rate = sum(s for _, s in data) / total_predictions
            calibration_gap = abs(avg_confidence - actual_success_rate)

            report[tool] = {
                "total_predictions": total_predictions,
                "avg_confidence": avg_confidence,
                "actual_success_rate": actual_success_rate,
                "calibration_gap": calibration_gap,
                "is_overconfident": avg_confidence > actual_success_rate + 0.1,
                "is_underconfident": actual_success_rate > avg_confidence + 0.1,
                "buckets": bucket_stats
            }

        return report

    def analyze_reasoning_patterns(self) -> List[ReasoningPattern]:
        """Analyze completed predictions to find reasoning patterns."""
        patterns = []

        if len(self.completed_predictions) < 5:
            return patterns

        # Pattern 1: Overconfidence detection
        overconfident = [
            p for p in self.completed_predictions
            if p.accuracy == PredictionAccuracy.WRONG and p.confidence >= 0.8
        ]
        if len(overconfident) >= 2:
            tools = [p.tool_name for p in overconfident]
            most_common_tool = max(set(tools), key=tools.count)
            patterns.append(ReasoningPattern(
                pattern_type="overconfidence",
                description=f"Overconfident predictions often fail with {most_common_tool}",
                conditions=[f"tool={most_common_tool}", "confidence>=0.8"],
                frequency=len(overconfident),
                confidence_delta=sum(p.confidence for p in overconfident) / len(overconfident) - 0.5,
                examples=[p.learning for p in overconfident[:3] if p.learning]
            ))

        # Pattern 2: Blind spots (repeated failures with same reasoning)
        reasoning_failures: Dict[str, List[Prediction]] = {}
        for p in self.completed_predictions:
            if p.accuracy == PredictionAccuracy.WRONG and p.reasoning:
                key = p.reasoning[:30].lower()
                if key not in reasoning_failures:
                    reasoning_failures[key] = []
                reasoning_failures[key].append(p)

        for reasoning, failures in reasoning_failures.items():
            if len(failures) >= 2:
                patterns.append(ReasoningPattern(
                    pattern_type="blind_spot",
                    description=f"Repeated failures when reasoning: '{reasoning}...'",
                    conditions=[f"reasoning_contains={reasoning}"],
                    frequency=len(failures),
                    confidence_delta=0.0,
                    examples=[f.learning for f in failures[:2] if f.learning]
                ))

        # Pattern 3: Risk factors that actually predict failure
        risk_hits: Dict[str, int] = {}
        risk_total: Dict[str, int] = {}

        for p in self.completed_predictions:
            for risk in p.risk_factors:
                risk_key = risk.lower()[:30]
                risk_total[risk_key] = risk_total.get(risk_key, 0) + 1
                if not p.actual_success:
                    risk_hits[risk_key] = risk_hits.get(risk_key, 0) + 1

        for risk, hits in risk_hits.items():
            total = risk_total.get(risk, 1)
            hit_rate = hits / total
            if hit_rate >= 0.5 and total >= 2:
                patterns.append(ReasoningPattern(
                    pattern_type="predictive_risk",
                    description=f"Risk factor '{risk}' predicts failure {hit_rate:.0%} of the time",
                    conditions=[f"risk_factor={risk}"],
                    frequency=total,
                    confidence_delta=hit_rate,
                    examples=[]
                ))

        self.patterns = patterns
        return patterns

    async def store_learnings_in_mind(self) -> int:
        """Store significant learnings in Mind."""
        if not await self.mind.is_available():
            return 0

        memories = []

        # Store learnings from wrong predictions (most valuable)
        for p in self.completed_predictions:
            if p.learning and p.accuracy in (PredictionAccuracy.WRONG, PredictionAccuracy.SURPRISING):
                memory = Memory(
                    content=f"REASONING [{p.accuracy.value.upper()}]: {p.learning}",
                    temporal_level=TemporalLevel.IDENTITY,
                    salience=0.8 if p.accuracy == PredictionAccuracy.WRONG else 0.6,
                    content_type=ContentType.REFLECTION,
                    metadata={
                        "tool": p.tool_name,
                        "predicted_success": p.expected_success,
                        "actual_success": p.actual_success,
                        "confidence": p.confidence,
                        "accuracy": p.accuracy.value
                    }
                )
                memories.append(memory)

        # Store reasoning patterns
        for pattern in self.patterns:
            if pattern.frequency >= 3:
                memory = Memory(
                    content=f"REASONING_PATTERN [{pattern.pattern_type.upper()}]: {pattern.description}",
                    temporal_level=TemporalLevel.IDENTITY,
                    salience=0.9,
                    content_type=ContentType.REFLECTION,
                    metadata={
                        "pattern_type": pattern.pattern_type,
                        "frequency": pattern.frequency,
                        "conditions": pattern.conditions,
                        "confidence_delta": pattern.confidence_delta
                    }
                )
                memories.append(memory)

        if memories:
            stored = await self.mind.store_batch(memories)
            return stored
        return 0

    def get_prediction_advice(self, tool_name: str, intent: str) -> Optional[str]:
        """
        Get advice based on past predictions for this tool/intent combo.

        This is the injection point - feeding learnings back into decisions.
        """
        # Check calibration
        report = self.get_calibration_report(tool_name)
        if tool_name in report:
            tool_report = report[tool_name]
            if tool_report["is_overconfident"]:
                return f"Caution: historically overconfident with {tool_name} (actual success: {tool_report['actual_success_rate']:.0%})"

        # Check for relevant patterns
        for pattern in self.patterns:
            if pattern.pattern_type == "overconfidence":
                if tool_name in str(pattern.conditions):
                    return f"Watch for overconfidence: {pattern.description}"

            if pattern.pattern_type == "blind_spot":
                if any(word in intent.lower() for word in pattern.conditions[0].split("=")[1].split()):
                    return f"Blind spot warning: {pattern.description}"

        return None

    def get_stats(self) -> Dict[str, Any]:
        """Get tracking statistics."""
        total = len(self.completed_predictions)
        if total == 0:
            return {"total_predictions": 0}

        accuracy_counts = {a.value: 0 for a in PredictionAccuracy}
        for p in self.completed_predictions:
            if p.accuracy:
                accuracy_counts[p.accuracy.value] += 1

        return {
            "total_predictions": total,
            "active_predictions": len(self.active_predictions),
            "accuracy_breakdown": accuracy_counts,
            "correct_rate": accuracy_counts["correct"] / total,
            "wrong_rate": accuracy_counts["wrong"] / total,
            "patterns_found": len(self.patterns),
            "tools_tracked": len(self.confidence_calibration)
        }

    def get_calibrated_confidence(self, tool_name: str, raw_confidence: float) -> float:
        """
        Get calibrated confidence for a tool.

        Adjusts raw confidence based on historical accuracy.
        If we're historically overconfident with a tool, this returns lower confidence.
        """
        # Check if we have a calibration factor
        if tool_name in self.calibration_factors:
            factor = self.calibration_factors[tool_name]
            calibrated = raw_confidence * factor
            # Clamp to valid range
            return max(0.1, min(0.99, calibrated))

        # Fall back to computing from raw data
        if tool_name not in self.confidence_calibration:
            return raw_confidence

        data = self.confidence_calibration[tool_name]
        if len(data) < 5:
            return raw_confidence  # Not enough data

        # Calculate actual success rate
        actual_success_rate = sum(s for _, s in data) / len(data)
        avg_confidence = sum(c for c, _ in data) / len(data)

        if avg_confidence == 0:
            return raw_confidence

        # Calibration factor: actual / predicted
        factor = actual_success_rate / avg_confidence
        # Clamp factor to reasonable range (0.5 to 1.5)
        factor = max(0.5, min(1.5, factor))

        calibrated = raw_confidence * factor
        return max(0.1, min(0.99, calibrated))

    def update_calibration_factors(self):
        """
        Update calibration factors from accumulated data.

        Call this periodically to update the calibration model.
        """
        for tool, data in self.confidence_calibration.items():
            if len(data) < 5:
                continue

            actual_success_rate = sum(s for _, s in data) / len(data)
            avg_confidence = sum(c for c, _ in data) / len(data)

            if avg_confidence > 0:
                factor = actual_success_rate / avg_confidence
                # Clamp to reasonable range
                self.calibration_factors[tool] = max(0.5, min(1.5, factor))

    async def save_calibration_to_mind(self) -> bool:
        """
        Save calibration factors to Mind for persistence.

        Returns True if saved successfully.
        """
        if not await self.mind.is_available():
            return False

        # Update factors from current data
        self.update_calibration_factors()

        if not self.calibration_factors:
            return False

        # Create a summary of calibration
        calibration_summary = []
        for tool, factor in self.calibration_factors.items():
            if tool in self.confidence_calibration:
                data = self.confidence_calibration[tool]
                actual_rate = sum(s for _, s in data) / len(data) if data else 0
                avg_conf = sum(c for c, _ in data) / len(data) if data else 0

                direction = "overconfident" if factor < 0.9 else "underconfident" if factor > 1.1 else "well-calibrated"
                calibration_summary.append(
                    f"{tool}: {direction} (factor={factor:.2f}, actual={actual_rate:.0%}, predicted={avg_conf:.0%})"
                )

        content = f"CALIBRATION: Confidence calibration factors updated.\n" + "\n".join(calibration_summary)

        memory = Memory(
            content=content,
            temporal_level=TemporalLevel.IDENTITY,
            salience=0.8,
            content_type=ContentType.REFLECTION,
            metadata={
                "type": "calibration",
                "calibration_factors": self.calibration_factors,
                "tools_calibrated": list(self.calibration_factors.keys())
            }
        )

        result = await self.mind.store(memory)
        return result is not None

    async def load_calibration_from_mind(self) -> int:
        """
        Load calibration factors from Mind.

        Returns number of tools with calibration loaded.
        """
        if not await self.mind.is_available():
            return 0

        # Query for calibration memories - use simple query, filter by content
        calibrations = await self.mind.retrieve(
            query="CALIBRATION",
            limit=10
        )

        loaded = 0
        for cal in calibrations:
            # Try metadata first
            metadata = cal.get("metadata", {})
            if metadata.get("type") == "calibration":
                factors = metadata.get("calibration_factors", {})
                for tool, factor in factors.items():
                    self.calibration_factors[tool] = factor
                    loaded += 1
                continue

            # Fall back to parsing content
            content = cal.get("content", "")
            if "CALIBRATION:" in content and "factor=" in content:
                import re
                # Parse lines like: "Edit: overconfident (factor=0.67, actual=60%, predicted=90%)"
                # Use [\w-]+ to match hyphenated words like "well-calibrated"
                matches = re.findall(r'(\w+): [\w-]+ \(factor=([0-9.]+)', content)
                for tool, factor_str in matches:
                    try:
                        self.calibration_factors[tool] = float(factor_str)
                        loaded += 1
                    except ValueError:
                        pass

        return loaded

    def get_calibration_summary(self) -> str:
        """Get human-readable calibration summary."""
        if not self.calibration_factors:
            return "No calibration data yet."

        lines = ["Confidence Calibration:"]
        for tool, factor in sorted(self.calibration_factors.items()):
            if factor < 0.9:
                status = "overconfident (reduce confidence)"
            elif factor > 1.1:
                status = "underconfident (increase confidence)"
            else:
                status = "well-calibrated"
            lines.append(f"  {tool}: {factor:.2f}x - {status}")

        return "\n".join(lines)

    async def close(self):
        """Close Mind client."""
        await self.mind.close()
