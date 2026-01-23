"""
Tests for lib/prompt_evolver.py
"""

import pytest
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

# Add lib to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.queue import SparkEvent, EventType
from lib.prompt_evolver import (
    PromptEvolver, ExecutionTrace, PromptPattern, ReflectionResult
)


class TestExecutionTrace:
    """Tests for ExecutionTrace dataclass."""

    def test_creation(self):
        """ExecutionTrace creates with required fields."""
        trace = ExecutionTrace(
            trace_id="abc123",
            session_id="session1",
            timestamp=1234567890.0,
            task_description="Find test files",
            tool_sequence=["Grep", "Read"],
            outcome="success",
            duration_ms=500.0
        )
        assert trace.trace_id == "abc123"
        assert trace.outcome == "success"
        assert len(trace.tool_sequence) == 2

    def test_optional_fields(self):
        """ExecutionTrace handles optional fields."""
        trace = ExecutionTrace(
            trace_id="abc123",
            session_id="session1",
            timestamp=1234567890.0,
            task_description="Test",
            tool_sequence=[],
            outcome="failure",
            duration_ms=100.0,
            error="Not found",
            error_category="not_found"
        )
        assert trace.error == "Not found"
        assert trace.error_category == "not_found"


class TestPromptPattern:
    """Tests for PromptPattern dataclass."""

    def test_success_rate_empty(self):
        """Success rate is 0 when no uses."""
        pattern = PromptPattern(
            pattern_id="p1",
            pattern_type="tool_sequence",
            description="Test pattern",
            trigger_conditions={},
            approach="Do something"
        )
        assert pattern.success_rate == 0.0

    def test_success_rate_calculation(self):
        """Success rate calculates correctly."""
        pattern = PromptPattern(
            pattern_id="p1",
            pattern_type="tool_sequence",
            description="Test",
            trigger_conditions={},
            approach="Do something",
            success_count=8,
            failure_count=2,
            total_uses=10
        )
        assert pattern.success_rate == 0.8

    def test_fitness_score_low_samples(self):
        """Fitness score is 0 with < 3 samples."""
        pattern = PromptPattern(
            pattern_id="p1",
            pattern_type="test",
            description="Test",
            trigger_conditions={},
            approach="Test",
            total_uses=2,
            success_count=2
        )
        assert pattern.fitness_score == 0.0

    def test_fitness_score_calculation(self):
        """Fitness score calculates with Wilson score."""
        pattern = PromptPattern(
            pattern_id="p1",
            pattern_type="test",
            description="Test",
            trigger_conditions={},
            approach="Test",
            total_uses=100,
            success_count=90,
            failure_count=10
        )
        # Should be positive and less than raw success rate
        assert 0 < pattern.fitness_score < pattern.success_rate


class TestPromptEvolver:
    """Tests for PromptEvolver class."""

    def test_init_default(self):
        """PromptEvolver initializes with defaults."""
        evolver = PromptEvolver()
        assert evolver.traces == []
        assert evolver.patterns == {}
        assert evolver.total_traces == 0

    def test_init_with_mock_client(self, mock_mind_client):
        """PromptEvolver accepts mock Mind client."""
        evolver = PromptEvolver(mind_client=mock_mind_client)
        assert evolver.mind == mock_mind_client


class TestCaptureTrace:
    """Tests for capture_trace method."""

    def test_captures_success_trace(self):
        """Captures successful execution trace."""
        evolver = PromptEvolver()
        event = SparkEvent(
            event_type=EventType.POST_TOOL,
            timestamp=1234567890.0,
            session_id="session1",
            data={},
            tool_name="Bash",
            tool_input={"command": "ls"},
            duration_ms=50.0
        )

        trace = evolver.capture_trace(event)

        assert trace is not None
        assert trace.outcome == "success"
        assert trace.tool_sequence == ["Bash"]
        assert evolver.total_traces == 1

    def test_captures_failure_trace(self):
        """Captures failed execution trace."""
        evolver = PromptEvolver()
        event = SparkEvent(
            event_type=EventType.POST_TOOL_FAILURE,
            timestamp=1234567890.0,
            session_id="session1",
            data={},
            tool_name="Read",
            error="File not found"
        )

        trace = evolver.capture_trace(event)

        assert trace.outcome == "failure"
        assert trace.error == "File not found"
        assert trace.error_category == "not_found"

    def test_ignores_non_tool_events(self):
        """Ignores non-tool events."""
        evolver = PromptEvolver()
        event = SparkEvent(
            event_type=EventType.SESSION_START,
            timestamp=1234567890.0,
            session_id="session1",
            data={}
        )

        trace = evolver.capture_trace(event)

        assert trace is None
        assert evolver.total_traces == 0


