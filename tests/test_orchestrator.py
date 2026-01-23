"""
Tests for lib/orchestrator.py
"""

import pytest
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

# Add lib to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.queue import SparkEvent, EventType
from lib.orchestrator import (
    AgentOrchestrator, AgentUsage, AgentStats, ParallelPattern, AgentRecommendation
)


class TestAgentUsage:
    """Tests for AgentUsage dataclass."""

    def test_creation(self):
        """AgentUsage creates with required fields."""
        usage = AgentUsage(
            agent_type="Explore",
            task_description="Find all test files",
            outcome="success"
        )
        assert usage.agent_type == "Explore"
        assert usage.task_description == "Find all test files"
        assert usage.outcome == "success"

    def test_creation_with_optional_fields(self):
        """AgentUsage accepts optional fields."""
        usage = AgentUsage(
            agent_type="Plan",
            task_description="Plan implementation",
            outcome="failure",
            duration_ms=5000.0,
            error="Timeout",
            session_id="test-session",
            parallel_with=["Explore"]
        )
        assert usage.duration_ms == 5000.0
        assert usage.parallel_with == ["Explore"]


class TestAgentStats:
    """Tests for AgentStats dataclass."""

    def test_success_rate_empty(self):
        """Success rate is 0 when no uses."""
        stats = AgentStats(agent_type="test")
        assert stats.success_rate == 0.0

    def test_success_rate_calculation(self):
        """Success rate calculates correctly."""
        stats = AgentStats(
            agent_type="test",
            total_uses=10,
            successes=8,
            failures=2
        )
        assert stats.success_rate == 0.8

    def test_avg_duration_empty(self):
        """Avg duration is 0 when no uses."""
        stats = AgentStats(agent_type="test")
        assert stats.avg_duration_ms == 0.0

    def test_avg_duration_calculation(self):
        """Avg duration calculates correctly."""
        stats = AgentStats(
            agent_type="test",
            total_uses=10,
            total_duration_ms=10000.0
        )
        assert stats.avg_duration_ms == 1000.0

    def test_best_task_category_empty(self):
        """Best task category is None when no data."""
        stats = AgentStats(agent_type="test")
        assert stats.best_task_category is None

    def test_best_task_category(self):
        """Best task category returns highest success rate."""
        stats = AgentStats(agent_type="test")
        stats.task_success_rates = {
            "search": (8, 10),  # 80%
            "debugging": (3, 5),  # 60%
            "implementation": (2, 2)  # 100% but only 2 samples
        }
        assert stats.best_task_category == "search"  # 80% with enough samples


class TestParallelPattern:
    """Tests for ParallelPattern dataclass."""

    def test_creation(self):
        """ParallelPattern creates correctly."""
        pattern = ParallelPattern(
            agent_types=("Explore", "Explore"),
            task_context="search",
            success_rate=0.9,
            sample_count=10
        )
        assert pattern.agent_types == ("Explore", "Explore")
        assert pattern.success_rate == 0.9


class TestAgentRecommendation:
    """Tests for AgentRecommendation dataclass."""

    def test_creation(self):
        """AgentRecommendation creates correctly."""
        rec = AgentRecommendation(
            agent_type="Explore",
            confidence=0.85,
            reasoning="90% success for search tasks",
            alternatives=[("Plan", 0.7)]
        )
        assert rec.agent_type == "Explore"
        assert rec.confidence == 0.85


class TestAgentOrchestrator:
    """Tests for AgentOrchestrator class."""

    def test_init_default(self):
        """AgentOrchestrator initializes with defaults."""
        orch = AgentOrchestrator()
        assert orch.agent_stats is not None
        assert orch.usage_history == []
        assert orch.parallel_patterns == []

    def test_init_with_mock_client(self, mock_mind_client):
        """AgentOrchestrator accepts mock Mind client."""
        orch = AgentOrchestrator(mind_client=mock_mind_client)
        assert orch.mind == mock_mind_client


