"""
Spark Auto-Improve: Act on self-discovered gaps.

This closes the recursive loop. When introspection finds a gap,
auto-improve takes action:

- blind_spot → trigger targeted learning
- missing_pattern → run extraction for that pattern type
- overconfidence → adjust confidence calibration
- stale_learning → mark for refresh

The system improves itself without human intervention.
"""

import json
import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .introspect import SparkIntrospection, LearningGap, IntrospectionReport
from .mind_client import MindClient, Memory, TemporalLevel, ContentType


@dataclass
class ImprovementAction:
    """An action taken to address a learning gap."""
    gap_type: str
    description: str
    action_taken: str
    success: bool
    details: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=lambda: datetime.now().timestamp())

    def to_dict(self) -> dict:
        return {
            "gap_type": self.gap_type,
            "description": self.description,
            "action_taken": self.action_taken,
            "success": self.success,
            "details": self.details,
            "timestamp": self.timestamp
        }


@dataclass
class ImprovementReport:
    """Report of auto-improvement actions taken."""
    timestamp: float
    gaps_found: int
    actions_taken: List[ImprovementAction]
    improvements_made: int
    summary: str

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "gaps_found": self.gaps_found,
            "actions_taken": [a.to_dict() for a in self.actions_taken],
            "improvements_made": self.improvements_made,
            "summary": self.summary
        }