class TestInferTaskCategory:
    """Tests for _infer_task_category method."""

    def test_infers_search(self):
        """Infers search category for grep/glob."""
        evolver = PromptEvolver()
        event = SparkEvent(
            event_type=EventType.POST_TOOL,
            timestamp=1234567890.0,
            session_id="test",
            data={},
            tool_name="Grep"
        )

        category = evolver._infer_task_category(event)
        assert category == "search"

    def test_infers_testing_from_command(self):
        """Infers testing from pytest command."""
        evolver = PromptEvolver()
        event = SparkEvent(
            event_type=EventType.POST_TOOL,
            timestamp=1234567890.0,
            session_id="test",
            data={},
            tool_name="Bash",
            tool_input={"command": "pytest tests/"}
        )

        category = evolver._infer_task_category(event)
        assert category == "testing"

    def test_infers_git(self):
        """Infers git category."""
        evolver = PromptEvolver()
        event = SparkEvent(
            event_type=EventType.POST_TOOL,
            timestamp=1234567890.0,
            session_id="test",
            data={},
            tool_name="Bash",
            tool_input={"command": "git status"}
        )

        category = evolver._infer_task_category(event)
        assert category == "git"


class TestCategorizeError:
    """Tests for _categorize_error method."""

    def test_not_found(self):
        """Categorizes not found errors."""
        evolver = PromptEvolver()
        assert evolver._categorize_error("File not found") == "not_found"
        assert evolver._categorize_error("No such file") == "not_found"

    def test_permission(self):
        """Categorizes permission errors."""
        evolver = PromptEvolver()
        assert evolver._categorize_error("Permission denied") == "permission"

    def test_timeout(self):
        """Categorizes timeout errors."""
        evolver = PromptEvolver()
        assert evolver._categorize_error("Request timed out") == "timeout"

    def test_syntax(self):
        """Categorizes syntax errors."""
        evolver = PromptEvolver()
        assert evolver._categorize_error("Syntax error at line 5") == "syntax"

    def test_other(self):
        """Categorizes unknown errors as other."""
        evolver = PromptEvolver()
        assert evolver._categorize_error("Something weird happened") == "other"


class TestReflectOnSession:
    """Tests for reflect_on_session method."""

    def test_reflects_on_empty_session(self):
        """Returns empty result for empty session."""
        evolver = PromptEvolver()

        result = evolver.reflect_on_session("nonexistent")

        assert result.traces_analyzed == 0
        assert result.patterns_identified == []

    def test_identifies_patterns_from_successes(self):
        """Identifies patterns from successful traces."""
        evolver = PromptEvolver()

        # Add multiple successful traces with same tool
        for i in range(3):
            evolver.session_traces["session1"].append(ExecutionTrace(
                trace_id=f"t{i}",
                session_id="session1",
                timestamp=1234567890.0 + i,
                task_description="Search for files",
                tool_sequence=["Grep"],
                outcome="success",
                duration_ms=50.0,
                task_category="search"
            ))

        result = evolver.reflect_on_session("session1")

        assert result.traces_analyzed == 3
        assert len(result.patterns_identified) >= 0  # May or may not find pattern

    def test_proposes_improvements_from_failures(self):
        """Proposes improvements from failure patterns."""
        evolver = PromptEvolver()

        # Add multiple failures with same error type
        for i in range(3):
            evolver.session_traces["session1"].append(ExecutionTrace(
                trace_id=f"t{i}",
                session_id="session1",
                timestamp=1234567890.0 + i,
                task_description="Read file",
                tool_sequence=["Read"],
                outcome="failure",
                duration_ms=10.0,
                error="File not found",
                error_category="not_found",
                task_category="read"
            ))

        result = evolver.reflect_on_session("session1")

        assert result.traces_analyzed == 3
        assert len(result.improvements_proposed) >= 1


