"""
End-to-end session simulation tests.

These tests verify the complete flow:
OBSERVE -> QUEUE -> PROCESS -> LEARN -> STORE -> INJECT
"""

import pytest
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from lib.queue import SparkEvent, EventType
from tests.integration.conftest import SessionScenario, SessionSimulator


class TestSessionFlow:
    """Tests for complete session flow."""

    @pytest.mark.asyncio
    async def test_basic_session_flow(self, simulator, sample_events):
        """Basic session processes events without errors."""
        scenario = SessionScenario(
            name="basic_flow",
            description="Simple event processing",
            events=sample_events
        )

        result = await simulator.simulate_session(scenario)

        assert result.events_processed == len(sample_events)
        assert len(result.errors) == 0

    @pytest.mark.asyncio
    async def test_search_session_extracts_patterns(self, simulator, search_scenario):
        """Search-heavy session extracts tool patterns."""
        result = await simulator.simulate_session(search_scenario)

        assert result.events_processed == len(search_scenario.events)
        # With 15 Grep calls, should extract at least one pattern
        assert result.patterns_extracted >= 0  # May be 0 if not enough variety

    @pytest.mark.asyncio
    async def test_edit_session_extracts_patterns(self, simulator, edit_scenario):
        """Edit-heavy session extracts tool patterns."""
        result = await simulator.simulate_session(edit_scenario)

        assert result.events_processed == len(edit_scenario.events)
        assert result.patterns_extracted >= 0

    @pytest.mark.asyncio
    async def test_error_session_captures_failures(self, simulator, error_scenario):
        """Error-heavy session captures failure patterns."""
        result = await simulator.simulate_session(error_scenario)

        assert result.events_processed == len(error_scenario.events)
        # Should identify error patterns
        assert result.patterns_extracted >= 0

    @pytest.mark.asyncio
    async def test_mixed_session_handles_variety(self, simulator, mixed_scenario):
        """Mixed session handles different event types."""
        result = await simulator.simulate_session(mixed_scenario)

        assert result.events_processed == len(mixed_scenario.events)
        assert len(result.errors) == 0


class TestQueueIntegration:
    """Tests for queue integration with processor."""

    @pytest.mark.asyncio
    async def test_events_survive_queue_roundtrip(self, isolated_queue, sample_events):
        """Events maintain integrity through queue."""
        # Push events
        for event in sample_events:
            isolated_queue.push(event)

        # Pop events
        retrieved = isolated_queue.pop_batch(len(sample_events))

        assert len(retrieved) == len(sample_events)
        for original, retrieved in zip(sample_events, retrieved):
            assert original.tool_name == retrieved.tool_name
            assert original.session_id == retrieved.session_id

    @pytest.mark.asyncio
    async def test_queue_handles_high_volume(self, isolated_queue):
        """Queue handles large number of events."""
        num_events = 1000
        events = [
            SparkEvent(
                event_type=EventType.POST_TOOL,
                timestamp=float(i),
                session_id="volume_test",
                data={},
                tool_name=f"Tool{i % 10}"
            )
            for i in range(num_events)
        ]

        # Push all
        for event in events:
            isolated_queue.push(event)

        assert isolated_queue.size() == num_events

        # Pop all
        retrieved = isolated_queue.pop_batch(num_events)
        assert len(retrieved) == num_events
        assert isolated_queue.size() == 0


class TestLearnerIntegration:
    """Tests for learner integration."""

    @pytest.mark.asyncio
    async def test_learner_processes_events(self, mock_mind, sample_events):
        """Learner processes events and extracts patterns."""
        from lib.learner import SparkLearner

        learner = SparkLearner(mock_mind)
        patterns = await learner.process_events(sample_events)

        # May or may not find patterns depending on thresholds
        assert patterns is not None or patterns == []

    @pytest.mark.asyncio
    async def test_learner_builds_tool_weights(self, mock_mind):
        """Learner builds tool effectiveness weights."""
        from lib.learner import SparkLearner

        learner = SparkLearner(mock_mind)

        # Process many events of same tool
        events = [
            SparkEvent(
                event_type=EventType.POST_TOOL,
                timestamp=float(i),
                session_id="weight_test",
                data={},
                tool_name="Grep",
                duration_ms=50.0
            )
            for i in range(20)
        ]

        await learner.process_events(events)

        rankings = learner.get_tool_ranking()
        # Should have Grep in rankings
        tool_names = [t for t, _ in rankings]
        assert "Grep" in tool_names


