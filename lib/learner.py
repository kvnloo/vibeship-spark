"""
Spark Learner: Pattern extraction and self-improvement engine.

This is where the magic happens. The learner:
1. Analyzes batches of events
2. Extracts patterns (what works, what fails)
3. Stores learnings in Mind
4. Updates Spark's behavior weights

All operations are async and run in background.
"""

import asyncio
import json
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
from pathlib import Path

from .queue import SparkEvent, EventType
from .mind_client import (
    MindClient, Memory, ContentType, TemporalLevel,
    store_learning, retrieve_learnings
)


@dataclass
class Pattern:
    """A learned pattern."""
    pattern_type: str  # tool_effectiveness, error_avoidance, skill_preference, etc.
    description: str
    conditions: List[str]  # When this pattern applies
    confidence: float  # 0.0 to 1.0
    sample_size: int
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ErrorInfo:
    """Information about an error occurrence."""
    category: str
    suggested_fix: Optional[str]
    count: int = 1
    recovered: int = 0  # How many times we recovered from this error


@dataclass
class ReasoningStats:
    """Statistics for reasoning/prediction accuracy."""
    tool_name: str
    total_predictions: int = 0
    correct_predictions: int = 0
    wrong_predictions: int = 0
    overconfident_count: int = 0  # High confidence but failed
    underconfident_count: int = 0  # Low confidence but succeeded

    @property
    def accuracy_rate(self) -> float:
        if self.total_predictions == 0:
            return 0.0
        return self.correct_predictions / self.total_predictions

    @property
    def is_overconfident(self) -> bool:
        return self.overconfident_count > self.underconfident_count + 2


@dataclass
class ToolStats:
    """Statistics for a tool."""
    name: str
    total_calls: int = 0
    successes: int = 0
    failures: int = 0
    total_duration_ms: float = 0.0
    error_types: Dict[str, int] = field(default_factory=dict)
    error_details: Dict[str, ErrorInfo] = field(default_factory=dict)  # category -> ErrorInfo

    @property
    def success_rate(self) -> float:
        if self.total_calls == 0:
            return 0.0
        return self.successes / self.total_calls

    @property
    def avg_duration_ms(self) -> float:
        if self.total_calls == 0:
            return 0.0
        return self.total_duration_ms / self.total_calls


