"""
Spark Introspection: Self-aware analysis of learning gaps.

This is different from the Witness (which observes systems) and the Learner
(which extracts patterns). Introspection asks deeper questions:

- What am I failing to learn?
- Where are my blind spots?
- What patterns should exist but don't?
- How can I improve my own learning?

This is recursive intelligence - thinking about thinking.
"""

import json
import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Set
from collections import defaultdict


@dataclass
class LearningGap:
    """A gap in Spark's learning."""
    gap_type: str  # blind_spot, stale_learning, missing_pattern, overconfidence
    description: str
    evidence: List[str]
    severity: str  # low, medium, high, critical
    suggested_action: str
    detected_at: float = field(default_factory=lambda: datetime.now().timestamp())

    def to_dict(self) -> dict:
        return {
            "gap_type": self.gap_type,
            "description": self.description,
            "evidence": self.evidence,
            "severity": self.severity,
            "suggested_action": self.suggested_action,
            "detected_at": self.detected_at
        }


@dataclass
class IntrospectionReport:
    """Complete self-analysis report."""
    timestamp: float
    total_learnings: int
    total_events_processed: int
    gaps_found: List[LearningGap]
    strengths: List[str]
    recommendations: List[str]
    self_assessment: str  # overall assessment

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "total_learnings": self.total_learnings,
            "total_events_processed": self.total_events_processed,
            "gaps_found": [g.to_dict() for g in self.gaps_found],
            "strengths": self.strengths,
            "recommendations": self.recommendations,
            "self_assessment": self.self_assessment
        }


