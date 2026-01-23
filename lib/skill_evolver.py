"""
Spark Skill Evolver: Track skill usage and propose improvements.

The skill evolver:
1. Tracks when skills are invoked and their outcomes
2. Calculates skill effectiveness by task type
3. Identifies skill gaps (missing skills for common tasks)
4. Proposes improvements to existing skills

All operations are async and integrate with Mind for persistence.
"""

import asyncio
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime

from .queue import SparkEvent, EventType
from .mind_client import (
    MindClient, Memory, ContentType, TemporalLevel
)


@dataclass
class SkillUsage:
    """A single skill usage record."""
    skill_id: str
    task_context: str  # What was the user trying to do
    outcome: str  # success, failure, partial
    duration_ms: Optional[float] = None
    error: Optional[str] = None
    session_id: Optional[str] = None
    timestamp: float = field(default_factory=lambda: datetime.now().timestamp())


@dataclass
class SkillStats:
    """Aggregated statistics for a skill."""
    skill_id: str
    total_uses: int = 0
    successes: int = 0
    failures: int = 0
    partial: int = 0
    total_duration_ms: float = 0.0
    task_types: Dict[str, int] = field(default_factory=dict)  # task_type -> count
    error_types: Dict[str, int] = field(default_factory=dict)  # error_type -> count

    @property
    def success_rate(self) -> float:
        if self.total_uses == 0:
            return 0.0
        return self.successes / self.total_uses

    @property
    def avg_duration_ms(self) -> float:
        if self.total_uses == 0:
            return 0.0
        return self.total_duration_ms / self.total_uses

    @property
    def most_common_task(self) -> Optional[str]:
        if not self.task_types:
            return None
        return max(self.task_types.items(), key=lambda x: x[1])[0]


@dataclass
class SkillGap:
    """An identified gap in skill coverage."""
    task_type: str
    frequency: int  # How often this task type occurs
    current_success_rate: float  # Success rate without dedicated skill
    suggested_skill: Optional[str] = None  # Existing skill that might help
    improvement_potential: float = 0.0  # Estimated improvement if skill added


@dataclass
class SkillImprovement:
    """A proposed improvement to an existing skill."""
    skill_id: str
    improvement_type: str  # error_handling, example_addition, clarity, scope
    description: str
    evidence: List[str]  # What data supports this improvement
    confidence: float
    priority: int  # 1=high, 2=medium, 3=low


