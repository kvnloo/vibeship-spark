"""
Tests for lib/learner.py
"""

import pytest
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

# Add lib to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.queue import SparkEvent, EventType
from lib.learner import SparkLearner, ToolStats, Pattern


class TestToolStats:
    """Tests for ToolStats dataclass."""

    def test_success_rate_empty(self):
        """Success rate is 0 when no calls."""
        stats = ToolStats(name="Bash")
        assert stats.success_rate == 0.0

    def test_success_rate_all_success(self):
        """Success rate is 100% when all succeed."""
        stats = ToolStats(name="Bash", total_calls=10, successes=10, failures=0)
        assert stats.success_rate == 1.0

    def test_success_rate_mixed(self):
        """Success rate calculates correctly with mixed results."""
        stats = ToolStats(name="Bash", total_calls=10, successes=7, failures=3)
        assert stats.success_rate == 0.7

    def test_avg_duration_empty(self):
        """Avg duration is 0 when no calls."""
        stats = ToolStats(name="Bash")
        assert stats.avg_duration_ms == 0.0

    def test_avg_duration_calculation(self):
        """Avg duration calculates correctly."""
        stats = ToolStats(name="Bash", total_calls=10, total_duration_ms=1000.0)
        assert stats.avg_duration_ms == 100.0

    def test_error_types_tracking(self):
        """Error types dict can track multiple errors."""
        stats = ToolStats(name="Bash")
        stats.error_types["file_not_found"] = 3
        stats.error_types["permission_denied"] = 2
        assert stats.error_types["file_not_found"] == 3
        assert stats.error_types["permission_denied"] == 2


class TestPattern:
    """Tests for Pattern dataclass."""

    def test_pattern_creation(self):
        """Pattern creates with all fields."""
        pattern = Pattern(
            pattern_type="tool_effectiveness",
            description="Bash has 90% success",
            conditions=["tool=Bash"],
            confidence=0.9,
            sample_size=20,
            metadata={"tool": "Bash", "success_rate": 0.9}
        )
        assert pattern.pattern_type == "tool_effectiveness"
        assert pattern.confidence == 0.9
        assert pattern.sample_size == 20
        assert pattern.metadata["tool"] == "Bash"


class TestSparkLearner:
    """Tests for SparkLearner class."""

    def test_init_default(self):
        """Learner initializes with defaults."""
        learner = SparkLearner()
        assert learner.tool_stats is not None
        assert learner.session_events == []
        assert learner.patterns_found == []

    def test_init_with_mock_client(self, mock_mind_client):
        """Learner accepts mock Mind client."""
        learner = SparkLearner(mind_client=mock_mind_client)
        assert learner.mind == mock_mind_client


class TestUpdateToolStats:
    """Tests for _update_tool_stats method."""

    def test_update_success(self):
        """Updates stats on success."""
        learner = SparkLearner()
        event = SparkEvent(
            event_type=EventType.POST_TOOL,
            timestamp=1234567890.0,
            session_id="test",
            data={},
            tool_name="Bash",
            duration_ms=100.0
        )

        learner._update_tool_stats(event, success=True)

        stats = learner.tool_stats["Bash"]
        assert stats.total_calls == 1
        assert stats.successes == 1
        assert stats.failures == 0
        assert stats.total_duration_ms == 100.0

    def test_update_failure(self):
        """Updates stats on failure."""
        learner = SparkLearner()
        event = SparkEvent(
            event_type=EventType.POST_TOOL_FAILURE,
            timestamp=1234567890.0,
            session_id="test",
            data={},
            tool_name="Bash",
            error="Command not found"
        )

        learner._update_tool_stats(event, success=False)

        stats = learner.tool_stats["Bash"]
        assert stats.total_calls == 1
        assert stats.successes == 0
        assert stats.failures == 1

    def test_update_multiple_calls(self):
        """Accumulates stats across multiple calls."""
        learner = SparkLearner()

        for i in range(5):
            event = SparkEvent(
                event_type=EventType.POST_TOOL,
                timestamp=1234567890.0 + i,
                session_id="test",
                data={},
                tool_name="Bash",
                duration_ms=100.0
            )
            learner._update_tool_stats(event, success=True)

        stats = learner.tool_stats["Bash"]
        assert stats.total_calls == 5
        assert stats.successes == 5
        assert stats.total_duration_ms == 500.0

    def test_update_unknown_tool(self):
        """Handles events without tool_name."""
        learner = SparkLearner()
        event = SparkEvent(
            event_type=EventType.POST_TOOL,
            timestamp=1234567890.0,
            session_id="test",
            data={},
            tool_name=None
        )

        learner._update_tool_stats(event, success=True)

        # Should use "unknown" as tool name
        assert "unknown" in learner.tool_stats


