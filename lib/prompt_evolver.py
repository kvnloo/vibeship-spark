"""
Spark Prompt Evolver: GEPA-inspired reflective prompt evolution.

Based on research from Berkeley/Stanford (2025):
- GEPA: Reflective Prompt Evolution Can Outperform Reinforcement Learning
- DSPy optimization framework
- Reflexion: Language Agents with Verbal Reinforcement Learning

Key principles:
1. Capture execution traces (reasoning, tool calls, outputs, errors)
2. Reflect on trajectories: what worked, what didn't, why
3. Propose prompt mutations based on textual feedback
4. Maintain Pareto frontier of high-performing patterns
5. Store evolved patterns in Mind for persistence

This is NOT gradient-based optimization. It's reflection-based evolution.
"""

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime
import hashlib

from .queue import SparkEvent, EventType
from .mind_client import MindClient, Memory, ContentType, TemporalLevel


@dataclass
class ExecutionTrace:
    """A single execution trace capturing the full chain."""
    trace_id: str
    session_id: str
    timestamp: float

    # What was attempted
    task_description: str
    tool_sequence: List[str]  # Ordered list of tools used

    # What happened
    outcome: str  # success, failure, partial
    duration_ms: float
    error: Optional[str] = None
    error_category: Optional[str] = None

    # Context
    project: Optional[str] = None
    task_category: Optional[str] = None

    # Reflection data (filled in during reflection phase)
    what_worked: List[str] = field(default_factory=list)
    what_failed: List[str] = field(default_factory=list)
    improvement_suggestions: List[str] = field(default_factory=list)


@dataclass
class PromptPattern:
    """A pattern extracted from successful executions."""
    pattern_id: str
    pattern_type: str  # tool_sequence, error_recovery, task_approach
    description: str

    # When to apply
    trigger_conditions: Dict[str, Any]  # task_category, keywords, etc.

    # The pattern itself
    approach: str  # Natural language description of the approach
    tool_sequence: Optional[List[str]] = None

    # Performance metrics
    success_count: int = 0
    failure_count: int = 0
    total_uses: int = 0
    avg_duration_ms: float = 0.0

    # Evolution metadata
    generation: int = 0  # How many times this has been evolved
    parent_id: Optional[str] = None
    created_at: float = field(default_factory=lambda: datetime.now().timestamp())

    @property
    def success_rate(self) -> float:
        if self.total_uses == 0:
            return 0.0
        return self.success_count / self.total_uses

    @property
    def fitness_score(self) -> float:
        """Combined fitness considering success rate and sample size."""
        if self.total_uses < 3:
            return 0.0
        # Wilson score lower bound for confidence
        n = self.total_uses
        p = self.success_rate
        z = 1.96  # 95% confidence
        denominator = 1 + z*z/n
        centre_adjusted_probability = p + z*z/(2*n)
        adjusted_standard_deviation = (p*(1-p) + z*z/(4*n)) / n
        lower_bound = (centre_adjusted_probability - z * adjusted_standard_deviation**0.5) / denominator
        return max(0.0, lower_bound)


@dataclass
class ReflectionResult:
    """Result of reflecting on a set of traces."""
    traces_analyzed: int
    patterns_identified: List[PromptPattern]
    improvements_proposed: List[Dict[str, Any]]
    insights: List[str]


