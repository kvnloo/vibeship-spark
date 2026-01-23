"""
Tests for lib/queue.py
"""

import pytest
import sys
from pathlib import Path

# Add lib to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.queue import SparkQueue, SparkEvent, EventType, quick_capture, get_queue


class TestEventType:
    """Tests for EventType enum."""

    def test_event_types_exist(self):
        """All expected event types exist."""
        assert EventType.SESSION_START == "session_start"
        assert EventType.USER_PROMPT == "user_prompt"
        assert EventType.PRE_TOOL == "pre_tool"
        assert EventType.POST_TOOL == "post_tool"
        assert EventType.POST_TOOL_FAILURE == "post_tool_failure"
        assert EventType.STOP == "stop"
        assert EventType.SESSION_END == "session_end"


class TestSparkEvent:
    """Tests for SparkEvent dataclass."""

    def test_to_dict_basic(self):
        """Event converts to dict correctly."""
        event = SparkEvent(
            event_type=EventType.POST_TOOL,
            timestamp=1234567890.0,
            session_id="test_session",
            data={"test": True},
            tool_name="Bash"
        )
        d = event.to_dict()

        assert d["event_type"] == "post_tool"
        assert d["timestamp"] == 1234567890.0
        assert d["session_id"] == "test_session"
        assert d["data"] == {"test": True}
        assert d["tool_name"] == "Bash"

    def test_to_dict_with_all_fields(self):
        """Event with all fields converts correctly."""
        event = SparkEvent(
            event_type=EventType.POST_TOOL_FAILURE,
            timestamp=1234567890.0,
            session_id="test_session",
            data={},
            tool_name="Edit",
            tool_input={"file": "test.py"},
            tool_output="Error output",
            error="File not found",
            duration_ms=150.5
        )
        d = event.to_dict()

        assert d["event_type"] == "post_tool_failure"
        assert d["tool_name"] == "Edit"
        assert d["tool_input"] == {"file": "test.py"}
        assert d["error"] == "File not found"
        assert d["duration_ms"] == 150.5

    def test_from_dict(self):
        """Event creates from dict correctly."""
        d = {
            "event_type": "post_tool",
            "timestamp": 1234567890.0,
            "session_id": "test_session",
            "data": {"key": "value"},
            "tool_name": "Bash",
            "tool_input": None,
            "tool_output": None,
            "error": None,
            "duration_ms": None
        }
        event = SparkEvent.from_dict(d)

        assert event.event_type == EventType.POST_TOOL
        assert event.session_id == "test_session"
        assert event.tool_name == "Bash"
        assert event.data == {"key": "value"}

    def test_roundtrip(self):
        """Event survives to_dict -> from_dict roundtrip."""
        original = SparkEvent(
            event_type=EventType.PRE_TOOL,
            timestamp=9999999999.0,
            session_id="roundtrip_test",
            data={"nested": {"data": [1, 2, 3]}},
            tool_name="Grep",
            tool_input={"pattern": "test"},
            duration_ms=25.0
        )

        d = original.to_dict()
        restored = SparkEvent.from_dict(d)

        assert restored.event_type == original.event_type
        assert restored.timestamp == original.timestamp
        assert restored.session_id == original.session_id
        assert restored.data == original.data
        assert restored.tool_name == original.tool_name
        assert restored.tool_input == original.tool_input