class TestTrackAgentUsage:
    """Tests for track_agent_usage method."""

    def test_tracks_success(self):
        """Tracks successful agent usage."""
        orch = AgentOrchestrator()
        event = SparkEvent(
            event_type=EventType.POST_TOOL,
            timestamp=1234567890.0,
            session_id="test",
            data={},
            tool_name="Task",
            tool_input={"subagent_type": "Explore", "prompt": "Find test files"},
            duration_ms=1000.0
        )

        usage = orch.track_agent_usage(event)

        assert usage is not None
        assert usage.agent_type == "Explore"
        assert usage.outcome == "success"
        assert orch.agent_stats["Explore"].successes == 1

    def test_tracks_failure(self):
        """Tracks failed agent usage."""
        orch = AgentOrchestrator()
        event = SparkEvent(
            event_type=EventType.POST_TOOL_FAILURE,
            timestamp=1234567890.0,
            session_id="test",
            data={},
            tool_name="Task",
            tool_input={"subagent_type": "Plan", "prompt": "Plan feature"},
            error="Timeout"
        )

        usage = orch.track_agent_usage(event)

        assert usage.outcome == "failure"
        assert usage.error == "Timeout"
        assert orch.agent_stats["Plan"].failures == 1

    def test_updates_stats(self):
        """Multiple usages update stats correctly."""
        orch = AgentOrchestrator()

        for i in range(5):
            event = SparkEvent(
                event_type=EventType.POST_TOOL,
                timestamp=1234567890.0 + i,
                session_id="test",
                data={},
                tool_name="Task",
                tool_input={"subagent_type": "Explore"},
                duration_ms=1000.0
            )
            orch.track_agent_usage(event)

        stats = orch.agent_stats["Explore"]
        assert stats.total_uses == 5
        assert stats.successes == 5
        assert stats.total_duration_ms == 5000.0


class TestInferTaskCategory:
    """Tests for _infer_task_category method."""

    def test_infers_search(self):
        """Infers search task."""
        orch = AgentOrchestrator()
        assert orch._infer_task_category("find all test files", "") == "search"
        assert orch._infer_task_category("search for config", "") == "search"
        assert orch._infer_task_category("where is the main file", "") == "search"

    def test_infers_debugging(self):
        """Infers debugging task."""
        orch = AgentOrchestrator()
        assert orch._infer_task_category("fix the bug in auth", "") == "debugging"
        assert orch._infer_task_category("error in database connection", "") == "debugging"

    def test_infers_implementation(self):
        """Infers implementation task."""
        orch = AgentOrchestrator()
        assert orch._infer_task_category("implement user login", "") == "implementation"
        assert orch._infer_task_category("create new component", "") == "implementation"
        assert orch._infer_task_category("build the API", "") == "implementation"

    def test_infers_from_agent_type(self):
        """Falls back to agent type for inference."""
        orch = AgentOrchestrator()
        assert orch._infer_task_category("do something", "Explore") == "search"
        assert orch._infer_task_category("do something", "Plan") == "planning"


class TestCategorizeError:
    """Tests for _categorize_error method."""

    def test_timeout(self):
        """Categorizes timeout errors."""
        orch = AgentOrchestrator()
        assert orch._categorize_error("Request timeout") == "timeout"

    def test_not_found(self):
        """Categorizes not found errors."""
        orch = AgentOrchestrator()
        assert orch._categorize_error("File not found") == "not_found"

    def test_context_limit(self):
        """Categorizes context limit errors."""
        orch = AgentOrchestrator()
        assert orch._categorize_error("Context too long") == "context_limit"
        assert orch._categorize_error("Token limit exceeded") == "context_limit"

    def test_other(self):
        """Categorizes unknown errors as other."""
        orch = AgentOrchestrator()
        assert orch._categorize_error("Something went wrong") == "other"


class TestProcessEvents:
    """Tests for process_events method."""

    @pytest.mark.asyncio
    async def test_processes_task_events(self, mock_mind_client):
        """Processes Task tool events."""
        orch = AgentOrchestrator(mind_client=mock_mind_client)

        events = [
            SparkEvent(
                event_type=EventType.POST_TOOL,
                timestamp=1234567890.0,
                session_id="test",
                data={},
                tool_name="Task",
                tool_input={"subagent_type": "Explore"}
            ),
            SparkEvent(
                event_type=EventType.POST_TOOL,
                timestamp=1234567891.0,
                session_id="test",
                data={},
                tool_name="Bash"  # Not a Task event
            )
        ]

        usages = await orch.process_events(events)

        assert len(usages) == 1  # Only Task events
        assert usages[0].agent_type == "Explore"