class TestCategorizeError:
    """Tests for _categorize_error method."""

    def test_file_not_found(self):
        """Categorizes file not found errors."""
        learner = SparkLearner()
        assert learner._categorize_error("No such file or directory") == "file_not_found"
        assert learner._categorize_error("File not found: test.py") == "file_not_found"

    def test_permission_denied(self):
        """Categorizes permission errors."""
        learner = SparkLearner()
        assert learner._categorize_error("Permission denied") == "permission_denied"

    def test_timeout(self):
        """Categorizes timeout errors."""
        learner = SparkLearner()
        assert learner._categorize_error("Command timeout after 60s") == "timeout"

    def test_edit_not_unique(self):
        """Categorizes edit not unique errors."""
        learner = SparkLearner()
        assert learner._categorize_error("old_string not unique in file") == "edit_not_unique"
        assert learner._categorize_error("String is not unique") == "edit_not_unique"

    def test_syntax_error(self):
        """Categorizes syntax errors."""
        learner = SparkLearner()
        assert learner._categorize_error("SyntaxError: invalid syntax") == "syntax_error"

    def test_other_error(self):
        """Categorizes unknown errors as other."""
        learner = SparkLearner()
        assert learner._categorize_error("Some random error") == "other"


class TestGetErrorAvoidance:
    """Tests for _get_error_avoidance method."""

    def test_edit_not_unique_strategy(self):
        """Returns strategy for Edit not unique errors."""
        learner = SparkLearner()
        strategy = learner._get_error_avoidance("Edit", "edit_not_unique")
        assert strategy is not None
        assert "context" in strategy.lower()

    def test_bash_permission_denied(self):
        """Returns strategy for Bash permission errors."""
        learner = SparkLearner()
        strategy = learner._get_error_avoidance("Bash", "permission_denied")
        assert strategy is not None
        assert "permission" in strategy.lower()

    def test_unknown_combination(self):
        """Returns None for unknown tool/error combinations."""
        learner = SparkLearner()
        strategy = learner._get_error_avoidance("Unknown", "random_error")
        assert strategy is None


class TestProcessEvents:
    """Tests for process_events method."""

    @pytest.mark.asyncio
    async def test_process_success_events(self, sample_success_events, mock_mind_client):
        """Processes success events and updates stats."""
        learner = SparkLearner(mind_client=mock_mind_client)
        patterns = await learner.process_events(sample_success_events)

        assert learner.tool_stats["Bash"].total_calls == 10
        assert learner.tool_stats["Bash"].successes == 10

    @pytest.mark.asyncio
    async def test_process_mixed_events(self, sample_success_events, sample_failure_events, mock_mind_client):
        """Processes mix of success and failure events."""
        learner = SparkLearner(mind_client=mock_mind_client)

        # Process successes
        await learner.process_events(sample_success_events)
        # Process failures
        await learner.process_events(sample_failure_events)

        stats = learner.tool_stats["Bash"]
        assert stats.total_calls == 13  # 10 + 3
        assert stats.successes == 10
        assert stats.failures == 3

    @pytest.mark.asyncio
    async def test_extracts_patterns_with_enough_data(self, mock_mind_client):
        """Extracts patterns when 10+ events accumulated."""
        learner = SparkLearner(mind_client=mock_mind_client)

        # Create 15 events to trigger pattern extraction
        events = [
            SparkEvent(
                event_type=EventType.POST_TOOL,
                timestamp=1234567890.0 + i,
                session_id="test",
                data={},
                tool_name="Bash"
            )
            for i in range(15)
        ]

        patterns = await learner.process_events(events)

        # Should have extracted tool effectiveness pattern for Bash
        assert len(patterns) > 0
        assert any(p.pattern_type == "tool_effectiveness" for p in patterns)


