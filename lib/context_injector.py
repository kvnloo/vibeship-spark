"""
Spark Context Injector: Feed learnings back to Claude.

This closes the loop - Spark observes, learns, and now INJECTS
that intelligence back into Claude at session start.

The injector pulls from:
1. Tool effectiveness (Learner)
2. Skill recommendations (SkillEvolver)
3. Agent recommendations (AgentOrchestrator)
4. Error avoidance patterns (Learner)

All formatted concisely to fit in Claude's context window.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime

from .mind_client import MindClient, TemporalLevel, ContentType


@dataclass
class InjectionContext:
    """Context to inject into Claude's session."""
    tool_insights: List[str] = field(default_factory=list)
    skill_recommendations: List[Tuple[str, float, str]] = field(default_factory=list)  # (skill, confidence, reason)
    agent_recommendations: List[Tuple[str, float, str]] = field(default_factory=list)  # (agent, confidence, reason)
    error_warnings: List[str] = field(default_factory=list)
    parallel_patterns: List[str] = field(default_factory=list)
    project_specific: List[str] = field(default_factory=list)

    @property
    def has_content(self) -> bool:
        """Check if there's any content to inject."""
        return bool(
            self.tool_insights or
            self.skill_recommendations or
            self.agent_recommendations or
            self.error_warnings or
            self.parallel_patterns or
            self.project_specific
        )

    def total_items(self) -> int:
        """Count total items across all categories."""
        return (
            len(self.tool_insights) +
            len(self.skill_recommendations) +
            len(self.agent_recommendations) +
            len(self.error_warnings) +
            len(self.parallel_patterns) +
            len(self.project_specific)
        )


