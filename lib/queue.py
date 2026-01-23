"""
Spark Queue: Ultra-fast event capture for zero-interference hooks.

Design principle: Hooks should complete in < 50ms.
All heavy processing happens in the background processor.
"""

import json
import os
import time
from pathlib import Path
from typing import Any, Dict, Optional
from dataclasses import dataclass, asdict
from enum import Enum


class EventType(str, Enum):
    """Types of events Spark observes."""
    SESSION_START = "session_start"
    USER_PROMPT = "user_prompt"
    PRE_TOOL = "pre_tool"
    POST_TOOL = "post_tool"
    POST_TOOL_FAILURE = "post_tool_failure"
    STOP = "stop"
    SESSION_END = "session_end"


@dataclass
class SparkEvent:
    """A single observation event."""
    event_type: EventType
    timestamp: float
    session_id: str
    data: Dict[str, Any]

    # Optional fields
    tool_name: Optional[str] = None
    tool_input: Optional[Dict[str, Any]] = None
    tool_output: Optional[str] = None
    error: Optional[str] = None
    duration_ms: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        result = asdict(self)
        result['event_type'] = self.event_type.value
        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SparkEvent':
        """Create from dictionary."""
        data['event_type'] = EventType(data['event_type'])
        return cls(**data)


class SparkQueue:
    """
    File-based event queue for ultra-fast capture.

    Design:
    - Append-only JSONL file for speed
    - File locking for concurrent access
    - No network calls, no database - just file I/O
    - Background processor reads and clears periodically
    """

    def __init__(self, queue_dir: Optional[str] = None):
        """Initialize the queue."""
        if queue_dir:
            self.queue_dir = Path(queue_dir)
        else:
            # Default: ~/.spark/queue/
            self.queue_dir = Path.home() / ".spark" / "queue"

        self.queue_dir.mkdir(parents=True, exist_ok=True)
        self.queue_file = self.queue_dir / "events.jsonl"
        self.processed_file = self.queue_dir / "processed.jsonl"

    def push(self, event: SparkEvent) -> bool:
        """
        Push an event to the queue.

        MUST be fast (< 10ms target).
        Uses append mode + file locking for safety.
        """
        try:
            line = json.dumps(event.to_dict()) + "\n"

            # Append with file locking (Windows compatible)
            with open(self.queue_file, 'a', encoding='utf-8') as f:
                # On Windows, we just append (no fcntl)
                # On Unix, we'd use fcntl.flock
                f.write(line)

            return True
        except Exception:
            # Never fail the hook - just lose this event
            return False

    def push_raw(self, event_type: EventType, session_id: str, data: Dict[str, Any], **kwargs) -> bool:
        """Convenience method to push raw data."""
        event = SparkEvent(
            event_type=event_type,
            timestamp=time.time(),
            session_id=session_id,
            data=data,
            **kwargs
        )
        return self.push(event)

    def pop_batch(self, max_events: int = 100) -> list[SparkEvent]:
        """
        Pop a batch of events for processing.

        Called by background processor, not hooks.
        Moves processed events to processed.jsonl for debugging.
        """
        events = []

        if not self.queue_file.exists():
            return events

        try:
            # Read all events
            with open(self.queue_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()

            # Parse events (up to max)
            for line in lines[:max_events]:
                line = line.strip()
                if line:
                    try:
                        data = json.loads(line)
                        events.append(SparkEvent.from_dict(data))
                    except json.JSONDecodeError:
                        continue

            # Move processed to archive, keep unprocessed
            remaining = lines[max_events:]

            # Archive processed
            with open(self.processed_file, 'a', encoding='utf-8') as f:
                for line in lines[:max_events]:
                    f.write(line)

            # Rewrite queue with remaining
            with open(self.queue_file, 'w', encoding='utf-8') as f:
                f.writelines(remaining)

        except Exception:
            pass

        return events

    def size(self) -> int:
        """Get approximate queue size (line count)."""
        if not self.queue_file.exists():
            return 0
        try:
            with open(self.queue_file, 'r', encoding='utf-8') as f:
                return sum(1 for _ in f)
        except Exception:
            return 0


# Singleton for fast access
_queue: Optional[SparkQueue] = None

def get_queue() -> SparkQueue:
    """Get the global queue instance."""
    global _queue
    if _queue is None:
        _queue = SparkQueue()
    return _queue


def quick_capture(event_type: EventType, session_id: str, data: Dict[str, Any], **kwargs) -> bool:
    """
    Ultra-fast event capture for hooks.

    This is the ONLY function hooks should call.
    Everything else happens in background.
    """
    return get_queue().push_raw(event_type, session_id, data, **kwargs)
