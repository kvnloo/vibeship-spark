"""
Spark Suggester: Proactive insight surfacing.

The Suggester doesn't wait to be asked - it anticipates needs and surfaces
relevant insights proactively. This is the "intelligent assistant" layer.

Capabilities:
1. Detect when current task matches past failure patterns → warn
2. Suggest proven approaches before they're requested
3. Surface relevant learnings based on context
4. Alert on potential issues before they occur
5. Recommend tools/skills/agents based on task

This makes Spark truly proactive rather than reactive.
"""

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple, Set
from datetime import datetime
import re

from .mind_client import MindClient, TemporalLevel, ContentType


@dataclass
class Suggestion:
    """A proactive suggestion to surface."""
    suggestion_id: str
    suggestion_type: str  # warning, recommendation, insight, tip
    priority: int  # 1 = critical, 2 = important, 3 = helpful, 4 = optional
    title: str
    description: str
    confidence: float

    # Context matching
    trigger_keywords: List[str] = field(default_factory=list)
    trigger_task_type: Optional[str] = None
    trigger_tool: Optional[str] = None

    # Evidence
    evidence: List[str] = field(default_factory=list)
    based_on_samples: int = 0

    # Tracking
    times_shown: int = 0
    times_helpful: int = 0
    times_dismissed: int = 0

    @property
    def helpfulness_rate(self) -> float:
        total = self.times_helpful + self.times_dismissed
        if total == 0:
            return 0.5
        return self.times_helpful / total

    @property
    def should_still_show(self) -> bool:
        """Determine if this suggestion should still be shown."""
        # Don't show if consistently dismissed
        if self.times_dismissed >= 5 and self.helpfulness_rate < 0.2:
            return False
        return True


@dataclass
class SuggestionContext:
    """Context for generating suggestions."""
    task_description: Optional[str] = None
    current_tool: Optional[str] = None
    recent_tools: List[str] = field(default_factory=list)
    recent_errors: List[str] = field(default_factory=list)
    project_name: Optional[str] = None
    session_id: Optional[str] = None
    keywords: Set[str] = field(default_factory=set)


