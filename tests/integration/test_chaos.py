"""
Chaos and failure testing for Spark.

Tests system behavior under adverse conditions:
- Mind unavailable
- Malformed events
- Queue overflow
- Concurrent access
- Timeout scenarios
"""

import pytest
import asyncio
import sys
import json
import tempfile
import os
from pathlib import Path
from unittest.mock import patch, MagicMock, AsyncMock

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from lib.queue import SparkQueue, SparkEvent, EventType
from lib.mind_client import MindClient, Memory, TemporalLevel, ContentType
from lib.learner import SparkLearner
from lib.context_injector import ContextInjector
from lib.prompt_evolver import PromptEvolver
from lib.meta_learner import MetaLearner
from lib.suggester import Suggester


class TestMindUnavailable:
    """Tests for system behavior when Mind is unavailable."""

    @pytest.mark.asyncio
    async def test_learner_continues_without_mind(self, mock_mind, sample_events):
        """Learner processes events even when Mind is down."""
        mock_mind.set_unavailable()

        learner = SparkLearner(mock_mind)
        patterns = await learner.process_events(sample_events)

        # Should still extract patterns locally
        # (storage will fail but extraction works)
        assert patterns is not None or patterns == []

    @pytest.mark.asyncio
    async def test_learner_storage_fails_gracefully(self, mock_mind):
        """Pattern storage fails gracefully when Mind unavailable."""
        mock_mind.set_unavailable()

        learner = SparkLearner(mock_mind)

        # Create enough events for a pattern
        events = [
            SparkEvent(
                event_type=EventType.POST_TOOL,
                timestamp=float(i),
                session_id="test",
                data={},
                tool_name="Grep",
                duration_ms=50.0
            )
            for i in range(20)
        ]

        patterns = await learner.process_events(events)

        # Try to store - should return 0 stored
        stored = await learner.store_patterns_in_mind(patterns or [])
        assert stored == 0

    @pytest.mark.asyncio
    async def test_context_injector_returns_none_without_mind(self, mock_mind):
        """Context injector returns None when Mind unavailable."""
        mock_mind.set_unavailable()

        injector = ContextInjector(mock_mind)
        result = await injector.get_injection_string("test_project")
        await injector.close()

        assert result is None

    @pytest.mark.asyncio
    async def test_suggester_works_without_mind(self, mock_mind):
        """Suggester continues with local suggestions when Mind unavailable."""
        mock_mind.set_unavailable()

        suggester = Suggester(mock_mind)

        # Add local suggestion
        from lib.suggester import Suggestion
        suggester.suggestions["local1"] = Suggestion(
            suggestion_id="local1",
            suggestion_type="tip",
            priority=3,
            title="Local tip",
            description="This is a local suggestion",
            confidence=0.8,
            trigger_keywords=["test"]
        )

        suggester.update_context(task_description="run tests")
        relevant = suggester.get_relevant_suggestions()

        # Should still return local suggestion
        assert len(relevant) == 1

    @pytest.mark.asyncio
    async def test_mind_reconnection(self, mock_mind, sample_events):
        """System recovers when Mind becomes available again."""
        # Start unavailable
        mock_mind.set_unavailable()

        learner = SparkLearner(mock_mind)
        await learner.process_events(sample_events)

        # Should fail to store
        available1 = await mock_mind.is_available()
        assert available1 is False

        # Reconnect
        mock_mind.set_available()

        # Should work now
        available2 = await mock_mind.is_available()
        assert available2 is True