class SparkAutoImprove:
    """
    Autonomous self-improvement based on introspection.

    The recursive loop:
    1. Introspect → find gaps
    2. For each gap → take specific action
    3. Store what was done → learn from improvement attempts
    4. Next introspection → verify if gap was addressed
    """

    IMPROVEMENT_LOG = Path.home() / ".spark" / "improvement_log.json"

    def __init__(self, mind_client: Optional[MindClient] = None):
        self.mind = mind_client or MindClient()
        self.introspection = SparkIntrospection(self.mind)
        self.actions_taken: List[ImprovementAction] = []

    async def improve(self) -> ImprovementReport:
        """
        Run the full auto-improvement cycle.

        1. Introspect to find gaps
        2. Take action on each gap
        3. Report what was done
        """
        # Step 1: Introspect
        report = await self.introspection.introspect()

        # Step 2: Act on each gap
        for gap in report.gaps_found:
            action = await self._act_on_gap(gap)
            if action:
                self.actions_taken.append(action)

        # Step 3: Generate improvement report
        improvements = sum(1 for a in self.actions_taken if a.success)

        summary = self._generate_summary(report, self.actions_taken)

        improvement_report = ImprovementReport(
            timestamp=datetime.now().timestamp(),
            gaps_found=len(report.gaps_found),
            actions_taken=self.actions_taken,
            improvements_made=improvements,
            summary=summary
        )

        # Step 4: Log what we did (for learning about improvement)
        await self._log_improvement(improvement_report)

        return improvement_report

    async def _act_on_gap(self, gap: LearningGap) -> Optional[ImprovementAction]:
        """
        Take action based on gap type.

        Each gap type has a specific remediation strategy.
        """
        if gap.gap_type == "blind_spot":
            return await self._fix_blind_spot(gap)
        elif gap.gap_type == "missing_pattern":
            return await self._fix_missing_pattern(gap)
        elif gap.gap_type == "overconfidence":
            return await self._fix_overconfidence(gap)
        elif gap.gap_type == "stale_learning":
            return await self._fix_stale_learning(gap)
        else:
            return None

    async def _fix_blind_spot(self, gap: LearningGap) -> ImprovementAction:
        """
        Fix a blind spot by creating an explicit learning about it.

        If we keep failing at something but haven't learned why,
        create a learning that acknowledges the gap.
        """
        # Extract key info from the gap
        description = gap.description

        # Create a learning that acknowledges this blind spot
        learning_content = f"LEARNING [BLIND_SPOT]: {description}. " \
                          f"Action needed: {gap.suggested_action}. " \
                          f"Evidence: {', '.join(gap.evidence[:2])}."

        try:
            memory = Memory(
                content=learning_content,
                temporal_level=TemporalLevel.IDENTITY,
                salience=0.8,  # High salience - this is important
                content_type=ContentType.REFLECTION,
                metadata={
                    "gap_type": "blind_spot",
                    "auto_generated": True,
                    "suggested_action": gap.suggested_action
                }
            )

            result = await self.mind.store(memory)

            return ImprovementAction(
                gap_type="blind_spot",
                description=description,
                action_taken="Created explicit learning about blind spot",
                success=result is not None,
                details={"learning_stored": learning_content[:100]}
            )
        except Exception as e:
            return ImprovementAction(
                gap_type="blind_spot",
                description=description,
                action_taken="Failed to store blind spot learning",
                success=False,
                details={"error": str(e)}
            )

    async def _fix_missing_pattern(self, gap: LearningGap) -> ImprovementAction:
        """
        Fix missing pattern by triggering extraction.

        If we should have learned X by now but haven't,
        flag it for the next processing cycle.
        """
        # Extract pattern type from description
        pattern_type = "unknown"
        for ptype in ["ERROR_CATEGORY", "GOAL_STRATEGY", "TOOL_SEQUENCE", "TOOL_EFFECTIVENESS"]:
            if ptype in gap.description:
                pattern_type = ptype
                break

        # Create a flag file for the processor to pick up
        flag_file = Path.home() / ".spark" / "extraction_flags.json"

        try:
            flags = {}
            if flag_file.exists():
                flags = json.loads(flag_file.read_text())

            flags[pattern_type] = {
                "requested_at": datetime.now().isoformat(),
                "reason": gap.description,
                "priority": "high" if gap.severity in ("high", "critical") else "normal"
            }

            flag_file.write_text(json.dumps(flags, indent=2))

            return ImprovementAction(
                gap_type="missing_pattern",
                description=gap.description,
                action_taken=f"Flagged {pattern_type} for priority extraction",
                success=True,
                details={"pattern_type": pattern_type}
            )
        except Exception as e:
            return ImprovementAction(
                gap_type="missing_pattern",
                description=gap.description,
                action_taken="Failed to flag pattern for extraction",
                success=False,
                details={"error": str(e)}
            )

    async def _fix_overconfidence(self, gap: LearningGap) -> ImprovementAction:
        """
        Fix overconfidence by creating calibration note.

        If we're consistently overconfident about something,
        store a learning to be more cautious.
        """
        learning_content = f"LEARNING [CALIBRATION]: {gap.description}. " \
                          f"Reduce confidence for predictions in this area. " \
                          f"Evidence: {', '.join(gap.evidence[:2])}."

        try:
            memory = Memory(
                content=learning_content,
                temporal_level=TemporalLevel.IDENTITY,
                salience=0.7,
                content_type=ContentType.REFLECTION,
                metadata={
                    "gap_type": "overconfidence",
                    "auto_generated": True,
                    "calibration": "reduce_confidence"
                }
            )

            result = await self.mind.store(memory)

            return ImprovementAction(
                gap_type="overconfidence",
                description=gap.description,
                action_taken="Created calibration learning",
                success=result is not None,
                details={"calibration": "reduce_confidence"}
            )
        except Exception as e:
            return ImprovementAction(
                gap_type="overconfidence",
                description=gap.description,
                action_taken="Failed to store calibration",
                success=False,
                details={"error": str(e)}
            )

    async def _fix_stale_learning(self, gap: LearningGap) -> ImprovementAction:
        """
        Fix stale learning by marking it for refresh.

        Old learnings with low sample sizes should be
        re-validated with new data.
        """
        # Create a refresh flag
        flag_file = Path.home() / ".spark" / "refresh_flags.json"

        try:
            flags = {}
            if flag_file.exists():
                flags = json.loads(flag_file.read_text())

            # Use first part of evidence as key
            key = gap.evidence[0][:50] if gap.evidence else "unknown"
            flags[key] = {
                "requested_at": datetime.now().isoformat(),
                "reason": "Low sample size - needs more data",
                "original_description": gap.description
            }

            flag_file.write_text(json.dumps(flags, indent=2))

            return ImprovementAction(
                gap_type="stale_learning",
                description=gap.description,
                action_taken="Marked learning for refresh",
                success=True,
                details={"flagged_for_refresh": True}
            )
        except Exception as e:
            return ImprovementAction(
                gap_type="stale_learning",
                description=gap.description,
                action_taken="Failed to flag for refresh",
                success=False,
                details={"error": str(e)}
            )

    def _generate_summary(self, intro_report: IntrospectionReport,
                         actions: List[ImprovementAction]) -> str:
        """Generate human-readable summary of improvements."""
        if not actions:
            return "No actions taken - no actionable gaps found."

        successful = sum(1 for a in actions if a.success)
        total = len(actions)

        if successful == total:
            return f"All {total} improvements successful."
        elif successful > 0:
            return f"{successful}/{total} improvements successful."
        else:
            return "No improvements succeeded - manual intervention may be needed."

    async def _log_improvement(self, report: ImprovementReport):
        """Log improvement attempt for meta-learning."""
        try:
            self.IMPROVEMENT_LOG.parent.mkdir(parents=True, exist_ok=True)

            # Load existing log
            log = []
            if self.IMPROVEMENT_LOG.exists():
                try:
                    log = json.loads(self.IMPROVEMENT_LOG.read_text())
                except:
                    log = []

            # Append this report
            log.append(report.to_dict())

            # Keep last 50 improvements
            if len(log) > 50:
                log = log[-50:]

            self.IMPROVEMENT_LOG.write_text(json.dumps(log, indent=2))

            # Also store in Mind for persistence
            if report.improvements_made > 0:
                memory = Memory(
                    content=f"SELF_IMPROVEMENT: Made {report.improvements_made} improvements. "
                           f"Gaps addressed: {report.gaps_found}. {report.summary}",
                    temporal_level=TemporalLevel.SEASONAL,
                    salience=0.6,
                    content_type=ContentType.EVENT,
                    metadata={
                        "type": "self_improvement",
                        "improvements": report.improvements_made,
                        "gaps": report.gaps_found
                    }
                )
                await self.mind.store(memory)

        except Exception:
            pass  # Don't fail the whole process if logging fails

    def explain(self, report: ImprovementReport) -> str:
        """Generate human-readable explanation."""
        lines = []

        lines.append("\n" + "=" * 60)
        lines.append("SPARK AUTO-IMPROVE: Actions Taken")
        lines.append("=" * 60)

        lines.append(f"\nGaps Found: {report.gaps_found}")
        lines.append(f"Actions Taken: {len(report.actions_taken)}")
        lines.append(f"Improvements Made: {report.improvements_made}")
        lines.append(f"\nSummary: {report.summary}")

        if report.actions_taken:
            lines.append("\n--- Actions ---")
            for action in report.actions_taken:
                status = "[OK]" if action.success else "[FAIL]"
                lines.append(f"  {status} {action.gap_type}: {action.action_taken}")
                if not action.success and "error" in action.details:
                    lines.append(f"       Error: {action.details['error'][:50]}")

        lines.append("\n" + "=" * 60)

        return "\n".join(lines)

    async def close(self):
        """Clean up resources."""
        await self.mind.close()


async def auto_improve() -> str:
    """Quick access to auto-improvement."""
    improver = SparkAutoImprove()
    report = await improver.improve()
    result = improver.explain(report)
    await improver.close()
    return result


if __name__ == "__main__":
    async def main():
        result = await auto_improve()
        print(result)

    asyncio.run(main())