class SkillEvolver:
    """
    Tracks skill usage and proposes improvements.

    Integrates with Spawner skills and Mind for persistence.
    """

    def __init__(self, mind_client: Optional[MindClient] = None):
        self.mind = mind_client or MindClient()
        self.skill_stats: Dict[str, SkillStats] = defaultdict(
            lambda: SkillStats(skill_id="unknown")
        )
        self.usage_history: List[SkillUsage] = []
        self.task_outcomes: Dict[str, List[bool]] = defaultdict(list)  # task_type -> outcomes
        self.gaps_identified: List[SkillGap] = []
        self.improvements_proposed: List[SkillImprovement] = []

    async def load_existing_data(self):
        """Load existing skill effectiveness data from Mind."""
        # Load skill effectiveness learnings
        learnings = await self.mind.retrieve(
            query="SKILL_EFFECTIVENESS",
            limit=50,
            temporal_level=TemporalLevel.IDENTITY,
            content_type=ContentType.REFLECTION
        )

        for learning in learnings:
            content = learning.get("content", "")
            # Parse existing skill stats from learning content
            if "skill=" in content:
                self._parse_skill_learning(content)

    def _parse_skill_learning(self, content: str):
        """Parse a skill learning from Mind into stats."""
        # Format: "LEARNING [SKILL_EFFECTIVENESS]: skill_id has X% success..."
        try:
            if "skill=" not in content:
                return

            # Extract skill_id
            skill_part = content.split("skill=")[1]
            skill_id = skill_part.split()[0].strip(".,")

            # Extract success rate if present
            if "%" in content:
                rate_part = content.split("%")[0]
                rate = float(rate_part.split()[-1]) / 100

                # Initialize stats with this data
                if skill_id not in self.skill_stats:
                    self.skill_stats[skill_id] = SkillStats(skill_id=skill_id)
                # We don't have exact counts, but we have the rate
        except Exception:
            pass  # Graceful degradation

    def track_skill_usage(self, event: SparkEvent) -> Optional[SkillUsage]:
        """
        Track a skill usage event.

        Called when we detect a Skill tool invocation.
        """
        tool_input = event.tool_input or {}

        # Extract skill info from tool input
        skill_id = tool_input.get("skill") or tool_input.get("name", "unknown")

        # Determine outcome from event type
        if event.event_type == EventType.POST_TOOL:
            outcome = "success"
        elif event.event_type == EventType.POST_TOOL_FAILURE:
            outcome = "failure"
        else:
            outcome = "unknown"

        # Try to infer task context from surrounding events
        task_context = self._infer_task_context(event)

        usage = SkillUsage(
            skill_id=skill_id,
            task_context=task_context,
            outcome=outcome,
            duration_ms=event.duration_ms,
            error=event.error,
            session_id=event.session_id,
            timestamp=event.timestamp
        )

        self.usage_history.append(usage)
        self._update_skill_stats(usage)

        return usage

    def _infer_task_context(self, event: SparkEvent) -> str:
        """Infer what task the user was trying to accomplish."""
        # Use skill args or data to infer context
        tool_input = event.tool_input or {}
        data = event.data or {}

        # Check for explicit task indicators
        args = tool_input.get("args", "")
        skill_id = tool_input.get("skill", "")

        # Categorize by skill type
        if any(x in skill_id.lower() for x in ["auth", "login", "oauth"]):
            return "authentication"
        elif any(x in skill_id.lower() for x in ["db", "database", "supabase", "postgres"]):
            return "database"
        elif any(x in skill_id.lower() for x in ["api", "rest", "graphql"]):
            return "api_design"
        elif any(x in skill_id.lower() for x in ["test", "spec", "jest"]):
            return "testing"
        elif any(x in skill_id.lower() for x in ["deploy", "ci", "cd"]):
            return "deployment"
        elif any(x in skill_id.lower() for x in ["ui", "component", "react", "vue"]):
            return "frontend"
        else:
            return "general"

    def _update_skill_stats(self, usage: SkillUsage):
        """Update aggregated stats for a skill."""
        stats = self.skill_stats[usage.skill_id]
        stats.skill_id = usage.skill_id
        stats.total_uses += 1

        if usage.outcome == "success":
            stats.successes += 1
        elif usage.outcome == "failure":
            stats.failures += 1
            if usage.error:
                error_type = self._categorize_error(usage.error)
                stats.error_types[error_type] = stats.error_types.get(error_type, 0) + 1
        else:
            stats.partial += 1

        if usage.duration_ms:
            stats.total_duration_ms += usage.duration_ms

        # Track task types
        stats.task_types[usage.task_context] = stats.task_types.get(usage.task_context, 0) + 1

        # Track task outcomes for gap analysis
        self.task_outcomes[usage.task_context].append(usage.outcome == "success")

    def _categorize_error(self, error: str) -> str:
        """Categorize an error into a type."""
        error_lower = error.lower()

        if "not found" in error_lower or "missing" in error_lower:
            return "missing_resource"
        elif "permission" in error_lower or "access" in error_lower:
            return "permission"
        elif "timeout" in error_lower:
            return "timeout"
        elif "syntax" in error_lower or "parse" in error_lower:
            return "syntax"
        elif "config" in error_lower or "env" in error_lower:
            return "configuration"
        else:
            return "other"

    async def process_events(self, events: List[SparkEvent]) -> List[SkillUsage]:
        """Process a batch of events and extract skill usages."""
        usages = []

        for event in events:
            # Check if this is a Skill tool invocation
            if event.tool_name == "Skill":
                usage = self.track_skill_usage(event)
                if usage:
                    usages.append(usage)

        return usages

    def identify_gaps(self, min_frequency: int = 3) -> List[SkillGap]:
        """
        Identify gaps in skill coverage.

        A gap is a task type with:
        - High frequency (many attempts)
        - Low success rate (no good skill for it)
        """
        gaps = []

        for task_type, outcomes in self.task_outcomes.items():
            if len(outcomes) < min_frequency:
                continue

            success_rate = sum(outcomes) / len(outcomes)

            # Gap threshold: less than 70% success with 5+ attempts
            if success_rate < 0.7 and len(outcomes) >= 5:
                gap = SkillGap(
                    task_type=task_type,
                    frequency=len(outcomes),
                    current_success_rate=success_rate,
                    improvement_potential=0.9 - success_rate  # Target 90%
                )

                # Try to find a skill that might help
                gap.suggested_skill = self._find_related_skill(task_type)
                gaps.append(gap)

        # Sort by improvement potential
        gaps.sort(key=lambda g: g.improvement_potential, reverse=True)
        self.gaps_identified = gaps

        return gaps

    def _find_related_skill(self, task_type: str) -> Optional[str]:
        """Find an existing skill that might help with this task type."""
        # Look for skills that have been successful with similar tasks
        best_skill = None
        best_rate = 0.0

        for skill_id, stats in self.skill_stats.items():
            if task_type in stats.task_types and stats.success_rate > best_rate:
                best_skill = skill_id
                best_rate = stats.success_rate

        return best_skill if best_rate > 0.7 else None

    def propose_improvements(self, min_samples: int = 5) -> List[SkillImprovement]:
        """
        Analyze skill usage and propose improvements.

        Types of improvements:
        - error_handling: Skill causes specific errors frequently
        - example_addition: Skill used in ways not covered by examples
        - clarity: Skill misused or misunderstood
        - scope: Skill scope too narrow or too broad
        """
        improvements = []

        for skill_id, stats in self.skill_stats.items():
            if stats.total_uses < min_samples:
                continue

            # Check for recurring errors -> error_handling improvement
            for error_type, count in stats.error_types.items():
                if count >= 3 and count / stats.failures > 0.3:
                    improvement = SkillImprovement(
                        skill_id=skill_id,
                        improvement_type="error_handling",
                        description=f"Add handling for {error_type} errors ({count} occurrences)",
                        evidence=[
                            f"{error_type} errors: {count}",
                            f"Total failures: {stats.failures}",
                            f"Error rate: {count/stats.total_uses:.0%}"
                        ],
                        confidence=min(count / 10, 1.0),
                        priority=1 if count / stats.total_uses > 0.2 else 2
                    )
                    improvements.append(improvement)

            # Check for low success rate -> clarity improvement
            if stats.success_rate < 0.7 and stats.total_uses >= 10:
                improvement = SkillImprovement(
                    skill_id=skill_id,
                    improvement_type="clarity",
                    description=f"Skill has low success rate ({stats.success_rate:.0%}), may need clearer instructions",
                    evidence=[
                        f"Success rate: {stats.success_rate:.0%}",
                        f"Total uses: {stats.total_uses}",
                        f"Most common task: {stats.most_common_task}"
                    ],
                    confidence=min(stats.total_uses / 20, 1.0),
                    priority=1
                )
                improvements.append(improvement)

            # Check for task type concentration -> scope improvement
            if stats.most_common_task:
                task_concentration = stats.task_types.get(stats.most_common_task, 0) / stats.total_uses
                if task_concentration > 0.8:
                    improvement = SkillImprovement(
                        skill_id=skill_id,
                        improvement_type="scope",
                        description=f"Skill heavily used for {stats.most_common_task} ({task_concentration:.0%}), consider specializing",
                        evidence=[
                            f"Task concentration: {task_concentration:.0%}",
                            f"Task type: {stats.most_common_task}",
                            f"Total uses: {stats.total_uses}"
                        ],
                        confidence=task_concentration,
                        priority=3
                    )
                    improvements.append(improvement)

        # Sort by priority then confidence
        improvements.sort(key=lambda i: (i.priority, -i.confidence))
        self.improvements_proposed = improvements

        return improvements

    async def store_learnings_in_mind(self) -> int:
        """Store skill effectiveness learnings in Mind."""
        memories = []

        # Store skill effectiveness patterns
        for skill_id, stats in self.skill_stats.items():
            if stats.total_uses >= 5:  # Minimum samples
                confidence = min(stats.total_uses / 20, 1.0)

                if confidence >= 0.5:  # Store if reasonably confident
                    content = (
                        f"LEARNING [SKILL_EFFECTIVENESS]: {skill_id} has {stats.success_rate:.0%} success rate. "
                        f"Conditions: skill={skill_id}, samples={stats.total_uses}. "
                        f"Most used for: {stats.most_common_task or 'general'}. "
                        f"Confidence: {confidence:.0%}"
                    )

                    memory = Memory(
                        content=content,
                        temporal_level=TemporalLevel.IDENTITY,
                        salience=confidence,
                        content_type=ContentType.REFLECTION,
                        metadata={
                            "pattern_type": "skill_effectiveness",
                            "skill_id": skill_id,
                            "success_rate": stats.success_rate,
                            "total_uses": stats.total_uses,
                            "most_common_task": stats.most_common_task
                        }
                    )
                    memories.append(memory)

        # Store gap identifications
        for gap in self.gaps_identified[:5]:  # Top 5 gaps
            content = (
                f"LEARNING [SKILL_GAP]: Task type '{gap.task_type}' has {gap.current_success_rate:.0%} success "
                f"with {gap.frequency} attempts. Improvement potential: {gap.improvement_potential:.0%}. "
                f"Suggested skill: {gap.suggested_skill or 'none found'}."
            )

            memory = Memory(
                content=content,
                temporal_level=TemporalLevel.SEASONAL,
                salience=gap.improvement_potential,
                content_type=ContentType.REFLECTION,
                metadata={
                    "pattern_type": "skill_gap",
                    "task_type": gap.task_type,
                    "success_rate": gap.current_success_rate,
                    "frequency": gap.frequency
                }
            )
            memories.append(memory)

        # Store improvement proposals
        for improvement in self.improvements_proposed[:5]:  # Top 5
            if improvement.confidence >= 0.7:
                content = (
                    f"LEARNING [SKILL_IMPROVEMENT]: {improvement.skill_id} needs {improvement.improvement_type}. "
                    f"{improvement.description}. Priority: {improvement.priority}. "
                    f"Evidence: {'; '.join(improvement.evidence[:2])}."
                )

                memory = Memory(
                    content=content,
                    temporal_level=TemporalLevel.SEASONAL,
                    salience=improvement.confidence,
                    content_type=ContentType.DECISION,
                    metadata={
                        "pattern_type": "skill_improvement",
                        "skill_id": improvement.skill_id,
                        "improvement_type": improvement.improvement_type,
                        "priority": improvement.priority
                    }
                )
                memories.append(memory)

        if memories:
            return await self.mind.store_batch(memories)
        return 0

    def get_skill_ranking(self) -> List[Tuple[str, float, int]]:
        """Get skills ranked by effectiveness."""
        rankings = []

        for skill_id, stats in self.skill_stats.items():
            if stats.total_uses >= 3:
                rankings.append((skill_id, stats.success_rate, stats.total_uses))

        rankings.sort(key=lambda x: (x[1], x[2]), reverse=True)
        return rankings

    def get_recommendations_for_task(self, task_type: str) -> List[str]:
        """Get skill recommendations for a task type."""
        recommendations = []

        # Find skills that work well for this task type
        for skill_id, stats in self.skill_stats.items():
            if task_type in stats.task_types:
                task_count = stats.task_types[task_type]
                if task_count >= 2 and stats.success_rate >= 0.7:
                    recommendations.append(
                        f"{skill_id} ({stats.success_rate:.0%} success, used {task_count}x for {task_type})"
                    )

        return recommendations

    def clear_session_data(self):
        """Clear session-specific data."""
        self.usage_history = []
        # Keep skill_stats and task_outcomes for cumulative learning