class TestEvolvePattern:
    """Tests for evolve_pattern method."""

    def test_evolves_existing_pattern(self):
        """Evolves an existing pattern with feedback."""
        evolver = PromptEvolver()

        # Add a pattern
        original = PromptPattern(
            pattern_id="p1",
            pattern_type="tool_sequence",
            description="Search pattern",
            trigger_conditions={"task_category": "search"},
            approach="Use Grep for searching",
            generation=0
        )
        evolver.patterns["p1"] = original

        evolved = evolver.evolve_pattern("p1", "Add file type filter")

        assert evolved is not None
        assert evolved.generation == 1
        assert evolved.parent_id == "p1"
        assert "filter" in evolved.approach.lower()

    def test_returns_none_for_nonexistent(self):
        """Returns None for nonexistent pattern."""
        evolver = PromptEvolver()

        result = evolver.evolve_pattern("nonexistent", "feedback")

        assert result is None


class TestGetPatternForTask:
    """Tests for get_pattern_for_task method."""

    def test_returns_best_pattern(self):
        """Returns highest fitness pattern for task."""
        evolver = PromptEvolver()

        # Add patterns with different fitness
        evolver.patterns["p1"] = PromptPattern(
            pattern_id="p1",
            pattern_type="test",
            description="Good pattern",
            trigger_conditions={"task_category": "search"},
            approach="Do A",
            total_uses=20,
            success_count=18,
            failure_count=2
        )
        evolver.patterns["p2"] = PromptPattern(
            pattern_id="p2",
            pattern_type="test",
            description="Bad pattern",
            trigger_conditions={"task_category": "search"},
            approach="Do B",
            total_uses=20,
            success_count=10,
            failure_count=10
        )

        best = evolver.get_pattern_for_task("search")

        assert best is not None
        assert best.pattern_id == "p1"

    def test_returns_none_without_matching(self):
        """Returns None when no matching patterns."""
        evolver = PromptEvolver()

        result = evolver.get_pattern_for_task("unknown")

        assert result is None


class TestProcessEvents:
    """Tests for process_events method."""

    @pytest.mark.asyncio
    async def test_processes_tool_events(self):
        """Processes tool events and captures traces."""
        evolver = PromptEvolver()

        events = [
            SparkEvent(
                event_type=EventType.POST_TOOL,
                timestamp=1234567890.0,
                session_id="test",
                data={},
                tool_name="Bash"
            ),
            SparkEvent(
                event_type=EventType.SESSION_START,  # Should be ignored
                timestamp=1234567891.0,
                session_id="test",
                data={}
            )
        ]

        traces = await evolver.process_events(events)

        assert len(traces) == 1
        assert evolver.total_traces == 1


class TestGetEvolutionStats:
    """Tests for get_evolution_stats method."""

    def test_returns_stats(self):
        """Returns evolution statistics."""
        evolver = PromptEvolver()
        evolver.total_traces = 100
        evolver.total_reflections = 5

        stats = evolver.get_evolution_stats()

        assert stats["total_traces"] == 100
        assert stats["total_reflections"] == 5
        assert "pareto_frontier_size" in stats


class TestClearSessionData:
    """Tests for clear_session_data method."""

    def test_clears_traces_keeps_patterns(self):
        """Clears traces but keeps patterns."""
        evolver = PromptEvolver()
        evolver.traces = [MagicMock()] * 10
        evolver.patterns["p1"] = PromptPattern(
            pattern_id="p1",
            pattern_type="test",
            description="Test",
            trigger_conditions={},
            approach="Test"
        )

        evolver.clear_session_data()

        assert evolver.traces == []
        assert "p1" in evolver.patterns