class Suggester:
    """
    Proactively surfaces relevant insights and warnings.

    The Suggester monitors context and pattern-matches against
    accumulated learnings to provide timely, relevant suggestions.
    """

    def __init__(self, mind_client: Optional[MindClient] = None):
        self.mind = mind_client or MindClient()

        # Registered suggestions (patterns to match)
        self.suggestions: Dict[str, Suggestion] = {}

        # Recent context for matching
        self.current_context: SuggestionContext = SuggestionContext()

        # Shown suggestions this session (avoid repetition)
        self.shown_this_session: Set[str] = set()

        # Statistics
        self.total_suggestions_shown: int = 0
        self.suggestions_by_type: Dict[str, int] = defaultdict(int)

    async def load_suggestions_from_mind(self):
        """Load learned patterns as potential suggestions."""
        # Load error avoidance patterns
        error_patterns = await self.mind.retrieve(
            query="ERROR_AVOIDANCE LEARNING",
            limit=20,
            temporal_level=TemporalLevel.IDENTITY,
            content_type=ContentType.REFLECTION
        )

        for pattern in error_patterns:
            content = pattern.get("content", "")
            metadata = pattern.get("metadata", {})

            suggestion = self._create_warning_from_error_pattern(content, metadata)
            if suggestion:
                self.suggestions[suggestion.suggestion_id] = suggestion

        # Load tool effectiveness patterns
        tool_patterns = await self.mind.retrieve(
            query="TOOL_EFFECTIVENESS LEARNING",
            limit=20,
            temporal_level=TemporalLevel.IDENTITY,
            content_type=ContentType.REFLECTION
        )

        for pattern in tool_patterns:
            content = pattern.get("content", "")
            metadata = pattern.get("metadata", {})

            suggestion = self._create_recommendation_from_tool_pattern(content, metadata)
            if suggestion:
                self.suggestions[suggestion.suggestion_id] = suggestion

        # Load agent effectiveness patterns
        agent_patterns = await self.mind.retrieve(
            query="AGENT_EFFECTIVENESS LEARNING",
            limit=10,
            temporal_level=TemporalLevel.IDENTITY,
            content_type=ContentType.REFLECTION
        )

        for pattern in agent_patterns:
            content = pattern.get("content", "")
            metadata = pattern.get("metadata", {})

            suggestion = self._create_agent_recommendation(content, metadata)
            if suggestion:
                self.suggestions[suggestion.suggestion_id] = suggestion

        # Load recovery strategy patterns (when X fails, try Y)
        recovery_patterns = await self.mind.retrieve(
            query="RECOVERY_STRATEGY LEARNING",
            limit=20,
            temporal_level=TemporalLevel.IDENTITY,
            content_type=ContentType.REFLECTION
        )

        for pattern in recovery_patterns:
            content = pattern.get("content", "")
            metadata = pattern.get("metadata", {})

            suggestion = self._create_recovery_suggestion(content, metadata)
            if suggestion:
                self.suggestions[suggestion.suggestion_id] = suggestion

    def _create_warning_from_error_pattern(
        self,
        content: str,
        metadata: Dict[str, Any]
    ) -> Optional[Suggestion]:
        """Create a warning suggestion from an error avoidance pattern."""
        if "ERROR_AVOIDANCE" not in content:
            return None

        error_type = metadata.get("error_type", "unknown")
        tool = metadata.get("tool")
        confidence = metadata.get("confidence", 0.5)

        # Extract the avoidance tip
        tip = ""
        if "To avoid" in content:
            start = content.find("To avoid")
            end = content.find(".", start)
            if end > start:
                tip = content[start:end + 1]

        if not tip:
            return None

        # Extract trigger keywords from error type
        keywords = self._extract_keywords(error_type)

        suggestion_id = f"warn:{error_type}:{tool or 'any'}"

        return Suggestion(
            suggestion_id=suggestion_id,
            suggestion_type="warning",
            priority=2,
            title=f"Watch out: {error_type}",
            description=tip,
            confidence=confidence,
            trigger_keywords=keywords,
            trigger_tool=tool,
            evidence=[f"Based on past {error_type} errors"],
            based_on_samples=metadata.get("occurrences", 1)
        )

    def _create_recommendation_from_tool_pattern(
        self,
        content: str,
        metadata: Dict[str, Any]
    ) -> Optional[Suggestion]:
        """Create a tool recommendation from effectiveness pattern."""
        if "TOOL_EFFECTIVENESS" not in content:
            return None

        tool = metadata.get("tool")
        success_rate = metadata.get("success_rate", 0)
        best_for = metadata.get("best_for")

        if not tool or success_rate < 0.7:
            return None

        suggestion_id = f"recommend:tool:{tool}"

        keywords = []
        if best_for:
            keywords = self._extract_keywords(best_for)

        return Suggestion(
            suggestion_id=suggestion_id,
            suggestion_type="recommendation",
            priority=3,
            title=f"Consider using {tool}",
            description=f"{tool} has {success_rate:.0%} success rate{f' for {best_for}' if best_for else ''}",
            confidence=success_rate,
            trigger_keywords=keywords,
            trigger_tool=None,
            trigger_task_type=best_for,
            evidence=[f"{success_rate:.0%} success rate"],
            based_on_samples=metadata.get("total_uses", 1)
        )

    def _create_agent_recommendation(
        self,
        content: str,
        metadata: Dict[str, Any]
    ) -> Optional[Suggestion]:
        """Create an agent recommendation from effectiveness pattern."""
        if "AGENT_EFFECTIVENESS" not in content:
            return None

        agent_type = metadata.get("agent_type")
        success_rate = metadata.get("success_rate", 0)
        best_task = metadata.get("best_task")

        if not agent_type or success_rate < 0.6:
            return None

        suggestion_id = f"recommend:agent:{agent_type}"

        keywords = []
        task_type = None
        if best_task:
            keywords = self._extract_keywords(best_task)
            task_type = best_task

        return Suggestion(
            suggestion_id=suggestion_id,
            suggestion_type="recommendation",
            priority=3,
            title=f"Try {agent_type} agent",
            description=f"{agent_type} agent excels at {best_task or 'this type of task'} ({success_rate:.0%} success)",
            confidence=success_rate,
            trigger_keywords=keywords,
            trigger_task_type=task_type,
            evidence=[f"{success_rate:.0%} success for {best_task or 'similar tasks'}"],
            based_on_samples=metadata.get("total_uses", 1)
        )

    def _create_recovery_suggestion(
        self,
        content: str,
        metadata: Dict[str, Any]
    ) -> Optional[Suggestion]:
        """Create a recovery suggestion from recovery strategy pattern."""
        if "RECOVERY_STRATEGY" not in content:
            return None

        failed_tool = metadata.get("failed_tool")
        failed_error = metadata.get("failed_error")
        recovery_tool = metadata.get("recovery_tool")
        occurrences = metadata.get("occurrences", 1)

        if not failed_tool or not recovery_tool:
            return None

        suggestion_id = f"recovery:{failed_tool}:{failed_error}:{recovery_tool}"

        # Build descriptive message
        if failed_error:
            description = f"When {failed_tool} fails with {failed_error}, try {recovery_tool} instead"
        else:
            description = f"When {failed_tool} fails, try {recovery_tool} instead"

        if occurrences > 1:
            description += f" (worked {occurrences} times)"

        return Suggestion(
            suggestion_id=suggestion_id,
            suggestion_type="recovery",
            priority=1,  # High priority - immediate actionable advice
            title=f"Recovery: Try {recovery_tool}",
            description=description,
            confidence=min(occurrences / 5, 1.0),
            trigger_keywords=[failed_error] if failed_error else [],
            trigger_tool=failed_tool,  # Trigger when this tool is about to be used
            evidence=[f"Recovered from {failed_tool} failure {occurrences} times"],
            based_on_samples=occurrences
        )

    def _extract_keywords(self, text: str) -> List[str]:
        """Extract searchable keywords from text."""
        if not text:
            return []

        # Common task-related keywords
        task_keywords = {
            "search": ["search", "find", "look", "where", "locate"],
            "edit": ["edit", "modify", "change", "update", "fix"],
            "read": ["read", "view", "show", "display", "get"],
            "write": ["write", "create", "new", "add", "make"],
            "test": ["test", "verify", "check", "validate"],
            "debug": ["debug", "error", "bug", "fix", "issue"],
            "git": ["git", "commit", "push", "pull", "branch"],
            "install": ["install", "setup", "configure", "npm", "pip"]
        }

        text_lower = text.lower()
        keywords = []

        for category, words in task_keywords.items():
            if any(w in text_lower for w in words):
                keywords.extend(words[:3])  # Add top 3 related words

        # Also add words from the text itself
        words = re.findall(r'\b[a-z]{4,}\b', text_lower)
        keywords.extend(words[:5])

        return list(set(keywords))

    def update_context(
        self,
        task_description: Optional[str] = None,
        current_tool: Optional[str] = None,
        recent_error: Optional[str] = None,
        project_name: Optional[str] = None,
        session_id: Optional[str] = None
    ):
        """Update the current context for suggestion matching."""
        if task_description:
            self.current_context.task_description = task_description
            self.current_context.keywords = set(self._extract_keywords(task_description))

        if current_tool:
            self.current_context.current_tool = current_tool
            if current_tool not in self.current_context.recent_tools:
                self.current_context.recent_tools.append(current_tool)
                # Keep only last 10
                self.current_context.recent_tools = self.current_context.recent_tools[-10:]

        if recent_error:
            self.current_context.recent_errors.append(recent_error)
            self.current_context.recent_errors = self.current_context.recent_errors[-5:]

        if project_name:
            self.current_context.project_name = project_name

        if session_id:
            if session_id != self.current_context.session_id:
                # New session - reset shown suggestions
                self.shown_this_session.clear()
            self.current_context.session_id = session_id

    def get_relevant_suggestions(
        self,
        max_suggestions: int = 3,
        min_confidence: float = 0.5
    ) -> List[Suggestion]:
        """
        Get suggestions relevant to the current context.

        Returns suggestions sorted by relevance and priority.
        """
        relevant = []

        for suggestion in self.suggestions.values():
            # Skip if already shown this session
            if suggestion.suggestion_id in self.shown_this_session:
                continue

            # Skip if shouldn't show anymore
            if not suggestion.should_still_show:
                continue

            # Skip low confidence
            if suggestion.confidence < min_confidence:
                continue

            # Calculate relevance score
            relevance = self._calculate_relevance(suggestion)

            if relevance > 0:
                relevant.append((suggestion, relevance))

        # Sort by relevance * priority weight
        priority_weights = {1: 4, 2: 3, 3: 2, 4: 1}
        relevant.sort(
            key=lambda x: x[1] * priority_weights.get(x[0].priority, 1),
            reverse=True
        )

        # Return top suggestions
        result = [s for s, _ in relevant[:max_suggestions]]

        # Mark as shown
        for s in result:
            self.shown_this_session.add(s.suggestion_id)
            s.times_shown += 1
            self.total_suggestions_shown += 1
            self.suggestions_by_type[s.suggestion_type] += 1

        return result

    def _calculate_relevance(self, suggestion: Suggestion) -> float:
        """Calculate how relevant a suggestion is to current context."""
        relevance = 0.0

        # Keyword matching
        if self.current_context.keywords and suggestion.trigger_keywords:
            matches = len(
                self.current_context.keywords.intersection(set(suggestion.trigger_keywords))
            )
            if matches > 0:
                relevance += min(matches * 0.3, 0.9)

        # Tool matching
        if suggestion.trigger_tool:
            if suggestion.trigger_tool == self.current_context.current_tool:
                relevance += 0.5
            elif suggestion.trigger_tool in self.current_context.recent_tools:
                relevance += 0.3

        # Task type matching
        if suggestion.trigger_task_type and self.current_context.task_description:
            task_keywords = self._extract_keywords(self.current_context.task_description)
            type_keywords = self._extract_keywords(suggestion.trigger_task_type)
            if set(task_keywords).intersection(set(type_keywords)):
                relevance += 0.4

        # Warnings get boost if we have recent errors
        if suggestion.suggestion_type == "warning" and self.current_context.recent_errors:
            relevance += 0.2

        # Boost by confidence
        relevance *= (0.5 + suggestion.confidence * 0.5)

        # Boost by helpfulness history
        relevance *= (0.5 + suggestion.helpfulness_rate * 0.5)

        return relevance

    def mark_suggestion_helpful(self, suggestion_id: str, was_helpful: bool):
        """Mark whether a shown suggestion was helpful."""
        if suggestion_id in self.suggestions:
            if was_helpful:
                self.suggestions[suggestion_id].times_helpful += 1
            else:
                self.suggestions[suggestion_id].times_dismissed += 1

    def register_custom_suggestion(self, suggestion: Suggestion):
        """Register a custom suggestion."""
        self.suggestions[suggestion.suggestion_id] = suggestion

    def get_warnings_for_tool(self, tool_name: str) -> List[Suggestion]:
        """Get all warnings relevant to a specific tool."""
        warnings = []

        for suggestion in self.suggestions.values():
            if suggestion.suggestion_type != "warning":
                continue
            if suggestion.trigger_tool == tool_name or not suggestion.trigger_tool:
                if suggestion.should_still_show:
                    warnings.append(suggestion)

        return sorted(warnings, key=lambda s: s.priority)

    def get_recommendations_for_task(self, task_description: str) -> List[Suggestion]:
        """Get recommendations for a specific task."""
        # Temporarily update context
        old_context = self.current_context
        self.current_context = SuggestionContext(
            task_description=task_description,
            keywords=set(self._extract_keywords(task_description))
        )

        # Get recommendations only
        relevant = []
        for suggestion in self.suggestions.values():
            if suggestion.suggestion_type != "recommendation":
                continue

            relevance = self._calculate_relevance(suggestion)
            if relevance > 0.3:
                relevant.append((suggestion, relevance))

        relevant.sort(key=lambda x: x[1], reverse=True)

        # Restore context
        self.current_context = old_context

        return [s for s, _ in relevant[:5]]

    def get_recovery_suggestions(
        self,
        failed_tool: str,
        error_category: Optional[str] = None
    ) -> List[Suggestion]:
        """
        Get recovery suggestions when a tool fails.

        This is the key method for resilience learning - when something fails,
        suggest what to try next based on past successful recoveries.
        """
        recoveries = []

        for suggestion in self.suggestions.values():
            if suggestion.suggestion_type != "recovery":
                continue

            if not suggestion.should_still_show:
                continue

            # Must match the failed tool
            if suggestion.trigger_tool != failed_tool:
                continue

            # Optionally match error category
            if error_category and suggestion.trigger_keywords:
                if error_category not in suggestion.trigger_keywords:
                    # Lower priority if error doesn't match
                    # but still include as general recovery
                    recoveries.append((suggestion, suggestion.confidence * 0.5))
                else:
                    recoveries.append((suggestion, suggestion.confidence))
            else:
                recoveries.append((suggestion, suggestion.confidence))

        # Sort by confidence
        recoveries.sort(key=lambda x: x[1], reverse=True)

        # Return suggestions (not marking as shown - these are situational)
        return [s for s, _ in recoveries[:3]]

    def format_recovery_advice(
        self,
        failed_tool: str,
        error_category: Optional[str] = None
    ) -> Optional[str]:
        """
        Format recovery advice for display after a failure.

        Returns None if no recovery suggestions available.
        """
        recoveries = self.get_recovery_suggestions(failed_tool, error_category)

        if not recoveries:
            return None

        lines = ["[SPARK RECOVERY] Suggestions based on past recoveries:"]
        for r in recoveries:
            lines.append(f"  -> {r.description}")

        return "\n".join(lines)

    def format_suggestions_for_display(
        self,
        suggestions: List[Suggestion],
        compact: bool = True
    ) -> str:
        """Format suggestions for display to user."""
        if not suggestions:
            return ""

        lines = []

        if compact:
            for s in suggestions:
                icon = {"warning": "⚠", "recommendation": "→", "insight": "💡", "tip": "•"}.get(
                    s.suggestion_type, "•"
                )
                lines.append(f"{icon} {s.title}: {s.description}")
        else:
            for s in suggestions:
                icon = {"warning": "⚠️", "recommendation": "✨", "insight": "💡", "tip": "📝"}.get(
                    s.suggestion_type, "📌"
                )
                lines.append(f"{icon} **{s.title}**")
                lines.append(f"   {s.description}")
                if s.evidence:
                    lines.append(f"   _Evidence: {'; '.join(s.evidence)}_")
                lines.append("")

        return "\n".join(lines)

    def get_stats(self) -> Dict[str, Any]:
        """Get suggester statistics."""
        return {
            "total_suggestions": len(self.suggestions),
            "total_shown": self.total_suggestions_shown,
            "by_type": dict(self.suggestions_by_type),
            "shown_this_session": len(self.shown_this_session),
            "avg_helpfulness": (
                sum(s.helpfulness_rate for s in self.suggestions.values()) / len(self.suggestions)
                if self.suggestions else 0
            )
        }

    def clear_session(self):
        """Clear session-specific data."""
        self.shown_this_session.clear()
        self.current_context = SuggestionContext()