class PromptEvolver:
    """
    Evolves prompt patterns through reflection on execution traces.

    Inspired by GEPA (Genetic-Pareto) algorithm:
    1. Collect execution traces from events
    2. Reflect on trajectories to identify what worked/failed
    3. Propose mutations based on reflection
    4. Maintain Pareto frontier of patterns
    5. Store learnings in Mind
    """

    def __init__(self, mind_client: Optional[MindClient] = None):
        self.mind = mind_client or MindClient()

        # Execution traces (short-term memory)
        self.traces: List[ExecutionTrace] = []
        self.session_traces: Dict[str, List[ExecutionTrace]] = defaultdict(list)

        # Prompt patterns (Pareto frontier)
        self.patterns: Dict[str, PromptPattern] = {}
        self.pareto_frontier: List[str] = []  # Pattern IDs on the frontier

        # Reflection history
        self.reflections: List[ReflectionResult] = []

        # Statistics
        self.total_traces: int = 0
        self.total_reflections: int = 0
        self.patterns_evolved: int = 0

    async def load_existing_data(self):
        """Load existing patterns from Mind."""
        learnings = await self.mind.retrieve(
            query="PROMPT_PATTERN LEARNING",
            limit=50,
            temporal_level=TemporalLevel.IDENTITY,
            content_type=ContentType.REFLECTION
        )

        for learning in learnings:
            metadata = learning.get("metadata", {})
            if "pattern_id" in metadata:
                pattern = PromptPattern(
                    pattern_id=metadata["pattern_id"],
                    pattern_type=metadata.get("pattern_type", "unknown"),
                    description=metadata.get("description", ""),
                    trigger_conditions=metadata.get("trigger_conditions", {}),
                    approach=metadata.get("approach", ""),
                    success_count=metadata.get("success_count", 0),
                    failure_count=metadata.get("failure_count", 0),
                    total_uses=metadata.get("total_uses", 0),
                    generation=metadata.get("generation", 0)
                )
                self.patterns[pattern.pattern_id] = pattern

        self._update_pareto_frontier()

    def capture_trace(self, event: SparkEvent) -> Optional[ExecutionTrace]:
        """
        Capture an execution trace from an event.

        Called for each tool event to build the execution history.
        """
        if event.event_type not in [EventType.POST_TOOL, EventType.POST_TOOL_FAILURE]:
            return None

        # Generate trace ID
        trace_id = hashlib.md5(
            f"{event.session_id}:{event.timestamp}:{event.tool_name}".encode()
        ).hexdigest()[:12]

        # Determine outcome
        outcome = "success" if event.event_type == EventType.POST_TOOL else "failure"

        # Categorize error if present
        error_category = None
        if event.error:
            error_category = self._categorize_error(event.error)

        # Infer task category from tool and context
        task_category = self._infer_task_category(event)

        trace = ExecutionTrace(
            trace_id=trace_id,
            session_id=event.session_id,
            timestamp=event.timestamp,
            task_description=self._extract_task_description(event),
            tool_sequence=[event.tool_name] if event.tool_name else [],
            outcome=outcome,
            duration_ms=event.duration_ms or 0.0,
            error=event.error,
            error_category=error_category,
            task_category=task_category
        )

        self.traces.append(trace)
        self.session_traces[event.session_id].append(trace)
        self.total_traces += 1

        return trace

    def _extract_task_description(self, event: SparkEvent) -> str:
        """Extract a task description from the event."""
        tool_input = event.tool_input or {}

        # Try to get description from various fields
        if "prompt" in tool_input:
            return str(tool_input["prompt"])[:200]
        if "description" in tool_input:
            return str(tool_input["description"])[:200]
        if "command" in tool_input:
            return f"Execute: {str(tool_input['command'])[:150]}"
        if "file_path" in tool_input:
            return f"File operation: {tool_input['file_path']}"

        return f"Tool: {event.tool_name or 'unknown'}"

    def _infer_task_category(self, event: SparkEvent) -> str:
        """Infer task category from event context."""
        tool_name = (event.tool_name or "").lower()
        tool_input = event.tool_input or {}

        # Map tools to categories
        if tool_name in ["grep", "glob"]:
            return "search"
        elif tool_name in ["read"]:
            return "read"
        elif tool_name in ["edit", "write"]:
            return "write"
        elif tool_name == "bash":
            command = str(tool_input.get("command", "")).lower()
            if any(x in command for x in ["test", "pytest", "jest"]):
                return "testing"
            elif any(x in command for x in ["git"]):
                return "git"
            elif any(x in command for x in ["npm", "pip", "install"]):
                return "dependency"
            return "shell"
        elif tool_name == "task":
            return "agent"
        elif tool_name == "skill":
            return "skill"

        return "general"

    def _categorize_error(self, error: str) -> str:
        """Categorize an error for pattern matching."""
        error_lower = error.lower()

        if any(x in error_lower for x in ["not found", "no such", "missing"]):
            return "not_found"
        elif any(x in error_lower for x in ["permission", "denied", "access"]):
            return "permission"
        elif any(x in error_lower for x in ["timeout", "timed out"]):
            return "timeout"
        elif any(x in error_lower for x in ["syntax", "parse", "invalid"]):
            return "syntax"
        elif any(x in error_lower for x in ["conflict", "already exists"]):
            return "conflict"
        elif any(x in error_lower for x in ["network", "connection", "refused"]):
            return "network"

        return "other"

    def reflect_on_session(self, session_id: str) -> ReflectionResult:
        """
        Reflect on a session's traces to extract patterns and insights.

        This is the core GEPA-inspired reflection step:
        1. Analyze what worked and what didn't
        2. Identify patterns in successful executions
        3. Propose improvements for failures
        """
        traces = self.session_traces.get(session_id, [])

        if not traces:
            return ReflectionResult(
                traces_analyzed=0,
                patterns_identified=[],
                improvements_proposed=[],
                insights=[]
            )

        # Separate successes and failures
        successes = [t for t in traces if t.outcome == "success"]
        failures = [t for t in traces if t.outcome == "failure"]

        patterns = []
        improvements = []
        insights = []

        # Analyze successful patterns
        if successes:
            # Group by task category
            by_category = defaultdict(list)
            for t in successes:
                by_category[t.task_category].append(t)

            for category, cat_traces in by_category.items():
                if len(cat_traces) >= 2:
                    # Extract common tool sequences
                    tool_sequences = [tuple(t.tool_sequence) for t in cat_traces]
                    common_tools = self._find_common_sequence(tool_sequences)

                    if common_tools:
                        pattern = self._create_pattern_from_traces(
                            cat_traces, category, common_tools
                        )
                        patterns.append(pattern)
                        insights.append(
                            f"Pattern found: {category} tasks succeed with {' → '.join(common_tools)}"
                        )

        # Analyze failures for improvement opportunities
        if failures:
            # Group by error category
            by_error = defaultdict(list)
            for t in failures:
                by_error[t.error_category or "unknown"].append(t)

            for error_cat, error_traces in by_error.items():
                if len(error_traces) >= 2:
                    # Propose improvement
                    improvement = {
                        "error_category": error_cat,
                        "frequency": len(error_traces),
                        "suggestion": self._suggest_improvement(error_cat, error_traces),
                        "affected_tasks": [t.task_category for t in error_traces]
                    }
                    improvements.append(improvement)
                    insights.append(
                        f"Recurring {error_cat} errors ({len(error_traces)}x) - "
                        f"Consider: {improvement['suggestion']}"
                    )

        # Compare success vs failure in same category
        for category in set(t.task_category for t in traces):
            cat_success = len([t for t in successes if t.task_category == category])
            cat_failure = len([t for t in failures if t.task_category == category])

            if cat_success > 0 and cat_failure > 0:
                rate = cat_success / (cat_success + cat_failure)
                if rate < 0.7:
                    insights.append(
                        f"Low success rate for {category}: {rate:.0%} - needs attention"
                    )

        result = ReflectionResult(
            traces_analyzed=len(traces),
            patterns_identified=patterns,
            improvements_proposed=improvements,
            insights=insights
        )

        self.reflections.append(result)
        self.total_reflections += 1

        # Update patterns with new findings
        for pattern in patterns:
            self._add_or_update_pattern(pattern)

        return result

    def _find_common_sequence(self, sequences: List[Tuple[str, ...]]) -> List[str]:
        """Find common elements across tool sequences."""
        if not sequences:
            return []

        # Find tools that appear in majority of sequences
        tool_counts = defaultdict(int)
        for seq in sequences:
            for tool in set(seq):  # Count each tool once per sequence
                tool_counts[tool] += 1

        threshold = len(sequences) * 0.5
        common = [tool for tool, count in tool_counts.items() if count >= threshold]

        return common

    def _create_pattern_from_traces(
        self,
        traces: List[ExecutionTrace],
        category: str,
        common_tools: List[str]
    ) -> PromptPattern:
        """Create a new pattern from a set of successful traces."""
        pattern_id = hashlib.md5(
            f"{category}:{':'.join(sorted(common_tools))}".encode()
        ).hexdigest()[:12]

        avg_duration = sum(t.duration_ms for t in traces) / len(traces)

        return PromptPattern(
            pattern_id=pattern_id,
            pattern_type="tool_sequence",
            description=f"Successful {category} pattern using {', '.join(common_tools)}",
            trigger_conditions={"task_category": category},
            approach=f"For {category} tasks, use: {' → '.join(common_tools)}",
            tool_sequence=common_tools,
            success_count=len(traces),
            failure_count=0,
            total_uses=len(traces),
            avg_duration_ms=avg_duration
        )

    def _suggest_improvement(
        self,
        error_category: str,
        traces: List[ExecutionTrace]
    ) -> str:
        """Suggest an improvement based on error patterns."""
        suggestions = {
            "not_found": "Verify file/resource existence before operating",
            "permission": "Check permissions or use elevated access",
            "timeout": "Use shorter timeouts or break into smaller operations",
            "syntax": "Validate syntax before execution",
            "conflict": "Check for conflicts before making changes",
            "network": "Add retry logic or check connectivity",
            "other": "Review error details and add specific handling"
        }
        return suggestions.get(error_category, "Investigate and add specific handling")

    def _add_or_update_pattern(self, pattern: PromptPattern):
        """Add a new pattern or update an existing one."""
        if pattern.pattern_id in self.patterns:
            existing = self.patterns[pattern.pattern_id]
            # Merge statistics
            existing.success_count += pattern.success_count
            existing.failure_count += pattern.failure_count
            existing.total_uses += pattern.total_uses
            # Update average duration
            total_duration = (
                existing.avg_duration_ms * (existing.total_uses - pattern.total_uses) +
                pattern.avg_duration_ms * pattern.total_uses
            )
            existing.avg_duration_ms = total_duration / existing.total_uses
        else:
            self.patterns[pattern.pattern_id] = pattern

        self._update_pareto_frontier()

    def _update_pareto_frontier(self):
        """Update the Pareto frontier of patterns."""
        # A pattern is on the frontier if no other pattern dominates it
        # across all metrics (success_rate, total_uses, avg_duration)

        frontier = []
        patterns_list = list(self.patterns.values())

        for pattern in patterns_list:
            if pattern.total_uses < 3:
                continue

            dominated = False
            for other in patterns_list:
                if other.pattern_id == pattern.pattern_id:
                    continue
                if other.total_uses < 3:
                    continue

                # Check if other dominates pattern
                if (other.success_rate >= pattern.success_rate and
                    other.total_uses >= pattern.total_uses and
                    (other.success_rate > pattern.success_rate or
                     other.total_uses > pattern.total_uses)):
                    dominated = True
                    break

            if not dominated:
                frontier.append(pattern.pattern_id)

        self.pareto_frontier = frontier

    def evolve_pattern(self, pattern_id: str, feedback: str) -> Optional[PromptPattern]:
        """
        Evolve a pattern based on feedback (mutation step).

        This is the GEPA mutation: use reflection to propose improvements.
        """
        if pattern_id not in self.patterns:
            return None

        original = self.patterns[pattern_id]

        # Create evolved version
        new_id = hashlib.md5(
            f"{pattern_id}:v{original.generation + 1}:{feedback[:50]}".encode()
        ).hexdigest()[:12]

        evolved = PromptPattern(
            pattern_id=new_id,
            pattern_type=original.pattern_type,
            description=f"Evolved from {original.description}",
            trigger_conditions=original.trigger_conditions.copy(),
            approach=f"{original.approach} (Refined: {feedback})",
            tool_sequence=original.tool_sequence.copy() if original.tool_sequence else None,
            generation=original.generation + 1,
            parent_id=pattern_id
        )

        self.patterns[new_id] = evolved
        self.patterns_evolved += 1

        return evolved

    def get_pattern_for_task(self, task_category: str) -> Optional[PromptPattern]:
        """Get the best pattern for a task category."""
        matching = [
            p for p in self.patterns.values()
            if p.trigger_conditions.get("task_category") == task_category
            and p.total_uses >= 3
        ]

        if not matching:
            return None

        # Return highest fitness pattern
        return max(matching, key=lambda p: p.fitness_score)

    def get_frontier_patterns(self) -> List[PromptPattern]:
        """Get all patterns on the Pareto frontier."""
        return [self.patterns[pid] for pid in self.pareto_frontier if pid in self.patterns]

    async def process_events(self, events: List[SparkEvent]) -> List[ExecutionTrace]:
        """Process a batch of events and capture traces."""
        traces = []

        for event in events:
            trace = self.capture_trace(event)
            if trace:
                traces.append(trace)

        return traces

    async def store_learnings_in_mind(self) -> int:
        """Store evolved patterns in Mind."""
        memories = []

        # Store Pareto frontier patterns
        for pattern in self.get_frontier_patterns():
            if pattern.total_uses >= 5:
                content = (
                    f"LEARNING [PROMPT_PATTERN]: {pattern.description}. "
                    f"Approach: {pattern.approach}. "
                    f"Success rate: {pattern.success_rate:.0%} over {pattern.total_uses} uses. "
                    f"Generation: {pattern.generation}"
                )

                memory = Memory(
                    content=content,
                    temporal_level=TemporalLevel.IDENTITY,
                    salience=pattern.fitness_score,
                    content_type=ContentType.REFLECTION,
                    metadata={
                        "pattern_type": "prompt_pattern",
                        "pattern_id": pattern.pattern_id,
                        "description": pattern.description,
                        "approach": pattern.approach,
                        "trigger_conditions": pattern.trigger_conditions,
                        "success_count": pattern.success_count,
                        "failure_count": pattern.failure_count,
                        "total_uses": pattern.total_uses,
                        "generation": pattern.generation,
                        "fitness_score": pattern.fitness_score
                    }
                )
                memories.append(memory)

        # Store recent insights
        if self.reflections:
            recent = self.reflections[-1]
            for insight in recent.insights[:3]:
                memory = Memory(
                    content=f"LEARNING [REFLECTION_INSIGHT]: {insight}",
                    temporal_level=TemporalLevel.SEASONAL,
                    salience=0.7,
                    content_type=ContentType.REFLECTION,
                    metadata={"pattern_type": "reflection_insight"}
                )
                memories.append(memory)

        if memories:
            return await self.mind.store_batch(memories)
        return 0

    def get_evolution_stats(self) -> Dict[str, Any]:
        """Get statistics about prompt evolution."""
        return {
            "total_traces": self.total_traces,
            "total_patterns": len(self.patterns),
            "pareto_frontier_size": len(self.pareto_frontier),
            "total_reflections": self.total_reflections,
            "patterns_evolved": self.patterns_evolved,
            "top_patterns": [
                {
                    "id": p.pattern_id,
                    "description": p.description,
                    "success_rate": p.success_rate,
                    "uses": p.total_uses,
                    "generation": p.generation
                }
                for p in sorted(
                    self.get_frontier_patterns(),
                    key=lambda x: x.fitness_score,
                    reverse=True
                )[:5]
            ]
        }

    def clear_session_data(self):
        """Clear session-specific data but keep patterns."""
        self.traces = []
        self.session_traces.clear()