class SparkLearner:
    """
    The learning engine of Spark.

    Processes events, extracts patterns, stores learnings.
    """

    def __init__(self, mind_client: Optional[MindClient] = None):
        self.mind = mind_client or MindClient()
        self.tool_stats: Dict[str, ToolStats] = defaultdict(lambda: ToolStats(name="unknown"))
        self.reasoning_stats: Dict[str, ReasoningStats] = defaultdict(lambda: ReasoningStats(tool_name="unknown"))
        self.session_events: List[SparkEvent] = []
        self.patterns_found: List[Pattern] = []
        self.reasoning_learnings: List[str] = []  # Learnings from prediction gaps

        # Behavior weights (loaded from Mind, updated by learnings)
        self.tool_weights: Dict[str, float] = {}  # tool -> preference weight
        self.skill_weights: Dict[str, float] = {}  # skill -> effectiveness weight
        self.agent_weights: Dict[str, float] = {}  # agent_type -> effectiveness weight

    async def load_existing_learnings(self):
        """Load existing learnings from Mind to initialize weights."""
        # Load tool effectiveness learnings
        tool_learnings = await self.mind.retrieve(
            query="tool effectiveness",
            limit=50,
            temporal_level=TemporalLevel.IDENTITY,
            content_type=ContentType.REFLECTION
        )

        for learning in tool_learnings:
            metadata = learning.get("metadata", {})
            if "tool" in metadata and "success_rate" in metadata:
                self.tool_weights[metadata["tool"]] = metadata["success_rate"]

        # Load skill effectiveness learnings
        skill_learnings = await self.mind.retrieve(
            query="skill effectiveness",
            limit=50,
            temporal_level=TemporalLevel.IDENTITY,
            content_type=ContentType.REFLECTION
        )

        for learning in skill_learnings:
            metadata = learning.get("metadata", {})
            if "skill" in metadata and "success_rate" in metadata:
                self.skill_weights[metadata["skill"]] = metadata["success_rate"]

    async def process_events(self, events: List[SparkEvent]) -> List[Pattern]:
        """
        Process a batch of events and extract patterns.

        This is the main entry point for the background processor.
        """
        self.session_events.extend(events)
        patterns = []

        # Update tool statistics and reasoning statistics
        for event in events:
            if event.event_type == EventType.POST_TOOL:
                self._update_tool_stats(event, success=True)
                self._update_reasoning_stats(event, success=True)
            elif event.event_type == EventType.POST_TOOL_FAILURE:
                self._update_tool_stats(event, success=False)
                self._update_reasoning_stats(event, success=False)

        # Extract patterns when we have enough data
        if len(self.session_events) >= 10:
            patterns = await self._extract_patterns()
            self.patterns_found.extend(patterns)

        return patterns

    def _update_reasoning_stats(self, event: SparkEvent, success: bool):
        """Update reasoning/prediction statistics from event."""
        tool_name = event.tool_name or "unknown"
        data = event.data or {}

        # Check if there's a prediction resolution
        resolution = data.get("prediction_resolution", {})
        if not resolution:
            return

        stats = self.reasoning_stats[tool_name]
        stats.tool_name = tool_name
        stats.total_predictions += 1

        was_correct = resolution.get("was_correct", True)
        if was_correct:
            stats.correct_predictions += 1
        else:
            stats.wrong_predictions += 1

            # Check for overconfidence vs underconfidence
            learning = resolution.get("learning", "")
            if "PREDICTION_WRONG" in learning:
                stats.overconfident_count += 1
            elif "PREDICTION_PESSIMISTIC" in learning:
                stats.underconfident_count += 1

        # Capture the reasoning learning
        reasoning_learning = data.get("reasoning_learning")
        if reasoning_learning:
            self.reasoning_learnings.append(reasoning_learning)

    def _update_tool_stats(self, event: SparkEvent, success: bool):
        """Update statistics for a tool."""
        tool_name = event.tool_name or "unknown"
        stats = self.tool_stats[tool_name]
        stats.name = tool_name
        stats.total_calls += 1

        if success:
            stats.successes += 1
            # Check if this success followed a failure (recovery)
            self._check_recovery(event)
        else:
            stats.failures += 1
            error = event.error or "unknown"
            error_category, suggested_fix = self._categorize_error(error)
            stats.error_types[error_category] = stats.error_types.get(error_category, 0) + 1

            # Store detailed error info
            if error_category not in stats.error_details:
                stats.error_details[error_category] = ErrorInfo(
                    category=error_category,
                    suggested_fix=suggested_fix
                )
            else:
                stats.error_details[error_category].count += 1

            # Track this failure for recovery detection
            self._last_failure = {
                "tool": tool_name,
                "category": error_category,
                "timestamp": event.timestamp,
                "session_id": event.session_id
            }

        if event.duration_ms:
            stats.total_duration_ms += event.duration_ms

    def _check_recovery(self, success_event: SparkEvent):
        """Check if this success recovered from a previous failure."""
        if not hasattr(self, "_last_failure") or self._last_failure is None:
            return

        last = self._last_failure
        # Same session, same tool, within reasonable time = recovery
        if (last["session_id"] == success_event.session_id and
            last["tool"] == success_event.tool_name):
            # Mark as recovered
            tool_stats = self.tool_stats.get(last["tool"])
            if tool_stats and last["category"] in tool_stats.error_details:
                tool_stats.error_details[last["category"]].recovered += 1

            # Track recovery pattern
            if not hasattr(self, "_recovery_patterns"):
                self._recovery_patterns = []
            self._recovery_patterns.append({
                "tool": last["tool"],
                "error_category": last["category"],
                "recovered": True
            })

        self._last_failure = None

    def _categorize_error(self, error: str) -> Tuple[str, Optional[str]]:
        """
        Categorize an error message and extract a suggested fix.

        Returns: (error_category, suggested_fix)
        """
        error_lower = error.lower()

        # Windows path issues
        if "\\users\\" in error_lower or "c:\\" in error_lower.replace("\\\\", "\\"):
            if "not found" in error_lower or "no such file" in error_lower:
                return ("windows_path", "Use forward slashes (/) instead of backslashes")

        # Path with spaces
        if "can't open" in error_lower and " " in error:
            return ("path_spaces", "Quote paths containing spaces")

        # Encoding issues
        if "unicode" in error_lower or "codec" in error_lower or "encode" in error_lower:
            if "charmap" in error_lower or "cp1252" in error_lower:
                return ("windows_encoding", "Use ASCII characters or set UTF-8 encoding")
            return ("encoding_error", "Check file encoding, consider UTF-8")

        # File not found
        if "not found" in error_lower or "no such file" in error_lower:
            return ("file_not_found", "Verify path exists with Read or ls first")

        # Permission issues
        if "permission" in error_lower or "access denied" in error_lower:
            return ("permission_denied", "Check file permissions or run with elevated privileges")

        # Timeout
        if "timeout" in error_lower:
            return ("timeout", "Reduce scope or increase timeout")

        # Edit conflicts
        if "not unique" in error_lower or "old_string" in error_lower:
            return ("edit_not_unique", "Include more surrounding context to make old_string unique")

        # Command not found
        if "command not found" in error_lower or "not recognized" in error_lower:
            return ("command_not_found", "Check command spelling or install required tool")

        # Syntax errors
        if "syntax" in error_lower or "parse" in error_lower:
            return ("syntax_error", "Check syntax, look for missing quotes or brackets")

        # JSON errors
        if "json" in error_lower and ("decode" in error_lower or "parse" in error_lower):
            return ("json_error", "Verify JSON format is valid")

        # Connection errors
        if "connection" in error_lower or "refused" in error_lower:
            return ("connection_error", "Check if service is running on expected port")

        # Git errors
        if "git" in error_lower:
            if "conflict" in error_lower:
                return ("git_conflict", "Resolve merge conflicts before continuing")
            if "not a git repository" in error_lower:
                return ("not_git_repo", "Initialize git or navigate to correct directory")

        # Generic/unknown
        return ("other", None)

    async def _extract_patterns(self) -> List[Pattern]:
        """Extract patterns from accumulated events."""
        patterns = []

        # Pattern 1: Tool effectiveness
        for tool_name, stats in self.tool_stats.items():
            if stats.total_calls >= 5:  # Need minimum samples
                pattern = Pattern(
                    pattern_type="tool_effectiveness",
                    description=f"{tool_name} has {stats.success_rate:.0%} success rate",
                    conditions=[f"tool={tool_name}"],
                    confidence=min(stats.total_calls / 20, 1.0),  # More samples = more confidence
                    sample_size=stats.total_calls,
                    metadata={
                        "tool": tool_name,
                        "success_rate": stats.success_rate,
                        "avg_duration_ms": stats.avg_duration_ms,
                        "error_types": dict(stats.error_types)
                    }
                )
                patterns.append(pattern)

        # Pattern 2: Error patterns with fixes
        for tool_name, stats in self.tool_stats.items():
            for error_category, error_info in stats.error_details.items():
                if error_info.count >= 2:  # Recurring error (lowered threshold)
                    fix = error_info.suggested_fix or self._get_error_avoidance(tool_name, error_category)
                    recovery_rate = error_info.recovered / error_info.count if error_info.count > 0 else 0

                    description = f"{tool_name} fails with {error_category}"
                    if fix:
                        description += f" -> Fix: {fix}"
                    if recovery_rate > 0:
                        description += f" (recovered {recovery_rate:.0%})"

                    pattern = Pattern(
                        pattern_type="error_category",
                        description=description,
                        conditions=[f"tool={tool_name}", f"error={error_category}"],
                        confidence=min(error_info.count / 5, 1.0),
                        sample_size=error_info.count,
                        metadata={
                            "tool": tool_name,
                            "error_category": error_category,
                            "suggested_fix": fix,
                            "occurrences": error_info.count,
                            "recoveries": error_info.recovered,
                            "recovery_rate": recovery_rate
                        }
                    )
                    patterns.append(pattern)

        # Pattern 3: Tool sequences that work well
        sequences = self._find_successful_sequences()
        for seq, success_rate, count in sequences:
            if success_rate > 0.8 and count >= 3:
                pattern = Pattern(
                    pattern_type="tool_sequence",
                    description=f"Sequence {' -> '.join(seq)} has {success_rate:.0%} success",
                    conditions=[f"sequence={seq}"],
                    confidence=min(count / 10, 1.0),
                    sample_size=count,
                    metadata={
                        "sequence": seq,
                        "success_rate": success_rate
                    }
                )
                patterns.append(pattern)

        # Pattern 4: Reasoning/prediction accuracy patterns
        for tool_name, stats in self.reasoning_stats.items():
            if stats.total_predictions >= 3:  # Need minimum samples
                # Overconfidence pattern
                if stats.is_overconfident:
                    pattern = Pattern(
                        pattern_type="overconfidence",
                        description=f"Overconfident with {tool_name}: predicted {stats.accuracy_rate:.0%} accuracy but often wrong",
                        conditions=[f"tool={tool_name}"],
                        confidence=min(stats.total_predictions / 10, 1.0),
                        sample_size=stats.total_predictions,
                        metadata={
                            "tool": tool_name,
                            "total_predictions": stats.total_predictions,
                            "correct": stats.correct_predictions,
                            "wrong": stats.wrong_predictions,
                            "overconfident_count": stats.overconfident_count
                        }
                    )
                    patterns.append(pattern)

                # General prediction accuracy pattern
                if stats.accuracy_rate < 0.6 and stats.total_predictions >= 5:
                    pattern = Pattern(
                        pattern_type="prediction_accuracy",
                        description=f"Low prediction accuracy for {tool_name}: {stats.accuracy_rate:.0%} correct",
                        conditions=[f"tool={tool_name}"],
                        confidence=min(stats.total_predictions / 10, 1.0),
                        sample_size=stats.total_predictions,
                        metadata={
                            "tool": tool_name,
                            "accuracy_rate": stats.accuracy_rate,
                            "needs_calibration": True
                        }
                    )
                    patterns.append(pattern)

        # Pattern 5: Goal strategies (what works for what goal types)
        goal_patterns = self._extract_goal_patterns()
        patterns.extend(goal_patterns)

        # Pattern 6: Reasoning learnings (from prediction gaps)
        if self.reasoning_learnings:
            # Deduplicate and count similar learnings
            learning_counts: Dict[str, int] = {}
            for learning in self.reasoning_learnings:
                # Normalize to first 50 chars for grouping
                key = learning[:50].lower()
                learning_counts[key] = learning_counts.get(key, 0) + 1

            for learning_key, count in learning_counts.items():
                if count >= 2:  # Recurring pattern
                    # Find the full learning
                    full_learning = next(
                        (l for l in self.reasoning_learnings if l[:50].lower() == learning_key),
                        learning_key
                    )
                    pattern = Pattern(
                        pattern_type="reasoning_gap",
                        description=full_learning,
                        conditions=["prediction != outcome"],
                        confidence=min(count / 5, 1.0),
                        sample_size=count,
                        metadata={
                            "learning_type": "prediction_gap",
                            "occurrences": count
                        }
                    )
                    patterns.append(pattern)

        return patterns

    def _extract_goal_patterns(self) -> List[Pattern]:
        """Extract patterns from completed goals."""
        patterns = []

        # Load goals from file
        from pathlib import Path
        goals_file = Path.home() / ".spark" / "active_goals.json"
        if not goals_file.exists():
            return patterns

        try:
            import json
            goals = json.loads(goals_file.read_text())

            # Group completed goals by type
            by_type: Dict[str, List[dict]] = {}
            for g_id, g in goals.items():
                if g.get("status") == "completed" and g.get("goal_type"):
                    goal_type = g["goal_type"]
                    if goal_type not in by_type:
                        by_type[goal_type] = []
                    by_type[goal_type].append(g)

            # Extract patterns for each goal type
            for goal_type, completed_goals in by_type.items():
                if len(completed_goals) >= 1:  # Even single goals are valuable
                    # Calculate average success and tool sequences
                    success_scores = [g.get("success_score", 0.5) for g in completed_goals]
                    avg_success = sum(success_scores) / len(success_scores)

                    # Find common tool sequences
                    tool_sequences = []
                    for g in completed_goals:
                        actions = g.get("actions", [])
                        seq = [a.get("tool") for a in actions if a.get("tool")]
                        if seq:
                            tool_sequences.append(tuple(seq[:5]))  # First 5 tools

                    # Find most common sequence
                    if tool_sequences:
                        from collections import Counter
                        seq_counts = Counter(tool_sequences)
                        most_common_seq, count = seq_counts.most_common(1)[0]

                        # Accept single occurrences for early learning
                        if avg_success >= 0.6:
                            seq_str = " -> ".join(most_common_seq)
                            # Confidence based on sample size but min 0.6 for success
                            # This ensures even single goals get stored
                            base_confidence = min(len(completed_goals) / 3, 1.0)
                            confidence = max(base_confidence, avg_success * 0.8)  # At least 80% of success
                            pattern = Pattern(
                                pattern_type="goal_strategy",
                                description=f"For {goal_type}: {seq_str} works ({avg_success:.0%} success)",
                                conditions=[f"goal_type={goal_type}"],
                                confidence=confidence,
                                sample_size=len(completed_goals),
                                metadata={
                                    "goal_type": goal_type,
                                    "tool_sequence": list(most_common_seq),
                                    "avg_success": avg_success,
                                    "sample_size": len(completed_goals)
                                }
                            )
                            patterns.append(pattern)

        except Exception:
            pass

        return patterns

    def _get_error_avoidance(self, tool: str, error_type: str) -> Optional[str]:
        """Get avoidance strategy for a tool/error combination."""
        strategies = {
            ("Edit", "edit_not_unique"): "Include more surrounding context in old_string to make it unique",
            ("Edit", "file_not_found"): "Always Read the file first to verify it exists",
            ("Bash", "permission_denied"): "Check file permissions before executing",
            ("Write", "file_not_found"): "Create parent directories first with mkdir -p",
            ("Grep", "timeout"): "Use more specific patterns or limit search scope",
        }
        return strategies.get((tool, error_type))

    def _find_successful_sequences(self) -> List[Tuple[List[str], float, int]]:
        """Find tool sequences that work well together."""
        # Group events by session
        sessions: Dict[str, List[SparkEvent]] = defaultdict(list)
        for event in self.session_events:
            sessions[event.session_id].append(event)

        # Find sequences of 2-3 tools
        sequences: Dict[tuple, List[bool]] = defaultdict(list)

        for session_events in sessions.values():
            tool_events = [
                e for e in session_events
                if e.event_type in (EventType.POST_TOOL, EventType.POST_TOOL_FAILURE)
            ]

            for i in range(len(tool_events) - 1):
                # 2-tool sequences
                seq = (tool_events[i].tool_name, tool_events[i+1].tool_name)
                success = tool_events[i+1].event_type == EventType.POST_TOOL
                sequences[seq].append(success)

                # 3-tool sequences
                if i < len(tool_events) - 2:
                    seq3 = (
                        tool_events[i].tool_name,
                        tool_events[i+1].tool_name,
                        tool_events[i+2].tool_name
                    )
                    success3 = tool_events[i+2].event_type == EventType.POST_TOOL
                    sequences[seq3].append(success3)

        # Calculate success rates
        results = []
        for seq, outcomes in sequences.items():
            if len(outcomes) >= 3:
                success_rate = sum(outcomes) / len(outcomes)
                results.append((list(seq), success_rate, len(outcomes)))

        return results

    async def store_patterns_in_mind(self, patterns: List[Pattern]):
        """Store extracted patterns in Mind as learnings."""
        memories = []

        for pattern in patterns:
            # Lower threshold for goal strategies (early learning)
            min_confidence = 0.5 if pattern.pattern_type == "goal_strategy" else 0.7
            if pattern.confidence >= min_confidence:
                memory = Memory(
                    content=f"LEARNING [{pattern.pattern_type.upper()}]: {pattern.description}. "
                           f"Conditions: {', '.join(pattern.conditions)}. "
                           f"Confidence: {pattern.confidence:.0%} ({pattern.sample_size} samples)",
                    temporal_level=TemporalLevel.IDENTITY,
                    salience=pattern.confidence,
                    content_type=ContentType.REFLECTION,
                    metadata=pattern.metadata
                )
                memories.append(memory)

        if memories:
            stored = await self.mind.store_batch(memories)
            return stored
        return 0

    async def get_recommendation(self, tool_name: str, context: Dict[str, Any]) -> Optional[str]:
        """Get a recommendation for using a tool based on learnings."""
        # Query Mind for relevant learnings
        learnings = await self.mind.retrieve(
            query=f"{tool_name} usage recommendations",
            limit=5,
            temporal_level=TemporalLevel.IDENTITY
        )

        if learnings:
            # Return the most relevant recommendation
            return learnings[0].get("content")
        return None

    def get_tool_ranking(self) -> List[Tuple[str, float]]:
        """Get tools ranked by effectiveness."""
        rankings = []
        for tool_name, stats in self.tool_stats.items():
            if stats.total_calls >= 3:
                rankings.append((tool_name, stats.success_rate))

        rankings.sort(key=lambda x: x[1], reverse=True)
        return rankings

    def clear_session_data(self):
        """Clear session-specific data after processing."""
        self.session_events = []
        self.tool_stats.clear()