class ContextInjector:
    """
    Pulls learnings from Mind and formats them for Claude.

    Designed to be fast (< 200ms) and concise (< 1000 chars).
    """

    MAX_CONTEXT_CHARS = 1000
    MAX_ITEMS_PER_CATEGORY = 3

    def __init__(self, mind_client: Optional[MindClient] = None):
        self.mind = mind_client or MindClient(timeout=2.0)

    async def gather_context(self, project_name: Optional[str] = None) -> InjectionContext:
        """
        Gather all relevant context from Mind.

        Args:
            project_name: Optional project name to filter learnings

        Returns:
            InjectionContext with all gathered insights
        """
        context = InjectionContext()

        if not await self.mind.is_available():
            return context

        # Gather in parallel for speed
        tool_task = self._gather_tool_insights(project_name)
        skill_task = self._gather_skill_recommendations(project_name)
        agent_task = self._gather_agent_recommendations(project_name)
        error_task = self._gather_error_warnings(project_name)
        parallel_task = self._gather_parallel_patterns()

        # Await all
        import asyncio
        results = await asyncio.gather(
            tool_task, skill_task, agent_task, error_task, parallel_task,
            return_exceptions=True
        )

        # Unpack results (ignore exceptions)
        if not isinstance(results[0], Exception):
            context.tool_insights = results[0]
        if not isinstance(results[1], Exception):
            context.skill_recommendations = results[1]
        if not isinstance(results[2], Exception):
            context.agent_recommendations = results[2]
        if not isinstance(results[3], Exception):
            context.error_warnings = results[3]
        if not isinstance(results[4], Exception):
            context.parallel_patterns = results[4]

        return context

    async def _gather_tool_insights(self, project_name: Optional[str]) -> List[str]:
        """Gather tool effectiveness insights."""
        query = "TOOL_EFFECTIVENESS LEARNING"
        if project_name:
            query = f"{project_name} {query}"

        learnings = await self.mind.retrieve(
            query=query,
            limit=5,
            temporal_level=TemporalLevel.IDENTITY,
            content_type=ContentType.REFLECTION
        )

        insights = []
        for l in learnings[:self.MAX_ITEMS_PER_CATEGORY]:
            content = l.get("content", "")
            formatted = self._format_tool_insight(content)
            if formatted:
                insights.append(formatted)

        return insights

    async def _gather_skill_recommendations(self, project_name: Optional[str]) -> List[Tuple[str, float, str]]:
        """Gather skill effectiveness data."""
        query = "SKILL_EFFECTIVENESS LEARNING"
        if project_name:
            query = f"{project_name} {query}"

        learnings = await self.mind.retrieve(
            query=query,
            limit=5,
            temporal_level=TemporalLevel.IDENTITY,
            content_type=ContentType.REFLECTION
        )

        recommendations = []
        for l in learnings[:self.MAX_ITEMS_PER_CATEGORY]:
            content = l.get("content", "")
            metadata = l.get("metadata", {})

            skill_id = metadata.get("skill_id")
            success_rate = metadata.get("success_rate", 0)
            best_task = metadata.get("best_task", "general")

            if skill_id and success_rate >= 0.7:
                reason = f"{success_rate:.0%} success for {best_task}"
                recommendations.append((skill_id, success_rate, reason))

        # Sort by success rate
        recommendations.sort(key=lambda x: x[1], reverse=True)
        return recommendations

    async def _gather_agent_recommendations(self, project_name: Optional[str]) -> List[Tuple[str, float, str]]:
        """Gather agent effectiveness data."""
        query = "AGENT_EFFECTIVENESS LEARNING"

        learnings = await self.mind.retrieve(
            query=query,
            limit=5,
            temporal_level=TemporalLevel.IDENTITY,
            content_type=ContentType.REFLECTION
        )

        recommendations = []
        for l in learnings[:self.MAX_ITEMS_PER_CATEGORY]:
            content = l.get("content", "")
            metadata = l.get("metadata", {})

            agent_type = metadata.get("agent_type")
            success_rate = metadata.get("success_rate", 0)
            best_task = metadata.get("best_task", "general")

            if agent_type and success_rate >= 0.6:
                reason = f"{success_rate:.0%} success, best for {best_task}"
                recommendations.append((agent_type, success_rate, reason))

        recommendations.sort(key=lambda x: x[1], reverse=True)
        return recommendations

    async def _gather_error_warnings(self, project_name: Optional[str]) -> List[str]:
        """Gather error avoidance patterns."""
        query = "ERROR_AVOIDANCE LEARNING"
        if project_name:
            query = f"{project_name} {query}"

        learnings = await self.mind.retrieve(
            query=query,
            limit=4,
            temporal_level=TemporalLevel.IDENTITY,
            content_type=ContentType.REFLECTION
        )

        warnings = []
        for l in learnings[:self.MAX_ITEMS_PER_CATEGORY]:
            content = l.get("content", "")
            formatted = self._format_error_warning(content)
            if formatted:
                warnings.append(formatted)

        return warnings

    async def _gather_parallel_patterns(self) -> List[str]:
        """Gather successful parallel execution patterns."""
        learnings = await self.mind.retrieve(
            query="PARALLEL_PATTERN LEARNING",
            limit=3,
            temporal_level=TemporalLevel.SEASONAL,
            content_type=ContentType.REFLECTION
        )

        patterns = []
        for l in learnings[:2]:
            metadata = l.get("metadata", {})
            agents = metadata.get("agents", [])
            success_rate = metadata.get("success_rate", 0)

            if agents and success_rate >= 0.8:
                pattern = f"{' + '.join(agents)} work well together ({success_rate:.0%})"
                patterns.append(pattern)

        return patterns

    def _format_tool_insight(self, content: str) -> Optional[str]:
        """Format a tool effectiveness learning."""
        if "TOOL_EFFECTIVENESS" not in content:
            return None

        try:
            # Extract: "Tool has X% success rate"
            parts = content.split(":")
            if len(parts) >= 2:
                insight = parts[1].strip()
                # First sentence only
                if "." in insight:
                    insight = insight.split(".")[0] + "."
                if len(insight) > 60:
                    insight = insight[:57] + "..."
                return insight
        except Exception:
            pass
        return None

    def _format_error_warning(self, content: str) -> Optional[str]:
        """Format an error avoidance pattern."""
        if "ERROR_AVOIDANCE" not in content:
            return None

        try:
            # Look for actionable advice
            if "To avoid" in content:
                start = content.find("To avoid")
                end = content.find(".", start)
                if end > start:
                    warning = content[start:end + 1]
                    if len(warning) > 70:
                        warning = warning[:67] + "..."
                    return warning

            # Fallback: extract error type
            if "errors with" in content.lower():
                start = content.lower().find("errors with")
                end = content.find(".", start)
                if end > start:
                    return content[start:end + 1]
        except Exception:
            pass
        return None

    def format_for_injection(self, context: InjectionContext) -> Optional[str]:
        """
        Format gathered context into a concise string for Claude.

        Returns None if no meaningful content.
        """
        if not context.has_content:
            return None

        lines = []
        total_chars = 0

        # Header
        header = "⚡ Spark Intelligence:"
        lines.append(header)
        total_chars += len(header)

        # Tool insights (most important)
        if context.tool_insights:
            for insight in context.tool_insights[:2]:
                if total_chars + len(insight) + 4 > self.MAX_CONTEXT_CHARS:
                    break
                line = f"  • {insight}"
                lines.append(line)
                total_chars += len(line) + 1

        # Agent recommendations
        if context.agent_recommendations and total_chars < self.MAX_CONTEXT_CHARS - 100:
            for agent, conf, reason in context.agent_recommendations[:2]:
                text = f"  • {agent}: {reason}"
                if total_chars + len(text) > self.MAX_CONTEXT_CHARS:
                    break
                lines.append(text)
                total_chars += len(text) + 1

        # Parallel patterns
        if context.parallel_patterns and total_chars < self.MAX_CONTEXT_CHARS - 80:
            for pattern in context.parallel_patterns[:1]:
                text = f"  • Parallel: {pattern}"
                if total_chars + len(text) > self.MAX_CONTEXT_CHARS:
                    break
                lines.append(text)
                total_chars += len(text) + 1

        # Error warnings (important)
        if context.error_warnings and total_chars < self.MAX_CONTEXT_CHARS - 100:
            lines.append("  ⚠ Watch for:")
            total_chars += 15
            for warning in context.error_warnings[:2]:
                if total_chars + len(warning) + 6 > self.MAX_CONTEXT_CHARS:
                    break
                line = f"    - {warning}"
                lines.append(line)
                total_chars += len(line) + 1

        # Only return if we have more than just the header
        if len(lines) <= 1:
            return None

        return "\n".join(lines)

    async def get_injection_string(self, project_name: Optional[str] = None) -> Optional[str]:
        """
        One-call method to gather and format context.

        Args:
            project_name: Optional project to filter by

        Returns:
            Formatted string ready to inject, or None
        """
        context = await self.gather_context(project_name)
        return self.format_for_injection(context)

    def get_task_specific_advice(
        self,
        context: InjectionContext,
        task_description: str
    ) -> Optional[str]:
        """
        Get advice specific to a task description.

        This can be called mid-session to get targeted recommendations.
        """
        task_lower = task_description.lower()
        advice_parts = []

        # Match agents to task
        if context.agent_recommendations:
            for agent, conf, reason in context.agent_recommendations:
                agent_lower = agent.lower()

                # Match Explore to search tasks
                if agent_lower == "explore" and any(x in task_lower for x in ["find", "search", "where", "look"]):
                    advice_parts.append(f"Consider using {agent} agent ({reason})")
                    break

                # Match Plan to implementation tasks
                if agent_lower == "plan" and any(x in task_lower for x in ["implement", "build", "create", "design"]):
                    advice_parts.append(f"Consider using {agent} agent ({reason})")
                    break

        # Match error warnings
        if context.error_warnings:
            for warning in context.error_warnings:
                warning_lower = warning.lower()
                # If warning mentions something in the task
                if any(word in warning_lower for word in task_lower.split() if len(word) > 4):
                    advice_parts.append(warning)
                    break

        if advice_parts:
            return " | ".join(advice_parts)
        return None

    async def close(self):
        """Close the Mind client."""
        await self.mind.close()