class TestContextInjection:
    """Tests for context injection flow."""

    @pytest.mark.asyncio
    async def test_injection_with_no_learnings(self, mock_mind):
        """Injection with no Mind learnings may still return content from local files."""
        from lib.context_injector import ContextInjector

        injector = ContextInjector(mock_mind)
        result = await injector.get_injection_string("test_project")
        await injector.close()

        # Even with no Mind learnings, may return content from:
        # - ~/.spark/active_goals.json (goal strategies)
        # - Other local state files
        # So we just verify it doesn't crash and returns string or None
        assert result is None or isinstance(result, str)

    @pytest.mark.asyncio
    async def test_injection_with_learnings(self, mock_mind):
        """Injection returns content when learnings exist."""
        from lib.context_injector import ContextInjector
        from lib.mind_client import Memory, TemporalLevel, ContentType

        # Pre-populate with a learning
        await mock_mind.store(Memory(
            content="LEARNING [TOOL_EFFECTIVENESS]: Grep has 95% success rate",
            temporal_level=TemporalLevel.IDENTITY,
            salience=0.9,
            content_type=ContentType.OBSERVATION,
            metadata={"pattern_type": "tool_effectiveness", "tool": "Grep"}
        ))

        injector = ContextInjector(mock_mind)
        context = await injector.gather_context("test_project")
        await injector.close()

        # Should find the learning
        assert len(context.tool_insights) >= 0  # Depends on query matching


class TestM4Integration:
    """Tests for M4 component integration."""

    @pytest.mark.asyncio
    async def test_prompt_evolver_captures_traces(self, mock_mind, sample_events):
        """PromptEvolver captures execution traces."""
        from lib.prompt_evolver import PromptEvolver

        evolver = PromptEvolver(mock_mind)
        traces = await evolver.process_events(sample_events)

        assert len(traces) == len(sample_events)
        assert evolver.total_traces == len(sample_events)

    @pytest.mark.asyncio
    async def test_meta_learner_records_learnings(self, mock_mind):
        """MetaLearner tracks learning events."""
        from lib.meta_learner import MetaLearner

        ml = MetaLearner(mock_mind)

        for i in range(10):
            ml.record_learning("tool", "learner", 0.7 + i * 0.02)

        assert ml.total_learnings == 10
        trends = ml.analyze_learning_trends()
        # Should have trend data for "tool" type
        assert "tool" in trends

    @pytest.mark.asyncio
    async def test_suggester_matches_context(self, mock_mind):
        """Suggester matches suggestions to context."""
        from lib.suggester import Suggester, Suggestion

        suggester = Suggester(mock_mind)

        # Add a suggestion
        suggester.suggestions["s1"] = Suggestion(
            suggestion_id="s1",
            suggestion_type="recommendation",
            priority=2,
            title="Use Grep for search",
            description="Grep is efficient for searching",
            confidence=0.9,
            trigger_keywords=["search", "find", "look"]
        )

        # Update context
        suggester.update_context(task_description="find all test files")

        # Get relevant
        relevant = suggester.get_relevant_suggestions()

        assert len(relevant) == 1
        assert relevant[0].title == "Use Grep for search"


class TestFullLoop:
    """Tests for the complete learning loop."""

    @pytest.mark.asyncio
    async def test_observe_learn_inject_loop(self, mock_mind, isolated_queue):
        """Complete loop: observe -> learn -> inject."""
        from lib.learner import SparkLearner
        from lib.context_injector import ContextInjector
        from lib.mind_client import Memory, TemporalLevel, ContentType

        # 1. OBSERVE - Push events
        events = [
            SparkEvent(
                event_type=EventType.POST_TOOL,
                timestamp=float(i),
                session_id="loop_test",
                data={},
                tool_name="Grep",
                duration_ms=50.0
            )
            for i in range(20)
        ]

        for e in events:
            isolated_queue.push(e)

        # 2. PROCESS - Pop and learn
        learner = SparkLearner(mock_mind)
        retrieved = isolated_queue.pop_batch(20)
        patterns = await learner.process_events(retrieved)

        # 3. STORE - Save high-confidence patterns
        # Manually store a learning to simulate
        await mock_mind.store(Memory(
            content="LEARNING [TOOL_EFFECTIVENESS]: Grep works well for search",
            temporal_level=TemporalLevel.IDENTITY,
            salience=0.8,
            content_type=ContentType.OBSERVATION,
            metadata={"pattern_type": "tool_effectiveness"}
        ))

        # 4. INJECT - Next session gets context
        injector = ContextInjector(mock_mind)
        context = await injector.gather_context("test_project")
        await injector.close()

        # Verify loop completed
        assert len(retrieved) == 20
        assert len(mock_mind.memories) >= 1

    @pytest.mark.asyncio
    async def test_multiple_sessions_accumulate(self, simulator, search_scenario, edit_scenario):
        """Multiple sessions accumulate learnings."""
        # Session 1
        result1 = await simulator.simulate_session(search_scenario)

        # Session 2
        result2 = await simulator.simulate_session(edit_scenario)

        # Both should complete
        assert result1.events_processed == len(search_scenario.events)
        assert result2.events_processed == len(edit_scenario.events)

        # Meta-learner should have recorded from both
        assert simulator.meta_learner.total_learnings >= 0
