"""
Spark Agent Orchestrator: Learn which agents work best for which tasks.

The orchestrator:
1. Tracks when agents (Task tool) are used and outcomes
2. Learns agent effectiveness by task type
3. Recommends best agent for a given task
4. Learns parallelization patterns (when to use multiple agents)

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
class AgentUsage:
    """A single agent usage record."""
    agent_type: str  # e.g., "Explore", "Plan", "general-purpose"
    task_description: str  # What was the agent asked to do
    outcome: str  # success, failure, partial
    duration_ms: Optional[float] = None
    error: Optional[str] = None
    session_id: Optional[str] = None
    parallel_with: Optional[List[str]] = None  # Other agents run in parallel
    timestamp: float = field(default_factory=lambda: datetime.now().timestamp())


@dataclass
class AgentStats:
    """Aggregated statistics for an agent type."""
    agent_type: str
    total_uses: int = 0
    successes: int = 0
    failures: int = 0
    total_duration_ms: float = 0.0
    task_categories: Dict[str, int] = field(default_factory=dict)  # category -> count
    task_success_rates: Dict[str, Tuple[int, int]] = field(default_factory=dict)  # category -> (success, total)
    error_types: Dict[str, int] = field(default_factory=dict)
    parallel_runs: int = 0  # Times run in parallel with others

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
    def best_task_category(self) -> Optional[str]:
        """Task category with highest success rate (min 3 samples)."""
        best = None
        best_rate = 0.0

        for category, (success, total) in self.task_success_rates.items():
            if total >= 3:
                rate = success / total
                if rate > best_rate:
                    best = category
                    best_rate = rate

        return best


@dataclass
class ParallelPattern:
    """A pattern of agents that work well together in parallel."""
    agent_types: Tuple[str, ...]  # e.g., ("Explore", "Explore")
    task_context: str
    success_rate: float
    sample_count: int
    avg_speedup: float = 1.0  # Estimated speedup vs sequential


@dataclass
class AgentRecommendation:
    """A recommendation for which agent to use."""
    agent_type: str
    confidence: float
    reasoning: str
    alternatives: List[Tuple[str, float]]  # (agent_type, confidence)


class AgentOrchestrator:
    """
    Learns and recommends agent usage patterns.

    Tracks which agents work best for which tasks and when
    to parallelize agent work.
    """

    def __init__(self, mind_client: Optional[MindClient] = None):
        self.mind = mind_client or MindClient()
        self.agent_stats: Dict[str, AgentStats] = defaultdict(
            lambda: AgentStats(agent_type="unknown")
        )
        self.usage_history: List[AgentUsage] = []
        self.parallel_patterns: List[ParallelPattern] = []
        self.session_agents: Dict[str, List[AgentUsage]] = defaultdict(list)  # session -> usages

    async def load_existing_data(self):
        """Load existing agent effectiveness data from Mind."""
        learnings = await self.mind.retrieve(
            query="AGENT_EFFECTIVENESS",
            limit=50,
            temporal_level=TemporalLevel.IDENTITY,
            content_type=ContentType.REFLECTION
        )

        for learning in learnings:
            content = learning.get("content", "")
            if "agent=" in content:
                self._parse_agent_learning(content)

    def _parse_agent_learning(self, content: str):
        """Parse an agent learning from Mind into stats."""
        try:
            if "agent=" not in content:
                return

            # Extract agent_type
            agent_part = content.split("agent=")[1]
            agent_type = agent_part.split()[0].strip(".,")

            # Initialize stats
            if agent_type not in self.agent_stats:
                self.agent_stats[agent_type] = AgentStats(agent_type=agent_type)
        except Exception:
            pass

    def track_agent_usage(self, event: SparkEvent) -> Optional[AgentUsage]:
        """
        Track an agent usage event.

        Called when we detect a Task tool invocation.
        """
        tool_input = event.tool_input or {}
        data = event.data or {}

        # Extract agent info
        agent_type = tool_input.get("subagent_type") or data.get("agent_type", "general-purpose")
        prompt = tool_input.get("prompt", "")[:200] if tool_input.get("prompt") else ""

        # Determine outcome
        if event.event_type == EventType.POST_TOOL:
            outcome = "success"
        elif event.event_type == EventType.POST_TOOL_FAILURE:
            outcome = "failure"
        else:
            outcome = "unknown"

        # Infer task category from prompt
        task_category = self._infer_task_category(prompt, agent_type)

        usage = AgentUsage(
            agent_type=agent_type,
            task_description=prompt,
            outcome=outcome,
            duration_ms=event.duration_ms,
            error=event.error,
            session_id=event.session_id,
            timestamp=event.timestamp
        )

        self.usage_history.append(usage)
        self.session_agents[event.session_id].append(usage)
        self._update_agent_stats(usage, task_category)

        # Check for parallel execution
        self._detect_parallel_execution(usage)

        return usage

    def _infer_task_category(self, prompt: str, agent_type: str) -> str:
        """Infer task category from prompt and agent type."""
        prompt_lower = prompt.lower()

        # Check for specific keywords
        if any(x in prompt_lower for x in ["search", "find", "look for", "where"]):
            return "search"
        elif any(x in prompt_lower for x in ["test", "spec", "verify"]):
            return "testing"
        elif any(x in prompt_lower for x in ["fix", "bug", "error", "issue"]):
            return "debugging"
        elif any(x in prompt_lower for x in ["implement", "create", "build", "add"]):
            return "implementation"
        elif any(x in prompt_lower for x in ["refactor", "clean", "improve"]):
            return "refactoring"
        elif any(x in prompt_lower for x in ["document", "explain", "understand"]):
            return "documentation"
        elif any(x in prompt_lower for x in ["review", "check", "audit"]):
            return "review"

        # Default based on agent type
        agent_defaults = {
            "Explore": "search",
            "Plan": "planning",
            "general-purpose": "general",
            "code-reviewer": "review",
        }
        return agent_defaults.get(agent_type, "general")

    def _update_agent_stats(self, usage: AgentUsage, task_category: str):
        """Update aggregated stats for an agent."""
        stats = self.agent_stats[usage.agent_type]
        stats.agent_type = usage.agent_type
        stats.total_uses += 1

        if usage.outcome == "success":
            stats.successes += 1
        elif usage.outcome == "failure":
            stats.failures += 1
            if usage.error:
                error_type = self._categorize_error(usage.error)
                stats.error_types[error_type] = stats.error_types.get(error_type, 0) + 1

        if usage.duration_ms:
            stats.total_duration_ms += usage.duration_ms

        # Track task category success
        stats.task_categories[task_category] = stats.task_categories.get(task_category, 0) + 1

        if task_category not in stats.task_success_rates:
            stats.task_success_rates[task_category] = (0, 0)

        success, total = stats.task_success_rates[task_category]
        if usage.outcome == "success":
            stats.task_success_rates[task_category] = (success + 1, total + 1)
        else:
            stats.task_success_rates[task_category] = (success, total + 1)

    def _categorize_error(self, error: str) -> str:
        """Categorize an error into a type."""
        error_lower = error.lower()

        if "timeout" in error_lower:
            return "timeout"
        elif "not found" in error_lower:
            return "not_found"
        elif "permission" in error_lower:
            return "permission"
        elif "context" in error_lower or "token" in error_lower:
            return "context_limit"
        else:
            return "other"

    def _detect_parallel_execution(self, usage: AgentUsage):
        """Detect if this agent was run in parallel with others."""
        session_usages = self.session_agents.get(usage.session_id, [])

        if len(session_usages) < 2:
            return

        # Check for agents started within 1 second of each other
        recent_parallel = []
        for other in session_usages[:-1]:  # Exclude current
            time_diff = abs(usage.timestamp - other.timestamp)
            if time_diff < 1.0:  # Within 1 second
                recent_parallel.append(other.agent_type)

        if recent_parallel:
            usage.parallel_with = recent_parallel
            self.agent_stats[usage.agent_type].parallel_runs += 1

    async def process_events(self, events: List[SparkEvent]) -> List[AgentUsage]:
        """Process a batch of events and extract agent usages."""
        usages = []

        for event in events:
            # Check if this is a Task tool invocation
            if event.tool_name == "Task":
                usage = self.track_agent_usage(event)
                if usage:
                    usages.append(usage)

        return usages

    def get_recommendation(self, task_description: str) -> AgentRecommendation:
        """
        Get agent recommendation for a task.

        Returns the best agent type and alternatives.
        """
        task_category = self._infer_task_category(task_description, "")

        # Score each agent for this task
        scores: List[Tuple[str, float, str]] = []

        for agent_type, stats in self.agent_stats.items():
            if stats.total_uses < 3:
                continue

            # Base score is overall success rate
            score = stats.success_rate

            # Boost if this agent is good at this task category
            if task_category in stats.task_success_rates:
                cat_success, cat_total = stats.task_success_rates[task_category]
                if cat_total >= 2:
                    category_rate = cat_success / cat_total
                    score = (score + category_rate * 2) / 3  # Weight category performance

            reasoning = f"{stats.success_rate:.0%} overall"
            if task_category in stats.task_success_rates:
                cat_success, cat_total = stats.task_success_rates[task_category]
                if cat_total >= 2:
                    reasoning += f", {cat_success/cat_total:.0%} for {task_category}"

            scores.append((agent_type, score, reasoning))

        if not scores:
            return AgentRecommendation(
                agent_type="general-purpose",
                confidence=0.5,
                reasoning="No data available, using default",
                alternatives=[]
            )

        # Sort by score
        scores.sort(key=lambda x: x[1], reverse=True)

        best = scores[0]
        alternatives = [(t, s) for t, s, _ in scores[1:3]]

        return AgentRecommendation(
            agent_type=best[0],
            confidence=best[1],
            reasoning=best[2],
            alternatives=alternatives
        )

    def identify_parallel_patterns(self, min_samples: int = 3) -> List[ParallelPattern]:
        """Identify patterns where parallel agent execution works well."""
        # Group parallel runs by agent combination
        parallel_combos: Dict[Tuple[str, ...], List[bool]] = defaultdict(list)

        for usage in self.usage_history:
            if usage.parallel_with:
                combo = tuple(sorted([usage.agent_type] + usage.parallel_with))
                parallel_combos[combo].append(usage.outcome == "success")

        # Find successful patterns
        patterns = []
        for combo, outcomes in parallel_combos.items():
            if len(outcomes) >= min_samples:
                success_rate = sum(outcomes) / len(outcomes)
                if success_rate >= 0.7:
                    pattern = ParallelPattern(
                        agent_types=combo,
                        task_context="various",  # Could be refined
                        success_rate=success_rate,
                        sample_count=len(outcomes)
                    )
                    patterns.append(pattern)

        patterns.sort(key=lambda p: (p.success_rate, p.sample_count), reverse=True)
        self.parallel_patterns = patterns

        return patterns

    async def store_learnings_in_mind(self) -> int:
        """Store agent effectiveness learnings in Mind."""
        memories = []

        # Store agent effectiveness patterns
        for agent_type, stats in self.agent_stats.items():
            if stats.total_uses >= 5:
                confidence = min(stats.total_uses / 20, 1.0)

                if confidence >= 0.5:
                    best_task = stats.best_task_category
                    content = (
                        f"LEARNING [AGENT_EFFECTIVENESS]: {agent_type} has {stats.success_rate:.0%} success rate. "
                        f"Conditions: agent={agent_type}, samples={stats.total_uses}. "
                        f"Best for: {best_task or 'general tasks'}. "
                        f"Confidence: {confidence:.0%}"
                    )

                    memory = Memory(
                        content=content,
                        temporal_level=TemporalLevel.IDENTITY,
                        salience=confidence,
                        content_type=ContentType.REFLECTION,
                        metadata={
                            "pattern_type": "agent_effectiveness",
                            "agent_type": agent_type,
                            "success_rate": stats.success_rate,
                            "total_uses": stats.total_uses,
                            "best_task": best_task
                        }
                    )
                    memories.append(memory)

        # Store parallel execution patterns
        for pattern in self.parallel_patterns[:3]:
            if pattern.sample_count >= 5:
                content = (
                    f"LEARNING [PARALLEL_PATTERN]: Agents {pattern.agent_types} work well together. "
                    f"Success rate: {pattern.success_rate:.0%} over {pattern.sample_count} runs."
                )

                memory = Memory(
                    content=content,
                    temporal_level=TemporalLevel.SEASONAL,
                    salience=pattern.success_rate,
                    content_type=ContentType.REFLECTION,
                    metadata={
                        "pattern_type": "parallel_pattern",
                        "agents": list(pattern.agent_types),
                        "success_rate": pattern.success_rate
                    }
                )
                memories.append(memory)

        if memories:
            return await self.mind.store_batch(memories)
        return 0

    def get_agent_ranking(self) -> List[Tuple[str, float, int]]:
        """Get agents ranked by effectiveness."""
        rankings = []

        for agent_type, stats in self.agent_stats.items():
            if stats.total_uses >= 3:
                rankings.append((agent_type, stats.success_rate, stats.total_uses))

        rankings.sort(key=lambda x: (x[1], x[2]), reverse=True)
        return rankings

    def get_best_agent_for_task(self, task_category: str) -> Optional[str]:
        """Get the best agent for a specific task category."""
        best = None
        best_rate = 0.0

        for agent_type, stats in self.agent_stats.items():
            if task_category in stats.task_success_rates:
                success, total = stats.task_success_rates[task_category]
                if total >= 3:
                    rate = success / total
                    if rate > best_rate:
                        best = agent_type
                        best_rate = rate

        return best

    def clear_session_data(self):
        """Clear session-specific data."""
        self.usage_history = []
        self.session_agents.clear()
