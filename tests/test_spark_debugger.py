"""
Unit tests for lib/spark_debugger.py
"""

import pytest
from unittest.mock import MagicMock
from datetime import datetime
import tempfile
from pathlib import Path

from lib.spark_debugger import (
    SparkDebugger, DebugLevel, DebugSession, TraceStep, ReplayResult
)
from lib.queue import SparkEvent, EventType


@pytest.fixture
def debugger():
    """Create a default debugger."""
    return SparkDebugger(level=DebugLevel.MINIMAL)


@pytest.fixture
def debugger_verbose():
    """Create a verbose debugger."""
    return SparkDebugger(level=DebugLevel.VERBOSE)


@pytest.fixture
def sample_event():
    """Create a sample event."""
    return SparkEvent(
        event_type=EventType.POST_TOOL,
        timestamp=datetime.now().timestamp(),
        session_id="test_session",
        data={"key": "value"},
        tool_name="Grep",
        duration_ms=50.0,
        error=None  # No error means success
    )


class TestSparkDebuggerInit:
    """Tests for SparkDebugger initialization."""

    def test_init_default(self):
        """Initializes with defaults."""
        debugger = SparkDebugger()

        assert debugger.level == DebugLevel.NORMAL
        assert debugger.max_sessions == 50
        assert debugger.auto_capture is True
        assert debugger.current_session is None

    def test_init_with_options(self):
        """Accepts initialization options."""
        debugger = SparkDebugger(
            level=DebugLevel.VERBOSE,
            max_sessions=10,
            auto_capture=False
        )

        assert debugger.level == DebugLevel.VERBOSE
        assert debugger.max_sessions == 10
        assert debugger.auto_capture is False


class TestStartSession:
    """Tests for start_session method."""

    def test_starts_session(self, debugger):
        """Starts a new debug session."""
        session = debugger.start_session("test_session")

        assert session.session_id == "test_session"
        assert session.started_at is not None
        assert session.ended_at is None
        assert len(session.steps) == 0

    def test_sets_current_session(self, debugger):
        """Sets current session."""
        debugger.start_session("test_session")

        assert debugger.current_session is not None
        assert debugger.current_session.session_id == "test_session"

    def test_accepts_metadata(self, debugger):
        """Accepts metadata."""
        session = debugger.start_session("test", metadata={"key": "value"})

        assert session.metadata["key"] == "value"


class TestEndSession:
    """Tests for end_session method."""

    def test_ends_session(self, debugger):
        """Ends a session."""
        debugger.start_session("test_session")
        session = debugger.end_session("test_session")

        assert session.ended_at is not None

    def test_clears_current_session(self, debugger):
        """Clears current session."""
        debugger.start_session("test_session")
        debugger.end_session("test_session")

        assert debugger.current_session is None

    def test_returns_none_for_unknown_session(self, debugger):
        """Returns None for unknown session."""
        result = debugger.end_session("nonexistent")

        assert result is None


class TestCaptureEvent:
    """Tests for capture_event method."""

    def test_captures_event(self, debugger, sample_event):
        """Captures an event as trace step."""
        debugger.start_session("test_session")
        step = debugger.capture_event(sample_event)

        assert step.step_number == 1
        assert step.tool_name == "Grep"
        assert step.duration_ms == 50.0
        assert step.success is True

    def test_auto_starts_session(self, debugger, sample_event):
        """Auto-starts session if needed."""
        step = debugger.capture_event(sample_event)

        assert debugger.current_session is not None
        assert step.step_number == 1

    def test_increments_step_number(self, debugger, sample_event):
        """Increments step number."""
        debugger.start_session("test")
        debugger.capture_event(sample_event)
        step = debugger.capture_event(sample_event)

        assert step.step_number == 2

    def test_captures_raw_data_in_verbose(self, debugger_verbose, sample_event):
        """Captures raw data in verbose mode."""
        debugger_verbose.start_session("test")
        step = debugger_verbose.capture_event(sample_event)

        assert len(step.raw_data) > 0


class TestCapturePatternTrigger:
    """Tests for capture_pattern_trigger method."""

    def test_records_pattern_trigger(self, debugger):
        """Records pattern trigger."""
        debugger.start_session("test")
        debugger.capture_pattern_trigger("pattern_1", "Matched search task")

        assert "pattern_1" in debugger.current_session.patterns_triggered

    def test_stores_in_trigger_list(self, debugger):
        """Stores in pattern triggers list."""
        debugger.capture_pattern_trigger("p1", "reason")

        assert len(debugger._pattern_triggers) == 1