class SparkIntrospection:
    """
    Self-aware analysis of Spark's learning.

    Asks the hard questions:
    - What am I not learning that I should be?
    - Where are my predictions consistently wrong?
    - What errors keep happening that I haven't learned to avoid?
    """

    def __init__(self, mind_client=None):
        from .mind_client import MindClient
        self.mind = mind_client or MindClient()

    async def introspect(self) -> IntrospectionReport:
        """
        Perform deep self-analysis.

        This is the main entry point - returns a complete report on
        what Spark knows, what it doesn't, and what it should do.
        """
        gaps = []
        strengths = []
        recommendations = []

        # Load all learnings
        learnings = await self._get_all_learnings()
        events_count = self._count_total_events()

        # Analysis 1: Blind spots - errors that keep happening but no learning exists
        blind_spots = await self._find_blind_spots(learnings)
        gaps.extend(blind_spots)

        # Analysis 2: Stale learnings - patterns that might be outdated
        stale = self._find_stale_learnings(learnings)
        gaps.extend(stale)

        # Analysis 3: Missing patterns - things we should have learned by now
        missing = await self._find_missing_patterns(learnings, events_count)
        gaps.extend(missing)

        # Analysis 4: Prediction accuracy - where are we overconfident?
        prediction_gaps = self._analyze_prediction_accuracy()
        gaps.extend(prediction_gaps)

        # Analysis 5: Goal completion analysis - what goal types do we struggle with?
        goal_gaps = self._analyze_goal_success()
        gaps.extend(goal_gaps)

        # Identify strengths
        strengths = self._identify_strengths(learnings)

        # Generate recommendations
        recommendations = self._generate_recommendations(gaps)

        # Overall self-assessment
        assessment = self._generate_assessment(gaps, strengths, learnings)

        return IntrospectionReport(
            timestamp=datetime.now().timestamp(),
            total_learnings=len(learnings),
            total_events_processed=events_count,
            gaps_found=gaps,
            strengths=strengths,
            recommendations=recommendations,
            self_assessment=assessment
        )

    async def _get_all_learnings(self) -> List[dict]:
        """Get all learnings from Mind."""
        try:
            # Mind API caps at ~100 results
            learnings = await self.mind.retrieve(
                query="LEARNING",
                limit=100
            )
            return learnings
        except:
            return []

    def _count_total_events(self) -> int:
        """Estimate total events processed."""
        # Check witness state for historical count
        state_file = Path.home() / ".spark" / "witness_state.json"
        if state_file.exists():
            try:
                state = json.loads(state_file.read_text())
                return state.get("learning_count", 0) * 10  # Rough estimate
            except:
                pass
        return 0

    async def _find_blind_spots(self, learnings: List[dict]) -> List[LearningGap]:
        """Find errors that keep happening but we haven't learned from."""
        gaps = []

        # Load goals to find failure patterns
        goals_file = Path.home() / ".spark" / "active_goals.json"
        if not goals_file.exists():
            return gaps

        try:
            goals = json.loads(goals_file.read_text())

            # Find abandoned goals (potential failures)
            abandoned = [g for g in goals.values() if g.get("status") == "abandoned"]

            if len(abandoned) >= 3:
                # Check if we have learnings about why goals get abandoned
                has_abandonment_learning = any(
                    "abandon" in l.get("content", "").lower()
                    for l in learnings
                )

                if not has_abandonment_learning:
                    gaps.append(LearningGap(
                        gap_type="blind_spot",
                        description="Goals frequently get abandoned but no learning exists about why",
                        evidence=[f"{len(abandoned)} goals abandoned"],
                        severity="medium",
                        suggested_action="Analyze abandoned goals to understand interruption patterns"
                    ))

            # Find goals with many actions but low success
            for g in goals.values():
                actions = len(g.get("actions", []))
                success = g.get("success_score", 0.5)
                if actions > 10 and success < 0.6:
                    goal_type = g.get("goal_type", "unknown")

                    # Check if we have strategy for this goal type
                    has_strategy = any(
                        goal_type in l.get("content", "")
                        for l in learnings
                        if "GOAL_STRATEGY" in l.get("content", "")
                    )

                    if not has_strategy:
                        gaps.append(LearningGap(
                            gap_type="blind_spot",
                            description=f"No effective strategy learned for '{goal_type}' goals despite attempts",
                            evidence=[f"Goal with {actions} actions, {success:.0%} success"],
                            severity="high",
                            suggested_action=f"Analyze successful {goal_type} patterns from other sessions"
                        ))

        except Exception as e:
            pass

        return gaps

    def _find_stale_learnings(self, learnings: List[dict]) -> List[LearningGap]:
        """Find learnings that might be outdated."""
        gaps = []

        # Check for learnings with low sample sizes that haven't been updated
        for learning in learnings:
            content = learning.get("content", "")

            # Parse sample size from content
            if "samples" in content.lower():
                try:
                    # Extract number before "samples"
                    import re
                    match = re.search(r'(\d+)\s*samples', content.lower())
                    if match:
                        samples = int(match.group(1))
                        if samples < 5:
                            # Low sample size - might be unreliable
                            gaps.append(LearningGap(
                                gap_type="stale_learning",
                                description=f"Learning based on only {samples} samples - may be unreliable",
                                evidence=[content[:80] + "..."],
                                severity="low",
                                suggested_action="Gather more data before relying on this pattern"
                            ))
                except:
                    pass

        return gaps

    async def _find_missing_patterns(self, learnings: List[dict], events_count: int) -> List[LearningGap]:
        """Find patterns that should exist but don't."""
        gaps = []

        # Expected pattern types - search for each directly
        expected_types = {
            "TOOL_EFFECTIVENESS": "How well each tool works",
            "TOOL_SEQUENCE": "Which tool combinations work well",
            "ERROR_CATEGORY": "Common errors and how to avoid them",
            "GOAL_STRATEGY": "What works for different goal types"
        }

        found_types = set()

        # Search Mind directly for each pattern type (more reliable than searching generic "LEARNING")
        for ptype in expected_types:
            try:
                results = await self.mind.retrieve(query=ptype, limit=5)
                if results and len(results) > 0:
                    found_types.add(ptype)
            except:
                pass

        missing = set(expected_types.keys()) - found_types

        for ptype in missing:
            if events_count > 50:  # Should have learned by now
                gaps.append(LearningGap(
                    gap_type="missing_pattern",
                    description=f"No {ptype} patterns learned despite {events_count}+ events",
                    evidence=[f"Expected: {expected_types[ptype]}"],
                    severity="medium",
                    suggested_action=f"Check if {ptype} extraction is working correctly"
                ))

        return gaps

    def _analyze_prediction_accuracy(self) -> List[LearningGap]:
        """Analyze prediction accuracy from predictions file."""
        gaps = []

        pred_file = Path.home() / ".spark" / "predictions.json"
        if not pred_file.exists():
            return gaps

        try:
            predictions = json.loads(pred_file.read_text())

            # Group by tool and check confidence vs actual
            tool_predictions = defaultdict(list)
            for key, pred in predictions.items():
                tool = pred.get("tool_name", "unknown")
                conf = pred.get("confidence", 0.5)
                tool_predictions[tool].append(conf)

            # Find tools where we're consistently high confidence
            for tool, confs in tool_predictions.items():
                if len(confs) >= 3:
                    avg_conf = sum(confs) / len(confs)
                    if avg_conf > 0.8:
                        gaps.append(LearningGap(
                            gap_type="overconfidence",
                            description=f"Consistently high confidence ({avg_conf:.0%}) for {tool} - verify accuracy",
                            evidence=[f"{len(confs)} predictions at avg {avg_conf:.0%}"],
                            severity="low",
                            suggested_action="Track actual outcomes to calibrate confidence"
                        ))

        except:
            pass

        return gaps

    def _analyze_goal_success(self) -> List[LearningGap]:
        """Analyze goal completion patterns."""
        gaps = []

        goals_file = Path.home() / ".spark" / "active_goals.json"
        if not goals_file.exists():
            return gaps

        try:
            goals = json.loads(goals_file.read_text())

            # Group by type
            by_type = defaultdict(list)
            for g in goals.values():
                gtype = g.get("goal_type", "unknown")
                by_type[gtype].append(g)

            # Check for struggling goal types
            for gtype, type_goals in by_type.items():
                completed = [g for g in type_goals if g.get("status") == "completed"]
                abandoned = [g for g in type_goals if g.get("status") == "abandoned"]

                if len(abandoned) > len(completed) and len(type_goals) >= 3:
                    gaps.append(LearningGap(
                        gap_type="blind_spot",
                        description=f"'{gtype}' goals fail more than succeed ({len(abandoned)} abandoned vs {len(completed)} completed)",
                        evidence=[f"Total: {len(type_goals)}, Abandoned: {len(abandoned)}"],
                        severity="high",
                        suggested_action=f"Analyze what makes '{gtype}' goals difficult and develop better strategies"
                    ))

            # Check for 'unknown' goal type overuse
            if "unknown" in by_type:
                unknown_count = len(by_type["unknown"])
                total = sum(len(v) for v in by_type.values())
                if unknown_count / total > 0.3:
                    gaps.append(LearningGap(
                        gap_type="missing_pattern",
                        description=f"{unknown_count}/{total} goals classified as 'unknown' - classification needs improvement",
                        evidence=["Goal classification is too limited"],
                        severity="medium",
                        suggested_action="Expand goal classification keywords or add ML-based classification"
                    ))

        except:
            pass

        return gaps

    def _identify_strengths(self, learnings: List[dict]) -> List[str]:
        """Identify what Spark is doing well."""
        strengths = []

        # Count learning types
        types = defaultdict(int)
        for l in learnings:
            content = l.get("content", "")
            if "TOOL_EFFECTIVENESS" in content:
                types["tool_effectiveness"] += 1
            elif "TOOL_SEQUENCE" in content:
                types["tool_sequence"] += 1
            elif "GOAL_STRATEGY" in content:
                types["goal_strategy"] += 1
            elif "ERROR_CATEGORY" in content:
                types["error_handling"] += 1

        if types["tool_sequence"] > 5:
            strengths.append(f"Learning tool sequences well ({types['tool_sequence']} patterns)")

        if types["tool_effectiveness"] > 3:
            strengths.append(f"Tracking tool effectiveness ({types['tool_effectiveness']} tools)")

        if types["goal_strategy"] > 0:
            strengths.append(f"Developing goal strategies ({types['goal_strategy']} strategies)")

        # Check goal completion
        goals_file = Path.home() / ".spark" / "active_goals.json"
        if goals_file.exists():
            try:
                goals = json.loads(goals_file.read_text())
                completed = sum(1 for g in goals.values() if g.get("status") == "completed")
                if completed > 0:
                    strengths.append(f"Successfully completing goals ({completed} completed)")
            except:
                pass

        if not strengths:
            strengths.append("Still gathering initial data")

        return strengths

    def _generate_recommendations(self, gaps: List[LearningGap]) -> List[str]:
        """Generate actionable recommendations from gaps."""
        recommendations = []

        # Prioritize by severity
        high_gaps = [g for g in gaps if g.severity in ("high", "critical")]
        medium_gaps = [g for g in gaps if g.severity == "medium"]

        if high_gaps:
            recommendations.append(f"PRIORITY: Address {len(high_gaps)} high-severity gaps first")
            for g in high_gaps[:2]:
                recommendations.append(f"  - {g.suggested_action}")

        if medium_gaps:
            recommendations.append(f"IMPROVE: {len(medium_gaps)} medium-severity gaps to work on")

        # General recommendations
        if any(g.gap_type == "blind_spot" for g in gaps):
            recommendations.append("Enable more detailed error tracking to reduce blind spots")

        if any(g.gap_type == "overconfidence" for g in gaps):
            recommendations.append("Implement confidence calibration based on actual outcomes")

        if any("unknown" in g.description for g in gaps):
            recommendations.append("Expand goal classification to reduce 'unknown' types")

        return recommendations

    def _generate_assessment(self, gaps: List[LearningGap], strengths: List[str], learnings: List[dict]) -> str:
        """Generate overall self-assessment."""

        high_gaps = len([g for g in gaps if g.severity in ("high", "critical")])
        total_gaps = len(gaps)

        if high_gaps == 0 and total_gaps < 3:
            return "HEALTHY: Learning system is functioning well with few gaps"
        elif high_gaps == 0:
            return "GOOD: Minor improvements possible but core learning is solid"
        elif high_gaps <= 2:
            return "NEEDS ATTENTION: Some significant gaps in learning that should be addressed"
        else:
            return "STRUGGLING: Multiple critical gaps - learning system needs improvement"

    def explain(self, report: IntrospectionReport) -> str:
        """Generate human-readable explanation of introspection."""
        lines = []

        lines.append("\n" + "=" * 60)
        lines.append("SPARK INTROSPECTION: What Am I Not Learning?")
        lines.append("=" * 60)

        lines.append(f"\nSelf-Assessment: {report.self_assessment}")
        lines.append(f"Total Learnings: {report.total_learnings}")

        # Strengths
        lines.append("\n--- Strengths ---")
        for s in report.strengths:
            lines.append(f"  + {s}")

        # Gaps
        if report.gaps_found:
            lines.append("\n--- Learning Gaps ---")
            for gap in sorted(report.gaps_found, key=lambda g: {"critical": 0, "high": 1, "medium": 2, "low": 3}.get(g.severity, 4)):
                severity_icon = {"critical": "!!!", "high": "!!", "medium": "!", "low": "."}.get(gap.severity, "?")
                lines.append(f"  [{severity_icon}] {gap.description}")
                lines.append(f"      Action: {gap.suggested_action}")
        else:
            lines.append("\n--- No significant gaps found ---")

        # Recommendations
        if report.recommendations:
            lines.append("\n--- Recommendations ---")
            for r in report.recommendations:
                lines.append(f"  > {r}")

        lines.append("\n" + "=" * 60)

        return "\n".join(lines)


async def introspect() -> str:
    """Quick access to introspection."""
    intro = SparkIntrospection()
    report = await intro.introspect()
    result = intro.explain(report)
    await intro.mind.close()
    return result


if __name__ == "__main__":
    # CLI usage
    async def main():
        result = await introspect()
        print(result)

    asyncio.run(main())