class TestSparkQueue:
    """Tests for SparkQueue class."""

    def test_init_creates_directory(self, tmp_path):
        """Queue creates directory if not exists."""
        queue_dir = tmp_path / "new_queue"
        queue = SparkQueue(queue_dir=str(queue_dir))

        assert queue_dir.exists()

    def test_push_creates_file(self, temp_queue):
        """Push creates queue file if not exists."""
        event = SparkEvent(
            event_type=EventType.POST_TOOL,
            timestamp=1234567890.0,
            session_id="test",
            data={}
        )

        result = temp_queue.push(event)

        assert result is True
        assert temp_queue.queue_file.exists()

    def test_push_returns_true_on_success(self, temp_queue):
        """Push returns True on success."""
        event = SparkEvent(
            event_type=EventType.POST_TOOL,
            timestamp=1234567890.0,
            session_id="test",
            data={}
        )

        result = temp_queue.push(event)

        assert result is True

    def test_push_appends_multiple(self, temp_queue):
        """Multiple pushes append to same file."""
        for i in range(5):
            event = SparkEvent(
                event_type=EventType.POST_TOOL,
                timestamp=float(i),
                session_id=f"test_{i}",
                data={}
            )
            temp_queue.push(event)

        assert temp_queue.size() == 5

    def test_push_raw(self, temp_queue):
        """push_raw convenience method works."""
        result = temp_queue.push_raw(
            EventType.POST_TOOL,
            "test_session",
            {"test": True},
            tool_name="Bash"
        )

        assert result is True
        assert temp_queue.size() == 1

    def test_pop_batch_returns_events(self, temp_queue):
        """Pop batch returns pushed events."""
        for i in range(5):
            temp_queue.push_raw(
                EventType.POST_TOOL,
                f"test_{i}",
                {},
                tool_name="Bash"
            )

        events = temp_queue.pop_batch(max_events=3)

        assert len(events) == 3
        assert all(isinstance(e, SparkEvent) for e in events)

    def test_pop_batch_respects_max(self, temp_queue):
        """Pop batch respects max_events limit."""
        for i in range(10):
            temp_queue.push_raw(EventType.POST_TOOL, f"test_{i}", {})

        events = temp_queue.pop_batch(max_events=3)

        assert len(events) == 3
        assert temp_queue.size() == 7  # 7 remaining

    def test_pop_batch_archives_processed(self, temp_queue):
        """Pop batch moves events to processed file."""
        for i in range(3):
            temp_queue.push_raw(EventType.POST_TOOL, f"test_{i}", {})

        temp_queue.pop_batch(max_events=3)

        assert temp_queue.processed_file.exists()
        # Check processed file has content
        with open(temp_queue.processed_file, 'r') as f:
            lines = f.readlines()
        assert len(lines) == 3

    def test_pop_batch_empty_queue(self, temp_queue):
        """Pop batch returns empty list for empty queue."""
        events = temp_queue.pop_batch(max_events=10)

        assert events == []

    def test_size_empty(self, temp_queue):
        """Size returns 0 for empty queue."""
        assert temp_queue.size() == 0

    def test_size_after_push(self, temp_queue):
        """Size reflects pushed events."""
        for i in range(7):
            temp_queue.push_raw(EventType.POST_TOOL, f"test_{i}", {})

        assert temp_queue.size() == 7

    def test_size_after_pop(self, temp_queue):
        """Size decreases after pop."""
        for i in range(10):
            temp_queue.push_raw(EventType.POST_TOOL, f"test_{i}", {})

        temp_queue.pop_batch(max_events=4)

        assert temp_queue.size() == 6


class TestQuickCapture:
    """Tests for quick_capture helper."""

    def test_quick_capture_success(self, temp_queue_dir, monkeypatch):
        """quick_capture returns True on success."""
        from lib import queue as queue_module

        test_queue = SparkQueue(queue_dir=str(temp_queue_dir))
        monkeypatch.setattr(queue_module, "_queue", test_queue)

        result = quick_capture(
            EventType.POST_TOOL,
            "session_123",
            {"test": True},
            tool_name="Bash"
        )

        assert result is True
        assert test_queue.size() == 1

    def test_quick_capture_with_all_kwargs(self, temp_queue_dir, monkeypatch):
        """quick_capture passes all kwargs to event."""
        from lib import queue as queue_module

        test_queue = SparkQueue(queue_dir=str(temp_queue_dir))
        monkeypatch.setattr(queue_module, "_queue", test_queue)

        quick_capture(
            EventType.POST_TOOL_FAILURE,
            "session_123",
            {"context": "test"},
            tool_name="Edit",
            tool_input={"file": "test.py"},
            error="Not found",
            duration_ms=100.0
        )

        events = test_queue.pop_batch(max_events=1)
        event = events[0]

        assert event.tool_name == "Edit"
        assert event.tool_input == {"file": "test.py"}
        assert event.error == "Not found"
        assert event.duration_ms == 100.0