class TestCaptureLearning:
    """Tests for capture_learning method."""

    def test_records_learning(self, debugger):
        """Records learning generation."""
        debugger.start_session("test")
        debugger.capture_learning("learning_1", "Tool effectiveness insight")

        assert "learning_1" in debugger.current_session.learnings_generated


class TestGetSession:
    """Tests for get_session method."""

    def test_gets_session(self, debugger):
        """Gets session by ID."""
        debugger.start_session("test_session")
        session = debugger.get_session("test_session")

        assert session is not None
        assert session.session_id == "test_session"

    def test_returns_none_for_unknown(self, debugger):
        """Returns None for unknown session."""
        session = debugger.get_session("nonexistent")

        assert session is None


class TestGetSessionTrace:
    """Tests for get_session_trace method."""

    def test_gets_trace_steps(self, debugger, sample_event):
        """Gets trace steps for session."""
        debugger.start_session("test")
        debugger.capture_event(sample_event)
        debugger.capture_event(sample_event)

        steps = debugger.get_session_trace("test")

        assert len(steps) == 2

    def test_returns_empty_for_unknown(self, debugger):
        """Returns empty for unknown session."""
        steps = debugger.get_session_trace("nonexistent")

        assert len(steps) == 0


class TestGetRecentSteps:
    """Tests for get_recent_steps method."""

    def test_gets_recent_steps(self, debugger, sample_event):
        """Gets recent steps from current session."""
        debugger.start_session("test")
        for _ in range(5):
            debugger.capture_event(sample_event)

        steps = debugger.get_recent_steps(3)

        assert len(steps) == 3

    def test_returns_empty_without_session(self, debugger):
        """Returns empty without current session."""
        steps = debugger.get_recent_steps()

        assert len(steps) == 0


class TestFindStepsByTool:
    """Tests for find_steps_by_tool method."""

    def test_finds_steps(self, debugger):
        """Finds steps by tool name."""
        debugger.start_session("test")

        event1 = SparkEvent(
            event_type=EventType.POST_TOOL,
            timestamp=1.0,
            session_id="test",
            data={},
            tool_name="Grep"
        )
        event2 = SparkEvent(
            event_type=EventType.POST_TOOL,
            timestamp=2.0,
            session_id="test",
            data={},
            tool_name="Read"
        )

        debugger.capture_event(event1)
        debugger.capture_event(event2)

        grep_steps = debugger.find_steps_by_tool("Grep")

        assert len(grep_steps) == 1
        assert grep_steps[0].tool_name == "Grep"


class TestFindSlowSteps:
    """Tests for find_slow_steps method."""

    def test_finds_slow_steps(self, debugger):
        """Finds steps exceeding threshold."""
        debugger.start_session("test")

        fast = SparkEvent(
            event_type=EventType.POST_TOOL,
            timestamp=1.0,
            session_id="test",
            data={},
            tool_name="Grep",
            duration_ms=100.0
        )
        slow = SparkEvent(
            event_type=EventType.POST_TOOL,
            timestamp=2.0,
            session_id="test",
            data={},
            tool_name="Bash",
            duration_ms=2000.0
        )

        debugger.capture_event(fast)
        debugger.capture_event(slow)

        slow_steps = debugger.find_slow_steps(threshold_ms=1000)

        assert len(slow_steps) == 1
        assert slow_steps[0].tool_name == "Bash"


class TestFindFailedSteps:
    """Tests for find_failed_steps method."""

    def test_finds_failed_steps(self, debugger):
        """Finds failed steps."""
        debugger.start_session("test")

        success_event = SparkEvent(
            event_type=EventType.POST_TOOL,
            timestamp=1.0,
            session_id="test",
            data={},
            tool_name="Grep",
            error=None  # No error = success
        )
        fail_event = SparkEvent(
            event_type=EventType.POST_TOOL,
            timestamp=2.0,
            session_id="test",
            data={},
            tool_name="Bash",
            error="Some error"  # Has error = failure
        )

        debugger.capture_event(success_event)
        debugger.capture_event(fail_event)

        failed = debugger.find_failed_steps()

        assert len(failed) == 1
        assert failed[0].tool_name == "Bash"


class TestAnalyzeSession:
    """Tests for analyze_session method."""

    def test_analyzes_session(self, debugger, sample_event):
        """Analyzes session metrics."""
        debugger.start_session("test")
        for _ in range(5):
            debugger.capture_event(sample_event)
        debugger.end_session("test")

        analysis = debugger.analyze_session("test")

        assert analysis["session_id"] == "test"
        assert analysis["total_steps"] == 5
        assert "tool_usage" in analysis
        assert "success_rate" in analysis

    def test_returns_error_for_unknown(self, debugger):
        """Returns error for unknown session."""
        analysis = debugger.analyze_session("nonexistent")

        assert "error" in analysis