class TestExtractPatterns:
    """Tests for _extract_patterns method."""

    @pytest.mark.asyncio
    async def test_tool_effectiveness_pattern(self, mock_mind_client):
        """Extracts tool effectiveness patterns."""
        learner = SparkLearner(mind_client=mock_mind_client)

        # Add enough events to trigger extraction
        learner.tool_stats["Bash"] = ToolStats(
            name="Bash",
            total_calls=20,
            successes=18,
            failures=2
        )
        learner.session_events = [MagicMock()] * 15  # Fake events to pass threshold

        patterns = await learner._extract_patterns()

        tool_patterns = [p for p in patterns if p.pattern_type == "tool_effectiveness"]
        assert len(tool_patterns) > 0
        assert tool_patterns[0].metadata["tool"] == "Bash"
        assert tool_patterns[0].metadata["success_rate"] == 0.9

    @pytest.mark.asyncio
    async def test_error_avoidance_pattern(self, mock_mind_client):
        """Extracts error avoidance patterns."""
        learner = SparkLearner(mind_client=mock_mind_client)

        # Add stats with recurring errors
        learner.tool_stats["Edit"] = ToolStats(
            name="Edit",
            total_calls=10,
            successes=6,
            failures=4
        )
        learner.tool_stats["Edit"].error_types["edit_not_unique"] = 4
        learner.session_events = [MagicMock()] * 15

        patterns = await learner._extract_patterns()

        error_patterns = [p for p in patterns if p.pattern_type == "error_avoidance"]
        assert len(error_patterns) > 0


class TestStorePatterns:
    """Tests for store_patterns_in_mind method."""

    @pytest.mark.asyncio
    async def test_stores_high_confidence_patterns(self, mock_mind_client):
        """Stores patterns with confidence >= 0.7."""
        learner = SparkLearner(mind_client=mock_mind_client)

        patterns = [
            Pattern(
                pattern_type="tool_effectiveness",
                description="Bash is 90% effective",
                conditions=["tool=Bash"],
                confidence=0.9,
                sample_size=20,
                metadata={"tool": "Bash"}
            )
        ]

        stored = await learner.store_patterns_in_mind(patterns)

        mock_mind_client.store_batch.assert_called_once()
        assert stored == 1

    @pytest.mark.asyncio
    async def test_skips_low_confidence_patterns(self, mock_mind_client):
        """Skips patterns with confidence < 0.7."""
        learner = SparkLearner(mind_client=mock_mind_client)

        patterns = [
            Pattern(
                pattern_type="tool_effectiveness",
                description="Bash might work",
                conditions=["tool=Bash"],
                confidence=0.5,  # Too low
                sample_size=5,
                metadata={"tool": "Bash"}
            )
        ]

        stored = await learner.store_patterns_in_mind(patterns)

        mock_mind_client.store_batch.assert_not_called()
        assert stored == 0


class TestGetToolRanking:
    """Tests for get_tool_ranking method."""

    def test_ranks_by_success_rate(self):
        """Ranks tools by success rate descending."""
        learner = SparkLearner()
        learner.tool_stats["Bash"] = ToolStats(name="Bash", total_calls=10, successes=8, failures=2)
        learner.tool_stats["Edit"] = ToolStats(name="Edit", total_calls=10, successes=6, failures=4)
        learner.tool_stats["Grep"] = ToolStats(name="Grep", total_calls=10, successes=9, failures=1)

        rankings = learner.get_tool_ranking()

        assert rankings[0][0] == "Grep"
        assert rankings[1][0] == "Bash"
        assert rankings[2][0] == "Edit"

    def test_excludes_low_sample_tools(self):
        """Excludes tools with < 3 calls."""
        learner = SparkLearner()
        learner.tool_stats["Bash"] = ToolStats(name="Bash", total_calls=10, successes=8, failures=2)
        learner.tool_stats["Rare"] = ToolStats(name="Rare", total_calls=2, successes=2, failures=0)

        rankings = learner.get_tool_ranking()

        assert len(rankings) == 1
        assert rankings[0][0] == "Bash"


class TestClearSessionData:
    """Tests for clear_session_data method."""

    def test_clears_events_and_stats(self):
        """Clears session events and tool stats."""
        learner = SparkLearner()
        learner.session_events = [MagicMock()] * 10
        learner.tool_stats["Bash"] = ToolStats(name="Bash", total_calls=5)

        learner.clear_session_data()

        assert learner.session_events == []
        assert len(learner.tool_stats) == 0