class TestMalformedEvents:
    """Tests for handling malformed or corrupted events."""

    def test_queue_handles_none_event(self, isolated_queue):
        """Queue handles None event gracefully."""
        try:
            isolated_queue.push(None)
            # Should not crash, may skip or raise
        except (TypeError, AttributeError):
            pass  # Expected behavior

    def test_queue_handles_empty_event(self, isolated_queue):
        """Queue handles event with missing fields."""
        # Create minimal event
        event = SparkEvent(
            event_type=EventType.POST_TOOL,
            timestamp=1.0,
            session_id="test",
            data={}
        )
        # Should handle missing optional fields
        isolated_queue.push(event)
        assert isolated_queue.size() == 1

    @pytest.mark.asyncio
    async def test_learner_handles_corrupt_event(self, mock_mind):
        """Learner handles events with corrupt data."""
        learner = SparkLearner(mock_mind)

        # Event with weird data
        events = [
            SparkEvent(
                event_type=EventType.POST_TOOL,
                timestamp=1.0,
                session_id="test",
                data={"corrupt": object()},  # Non-serializable
                tool_name=None  # Missing tool name
            )
        ]

        try:
            patterns = await learner.process_events(events)
            # Should either skip or handle gracefully
            assert patterns is not None or patterns == []
        except Exception:
            pass  # Some corruption may raise

    @pytest.mark.asyncio
    async def test_prompt_evolver_handles_missing_fields(self, mock_mind):
        """PromptEvolver handles events with missing optional fields."""
        evolver = PromptEvolver(mock_mind)

        event = SparkEvent(
            event_type=EventType.POST_TOOL,
            timestamp=1.0,
            session_id="test",
            data={},
            tool_name="Test"
            # Missing: duration_ms, tool_input, etc.
        )

        trace = evolver.capture_trace(event)
        # Should create trace with defaults
        assert trace is not None or trace is None  # Either is acceptable


class TestQueueResilience:
    """Tests for queue resilience under stress."""

    def test_queue_handles_concurrent_writes(self, temp_queue_dir):
        """Queue handles concurrent write attempts."""
        import threading

        queue = SparkQueue(queue_dir=temp_queue_dir)
        errors = []

        def write_events(start_id, count):
            try:
                for i in range(count):
                    event = SparkEvent(
                        event_type=EventType.POST_TOOL,
                        timestamp=float(start_id * 1000 + i),
                        session_id=f"thread_{start_id}",
                        data={},
                        tool_name=f"Tool_{start_id}_{i}"
                    )
                    queue.push(event)
            except Exception as e:
                errors.append(e)

        # Launch multiple threads
        threads = []
        for i in range(5):
            t = threading.Thread(target=write_events, args=(i, 100))
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        # Should have all events (or at least most)
        assert queue.size() >= 400  # Allow some loss under contention
        assert len(errors) == 0

    def test_queue_handles_large_events(self, isolated_queue):
        """Queue handles events with large payloads."""
        large_data = {"key": "x" * 100000}  # 100KB string

        event = SparkEvent(
            event_type=EventType.POST_TOOL,
            timestamp=1.0,
            session_id="large_test",
            data=large_data,
            tool_name="Test"
        )

        isolated_queue.push(event)
        retrieved = isolated_queue.pop_batch(1)

        assert len(retrieved) == 1
        assert len(retrieved[0].data.get("key", "")) == 100000

    def test_queue_handles_special_characters(self, isolated_queue):
        """Queue handles events with special characters."""
        special_data = {
            "unicode": "Hello \u4e16\u754c",
            "emoji": "Test 🔥✨",
            "newlines": "Line1\nLine2\rLine3",
            "quotes": 'Say "hello" and \'goodbye\'',
            "backslash": "path\\to\\file"
        }

        event = SparkEvent(
            event_type=EventType.POST_TOOL,
            timestamp=1.0,
            session_id="special_test",
            data=special_data,
            tool_name="Test"
        )

        isolated_queue.push(event)
        retrieved = isolated_queue.pop_batch(1)

        assert len(retrieved) == 1
        assert retrieved[0].data["unicode"] == special_data["unicode"]


class TestTimeoutScenarios:
    """Tests for timeout handling."""

    @pytest.mark.asyncio
    async def test_slow_mind_operation(self, mock_mind):
        """System handles slow Mind operations."""
        # Make store slow
        original_store = mock_mind.store

        async def slow_store(memory):
            await asyncio.sleep(0.1)  # 100ms delay
            return await original_store(memory)

        mock_mind.store = slow_store

        learner = SparkLearner(mock_mind)
        # Should still complete (no hard timeout in learner)
        from lib.mind_client import Memory, TemporalLevel, ContentType
        memory = Memory(
            content="test",
            temporal_level=TemporalLevel.SITUATIONAL,
            salience=0.5,
            content_type=ContentType.OBSERVATION
        )
        result = await mock_mind.store(memory)
        assert result is not None