class TestGetRecommendation:
    """Tests for get_recommendation method."""

    def test_recommends_best_agent(self):
        """Recommends agent with best success rate."""
        orch = AgentOrchestrator()

        orch.agent_stats["Explore"] = AgentStats(
            agent_type="Explore", total_uses=10, successes=9, failures=1
        )
        orch.agent_stats["Plan"] = AgentStats(
            agent_type="Plan", total_uses=10, successes=7, failures=3
        )

        rec = orch.get_recommendation("find something")

        assert rec.agent_type == "Explore"
        assert rec.confidence >= 0.8

    def test_weights_task_category(self):
        """Weights task category success rate."""
        orch = AgentOrchestrator()

        # Explore is good overall but bad at debugging
        orch.agent_stats["Explore"] = AgentStats(
            agent_type="Explore", total_uses=10, successes=8, failures=2
        )
        orch.agent_stats["Explore"].task_success_rates["debugging"] = (1, 5)  # 20%

        # Plan is worse overall but good at debugging
        orch.agent_stats["Plan"] = AgentStats(
            agent_type="Plan", total_uses=10, successes=6, failures=4
        )
        orch.agent_stats["Plan"].task_success_rates["debugging"] = (4, 5)  # 80%

        rec = orch.get_recommendation("fix the bug")

        # Should recommend Plan for debugging despite lower overall rate
        assert rec.agent_type == "Plan"

    def test_returns_default_without_data(self):
        """Returns default when no data."""
        orch = AgentOrchestrator()

        rec = orch.get_recommendation("do something")

        assert rec.agent_type == "general-purpose"
        assert rec.confidence == 0.5


class TestIdentifyParallelPatterns:
    """Tests for identify_parallel_patterns method."""

    def test_identifies_successful_parallel(self):
        """Identifies successful parallel patterns."""
        orch = AgentOrchestrator()

        # Add usages with parallel execution
        for i in range(5):
            usage = AgentUsage(
                agent_type="Explore",
                task_description="search",
                outcome="success",
                session_id="test",
                parallel_with=["Explore"]
            )
            orch.usage_history.append(usage)

        patterns = orch.identify_parallel_patterns(min_samples=3)

        assert len(patterns) >= 1
        assert ("Explore", "Explore") in [p.agent_types for p in patterns]


class TestGetAgentRanking:
    """Tests for get_agent_ranking method."""

    def test_ranks_by_success_rate(self):
        """Ranks agents by success rate."""
        orch = AgentOrchestrator()

        orch.agent_stats["agent-a"] = AgentStats(
            agent_type="agent-a", total_uses=10, successes=9, failures=1
        )
        orch.agent_stats["agent-b"] = AgentStats(
            agent_type="agent-b", total_uses=10, successes=7, failures=3
        )
        orch.agent_stats["agent-c"] = AgentStats(
            agent_type="agent-c", total_uses=10, successes=5, failures=5
        )

        rankings = orch.get_agent_ranking()

        assert rankings[0][0] == "agent-a"
        assert rankings[1][0] == "agent-b"
        assert rankings[2][0] == "agent-c"

    def test_excludes_low_sample_agents(self):
        """Excludes agents with < 3 uses."""
        orch = AgentOrchestrator()

        orch.agent_stats["good-agent"] = AgentStats(
            agent_type="good-agent", total_uses=10, successes=10, failures=0
        )
        orch.agent_stats["new-agent"] = AgentStats(
            agent_type="new-agent", total_uses=2, successes=2, failures=0
        )

        rankings = orch.get_agent_ranking()

        assert len(rankings) == 1
        assert rankings[0][0] == "good-agent"


class TestGetBestAgentForTask:
    """Tests for get_best_agent_for_task method."""

    def test_returns_best_for_category(self):
        """Returns agent with best success for task category."""
        orch = AgentOrchestrator()

        orch.agent_stats["Explore"] = AgentStats(agent_type="Explore")
        orch.agent_stats["Explore"].task_success_rates["search"] = (9, 10)

        orch.agent_stats["Plan"] = AgentStats(agent_type="Plan")
        orch.agent_stats["Plan"].task_success_rates["search"] = (5, 10)

        best = orch.get_best_agent_for_task("search")

        assert best == "Explore"

    def test_returns_none_without_data(self):
        """Returns None when no data for category."""
        orch = AgentOrchestrator()

        best = orch.get_best_agent_for_task("unknown_category")

        assert best is None


class TestClearSessionData:
    """Tests for clear_session_data method."""

    def test_clears_usage_history(self):
        """Clears usage history but keeps stats."""
        orch = AgentOrchestrator()
        orch.usage_history = [MagicMock()] * 10
        orch.session_agents["session1"] = [MagicMock()] * 5
        orch.agent_stats["test"] = AgentStats(agent_type="test", total_uses=5)

        orch.clear_session_data()

        assert orch.usage_history == []
        assert len(orch.session_agents) == 0
        # Stats should be preserved
        assert "test" in orch.agent_stats