class TestReplaySession:
    """Tests for replay_session method."""

    def test_replays_session(self, debugger, sample_event):
        """Replays session."""
        debugger.start_session("test")
        debugger.capture_event(sample_event)
        debugger.end_session("test")

        result = debugger.replay_session("test")

        assert result.session_id == "test"
        assert result.steps_replayed == 1

    def test_returns_failure_for_unknown(self, debugger):
        """Returns failure for unknown session."""
        result = debugger.replay_session("nonexistent")

        assert result.success is False
        assert result.steps_replayed == 0


class TestCompareSession:
    """Tests for compare_sessions method."""

    def test_compares_sessions(self, debugger, sample_event):
        """Compares two sessions."""
        debugger.start_session("session1")
        debugger.capture_event(sample_event)
        debugger.end_session("session1")

        debugger.start_session("session2")
        debugger.capture_event(sample_event)
        debugger.capture_event(sample_event)
        debugger.end_session("session2")

        comparison = debugger.compare_sessions("session1", "session2")

        assert comparison["session_1"] == "session1"
        assert comparison["session_2"] == "session2"
        assert comparison["steps_difference"] == -1

    def test_returns_error_for_missing(self, debugger):
        """Returns error for missing session."""
        comparison = debugger.compare_sessions("missing1", "missing2")

        assert "error" in comparison


class TestExportSession:
    """Tests for export_session method."""

    def test_exports_json(self, debugger, sample_event):
        """Exports session as JSON."""
        debugger.start_session("test")
        debugger.capture_event(sample_event)

        exported = debugger.export_session("test", "json")

        assert "test" in exported
        assert "steps" in exported

    def test_exports_text(self, debugger, sample_event):
        """Exports session as text."""
        debugger.start_session("test")
        debugger.capture_event(sample_event)

        exported = debugger.export_session("test", "text")

        assert "Session: test" in exported
        assert "Steps:" in exported


class TestSetLevel:
    """Tests for set_level method."""

    def test_sets_level(self, debugger):
        """Sets debug level."""
        debugger.set_level(DebugLevel.TRACE)

        assert debugger.level == DebugLevel.TRACE


class TestGetStats:
    """Tests for get_stats method."""

    def test_returns_stats(self, debugger, sample_event):
        """Returns debugger statistics."""
        debugger.start_session("test")
        debugger.capture_event(sample_event)

        stats = debugger.get_stats()

        assert "level" in stats
        assert "sessions_in_memory" in stats
        assert "current_session" in stats
        assert stats["current_session_steps"] == 1


class TestClear:
    """Tests for clear method."""

    def test_clears_all_data(self, debugger, sample_event):
        """Clears all debug data."""
        debugger.start_session("test")
        debugger.capture_event(sample_event)
        debugger.clear()

        assert len(debugger.sessions) == 0
        assert debugger.current_session is None
        assert len(debugger._event_buffer) == 0


class TestTraceStepDataclass:
    """Tests for TraceStep dataclass."""

    def test_creation(self):
        """TraceStep creates with required fields."""
        step = TraceStep(
            step_number=1,
            timestamp=datetime.now(),
            event_type="post_tool",
            tool_name="Grep",
            duration_ms=50.0,
            success=True,
            data_summary="test"
        )

        assert step.step_number == 1
        assert step.tool_name == "Grep"


class TestDebugSessionDataclass:
    """Tests for DebugSession dataclass."""

    def test_creation(self):
        """DebugSession creates with required fields."""
        session = DebugSession(
            session_id="test",
            started_at=datetime.now(),
            ended_at=None,
            steps=[],
            patterns_triggered=[],
            learnings_generated=[]
        )

        assert session.session_id == "test"
        assert session.ended_at is None


class TestReplayResultDataclass:
    """Tests for ReplayResult dataclass."""

    def test_creation(self):
        """ReplayResult creates with required fields."""
        result = ReplayResult(
            session_id="test",
            steps_replayed=5,
            patterns_matched=["p1"],
            learnings_would_generate=[],
            differences=[],
            success=True
        )

        assert result.session_id == "test"
        assert result.success is True


class TestSummarizeData:
    """Tests for _summarize_data method."""

    def test_summarizes_data(self, debugger):
        """Summarizes data dict."""
        summary = debugger._summarize_data({"key": "value", "num": 42})

        assert "key=" in summary
        assert "num=42" in summary

    def test_handles_empty(self, debugger):
        """Handles empty data."""
        summary = debugger._summarize_data({})

        assert summary == "(empty)"