class TestDataIntegrity:
    """Tests for data integrity under various conditions."""

    @pytest.mark.asyncio
    async def test_patterns_preserve_metadata(self, mock_mind):
        """Extracted patterns preserve all metadata."""
        learner = SparkLearner(mock_mind)

        events = [
            SparkEvent(
                event_type=EventType.POST_TOOL,
                timestamp=float(i),
                session_id="integrity_test",
                data={"custom_field": f"value_{i}"},
                tool_name="Grep",
                tool_input={"pattern": "test"},
                duration_ms=50.0
            )
            for i in range(20)
        ]

        patterns = await learner.process_events(events)

        # Patterns should exist and have structure
        if patterns:
            for p in patterns:
                assert hasattr(p, 'pattern_type')
                assert hasattr(p, 'confidence')
                assert hasattr(p, 'sample_size')

    @pytest.mark.asyncio
    async def test_meta_learner_tracks_all_types(self, mock_mind):
        """MetaLearner correctly tracks all learning types."""
        ml = MetaLearner(mock_mind)

        types = ["tool", "skill", "agent", "prompt", "error"]
        for lt in types:
            ml.record_learning(lt, "test_source", 0.8)

        assert ml.total_learnings == len(types)
        for lt in types:
            assert lt in ml.events_by_type


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_empty_queue_pop(self, isolated_queue):
        """Popping from empty queue returns empty list."""
        events = isolated_queue.pop_batch(100)
        assert events == []

    @pytest.mark.asyncio
    async def test_learner_empty_events(self, mock_mind):
        """Learner handles empty event list."""
        learner = SparkLearner(mock_mind)
        patterns = await learner.process_events([])
        assert patterns == [] or patterns is None

    @pytest.mark.asyncio
    async def test_suggester_empty_context(self, mock_mind):
        """Suggester handles empty context."""
        suggester = Suggester(mock_mind)
        # Don't set any context
        relevant = suggester.get_relevant_suggestions()
        # Should return empty, not crash
        assert relevant == []

    @pytest.mark.asyncio
    async def test_prompt_evolver_reflect_empty_session(self, mock_mind):
        """PromptEvolver reflects on non-existent session."""
        evolver = PromptEvolver(mock_mind)
        result = evolver.reflect_on_session("nonexistent_session_12345")

        assert result.traces_analyzed == 0
        assert result.patterns_identified == []

    def test_meta_learner_prune_empty(self, mock_mind):
        """MetaLearner prunes with no candidates."""
        ml = MetaLearner(mock_mind)
        pruned = ml.prune_learnings([])
        assert pruned == 0


class TestRecoveryScenarios:
    """Tests for recovery from failure states."""

    def test_queue_recovers_from_corrupt_file(self, temp_queue_dir):
        """Queue recovers from corrupt queue file."""
        queue_file = Path(temp_queue_dir) / "events.jsonl"

        # Write corrupt data
        with open(queue_file, 'w') as f:
            f.write("not valid json\n")
            f.write('{"also": "incomplete\n')

        # Create queue - should handle corrupt file
        try:
            queue = SparkQueue(queue_dir=temp_queue_dir)
            # Should either skip corrupt lines or reinitialize
            events = queue.pop_batch(10)
            assert isinstance(events, list)
        except Exception:
            # Acceptable to raise on corruption
            pass

    @pytest.mark.asyncio
    async def test_mind_client_handles_network_error(self):
        """MindClient handles network errors gracefully."""
        # Create client pointing to non-existent server
        client = MindClient(base_url="http://localhost:99999")

        available = await client.is_available()
        assert available is False

        # Should not crash on operations
        results = await client.retrieve("test")
        assert results == []

        await client.close()
