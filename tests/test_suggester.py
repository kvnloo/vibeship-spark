"""
Tests for lib/suggester.py
"""

import pytest
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

# Add lib to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.suggester import Suggester, Suggestion, SuggestionContext


class TestSuggestion:
    """Tests for Suggestion dataclass."""

    def test_creation(self):
        """Suggestion creates with required fields."""
        suggestion = Suggestion(
            suggestion_id="s1",
            suggestion_type="warning",
            priority=2,
            title="Watch out",
            description="Be careful here",
            confidence=0.8
        )
        assert suggestion.suggestion_id == "s1"
        assert suggestion.priority == 2

    def test_helpfulness_rate_no_feedback(self):
        """Helpfulness rate is 0.5 with no feedback."""
        suggestion = Suggestion(
            suggestion_id="s1",
            suggestion_type="tip",
            priority=3,
            title="Tip",
            description="Helpful tip",
            confidence=0.7
        )
        assert suggestion.helpfulness_rate == 0.5

    def test_helpfulness_rate_calculation(self):
        """Helpfulness rate calculates correctly."""
        suggestion = Suggestion(
            suggestion_id="s1",
            suggestion_type="tip",
            priority=3,
            title="Tip",
            description="Helpful tip",
            confidence=0.7,
            times_helpful=8,
            times_dismissed=2
        )
        assert suggestion.helpfulness_rate == 0.8

    def test_should_still_show_new(self):
        """New suggestions should be shown."""
        suggestion = Suggestion(
            suggestion_id="s1",
            suggestion_type="tip",
            priority=3,
            title="Tip",
            description="Test",
            confidence=0.7
        )
        assert suggestion.should_still_show is True

    def test_should_not_show_consistently_dismissed(self):
        """Consistently dismissed suggestions should not be shown."""
        suggestion = Suggestion(
            suggestion_id="s1",
            suggestion_type="tip",
            priority=3,
            title="Tip",
            description="Test",
            confidence=0.7,
            times_helpful=0,
            times_dismissed=6
        )
        assert suggestion.should_still_show is False


class TestSuggestionContext:
    """Tests for SuggestionContext dataclass."""

    def test_creation(self):
        """SuggestionContext creates with defaults."""
        ctx = SuggestionContext()
        assert ctx.task_description is None
        assert ctx.recent_tools == []
        assert ctx.keywords == set()


class TestSuggester:
    """Tests for Suggester class."""

    def test_init_default(self):
        """Suggester initializes with defaults."""
        suggester = Suggester()
        assert suggester.suggestions == {}
        assert suggester.total_suggestions_shown == 0

    def test_init_with_mock_client(self, mock_mind_client):
        """Suggester accepts mock Mind client."""
        suggester = Suggester(mind_client=mock_mind_client)
        assert suggester.mind == mock_mind_client


class TestUpdateContext:
    """Tests for update_context method."""

    def test_updates_task(self):
        """Updates task description."""
        suggester = Suggester()

        suggester.update_context(task_description="Find test files")

        assert suggester.current_context.task_description == "Find test files"
        assert "find" in suggester.current_context.keywords

    def test_updates_current_tool(self):
        """Updates current tool."""
        suggester = Suggester()

        suggester.update_context(current_tool="Grep")

        assert suggester.current_context.current_tool == "Grep"
        assert "Grep" in suggester.current_context.recent_tools

    def test_tracks_recent_tools(self):
        """Tracks recent tools."""
        suggester = Suggester()

        for i in range(15):
            suggester.update_context(current_tool=f"Tool{i}")

        # Should only keep last 10
        assert len(suggester.current_context.recent_tools) == 10

    def test_clears_on_new_session(self):
        """Clears shown suggestions on new session."""
        suggester = Suggester()
        suggester.shown_this_session.add("s1")

        suggester.update_context(session_id="old_session")
        suggester.update_context(session_id="new_session")

        assert len(suggester.shown_this_session) == 0


class TestExtractKeywords:
    """Tests for _extract_keywords method."""

    def test_extracts_search_keywords(self):
        """Extracts search-related keywords."""
        suggester = Suggester()

        keywords = suggester._extract_keywords("find all test files")

        assert any("find" in k for k in keywords) or any("search" in k for k in keywords)

    def test_extracts_edit_keywords(self):
        """Extracts edit-related keywords."""
        suggester = Suggester()

        keywords = suggester._extract_keywords("modify the configuration")

        assert any("modify" in k or "edit" in k or "change" in k for k in keywords)

    def test_handles_empty(self):
        """Handles empty input."""
        suggester = Suggester()

        keywords = suggester._extract_keywords("")

        assert keywords == []


class TestCreateWarningFromErrorPattern:
    """Tests for _create_warning_from_error_pattern method."""

    def test_creates_warning(self):
        """Creates warning from error pattern."""
        suggester = Suggester()
        content = "LEARNING [ERROR_AVOIDANCE]: To avoid timeout errors, use shorter commands."
        metadata = {"error_type": "timeout", "tool": "Bash", "confidence": 0.8}

        warning = suggester._create_warning_from_error_pattern(content, metadata)

        assert warning is not None
        assert warning.suggestion_type == "warning"
        assert "timeout" in warning.title.lower()

    def test_returns_none_for_invalid(self):
        """Returns None for non-error content."""
        suggester = Suggester()
        content = "LEARNING [TOOL_EFFECTIVENESS]: Bash works well."
        metadata = {}

        warning = suggester._create_warning_from_error_pattern(content, metadata)

        assert warning is None


class TestCreateRecommendationFromToolPattern:
    """Tests for _create_recommendation_from_tool_pattern method."""

    def test_creates_recommendation(self):
        """Creates recommendation from tool pattern."""
        suggester = Suggester()
        content = "LEARNING [TOOL_EFFECTIVENESS]: Grep has 95% success rate."
        metadata = {"tool": "Grep", "success_rate": 0.95, "best_for": "search"}

        rec = suggester._create_recommendation_from_tool_pattern(content, metadata)

        assert rec is not None
        assert rec.suggestion_type == "recommendation"
        assert "Grep" in rec.title

    def test_ignores_low_success(self):
        """Ignores tools with low success rate."""
        suggester = Suggester()
        content = "LEARNING [TOOL_EFFECTIVENESS]: BadTool has 50% success."
        metadata = {"tool": "BadTool", "success_rate": 0.5}

        rec = suggester._create_recommendation_from_tool_pattern(content, metadata)

        assert rec is None


class TestGetRelevantSuggestions:
    """Tests for get_relevant_suggestions method."""

    def test_returns_matching_suggestions(self):
        """Returns suggestions matching context."""
        suggester = Suggester()

        # Add a suggestion
        suggestion = Suggestion(
            suggestion_id="s1",
            suggestion_type="recommendation",
            priority=2,
            title="Use Grep",
            description="Grep is great for searching",
            confidence=0.9,
            trigger_keywords=["search", "find"]
        )
        suggester.suggestions["s1"] = suggestion

        # Update context to match
        suggester.update_context(task_description="find all files")

        relevant = suggester.get_relevant_suggestions()

        assert len(relevant) >= 1
        assert suggestion in relevant

    def test_respects_max_suggestions(self):
        """Respects max_suggestions limit."""
        suggester = Suggester()

        # Add many suggestions
        for i in range(10):
            suggester.suggestions[f"s{i}"] = Suggestion(
                suggestion_id=f"s{i}",
                suggestion_type="tip",
                priority=3,
                title=f"Tip {i}",
                description="Generic tip",
                confidence=0.8,
                trigger_keywords=["test"]
            )

        suggester.update_context(task_description="run tests")

        relevant = suggester.get_relevant_suggestions(max_suggestions=3)

        assert len(relevant) <= 3

    def test_avoids_showing_twice(self):
        """Doesn't show same suggestion twice in session."""
        suggester = Suggester()

        suggestion = Suggestion(
            suggestion_id="s1",
            suggestion_type="tip",
            priority=3,
            title="Tip",
            description="Test",
            confidence=0.8,
            trigger_keywords=["test"]
        )
        suggester.suggestions["s1"] = suggestion
        suggester.update_context(task_description="run tests")

        # First call
        first = suggester.get_relevant_suggestions()
        # Second call
        second = suggester.get_relevant_suggestions()

        assert suggestion in first
        assert suggestion not in second


class TestMarkSuggestionHelpful:
    """Tests for mark_suggestion_helpful method."""

    def test_marks_helpful(self):
        """Marks suggestion as helpful."""
        suggester = Suggester()
        suggester.suggestions["s1"] = Suggestion(
            suggestion_id="s1",
            suggestion_type="tip",
            priority=3,
            title="Tip",
            description="Test",
            confidence=0.8
        )

        suggester.mark_suggestion_helpful("s1", True)

        assert suggester.suggestions["s1"].times_helpful == 1

    def test_marks_not_helpful(self):
        """Marks suggestion as not helpful."""
        suggester = Suggester()
        suggester.suggestions["s1"] = Suggestion(
            suggestion_id="s1",
            suggestion_type="tip",
            priority=3,
            title="Tip",
            description="Test",
            confidence=0.8
        )

        suggester.mark_suggestion_helpful("s1", False)

        assert suggester.suggestions["s1"].times_dismissed == 1


class TestGetWarningsForTool:
    """Tests for get_warnings_for_tool method."""

    def test_returns_tool_warnings(self):
        """Returns warnings for specific tool."""
        suggester = Suggester()

        # Add tool-specific warning
        suggester.suggestions["w1"] = Suggestion(
            suggestion_id="w1",
            suggestion_type="warning",
            priority=2,
            title="Bash warning",
            description="Watch out",
            confidence=0.8,
            trigger_tool="Bash"
        )

        # Add generic warning
        suggester.suggestions["w2"] = Suggestion(
            suggestion_id="w2",
            suggestion_type="warning",
            priority=2,
            title="General warning",
            description="Watch out",
            confidence=0.8,
            trigger_tool=None
        )

        warnings = suggester.get_warnings_for_tool("Bash")

        assert len(warnings) == 2
        assert any(w.suggestion_id == "w1" for w in warnings)


class TestGetRecommendationsForTask:
    """Tests for get_recommendations_for_task method."""

    def test_returns_relevant_recommendations(self):
        """Returns recommendations for task."""
        suggester = Suggester()

        suggester.suggestions["r1"] = Suggestion(
            suggestion_id="r1",
            suggestion_type="recommendation",
            priority=3,
            title="Use Grep",
            description="Good for search",
            confidence=0.9,
            trigger_keywords=["search", "find"],
            trigger_task_type="search"
        )

        recs = suggester.get_recommendations_for_task("find all test files")

        assert len(recs) >= 1


class TestFormatSuggestionsForDisplay:
    """Tests for format_suggestions_for_display method."""

    def test_formats_compact(self):
        """Formats suggestions in compact mode."""
        suggester = Suggester()
        suggestions = [
            Suggestion(
                suggestion_id="s1",
                suggestion_type="warning",
                priority=2,
                title="Watch out",
                description="Be careful",
                confidence=0.8
            )
        ]

        formatted = suggester.format_suggestions_for_display(suggestions, compact=True)

        assert "Watch out" in formatted
        assert "Be careful" in formatted

    def test_formats_expanded(self):
        """Formats suggestions in expanded mode."""
        suggester = Suggester()
        suggestions = [
            Suggestion(
                suggestion_id="s1",
                suggestion_type="recommendation",
                priority=3,
                title="Use Grep",
                description="Good for search",
                confidence=0.8,
                evidence=["90% success rate"]
            )
        ]

        formatted = suggester.format_suggestions_for_display(suggestions, compact=False)

        assert "Use Grep" in formatted
        assert "90% success rate" in formatted

    def test_handles_empty(self):
        """Handles empty suggestion list."""
        suggester = Suggester()

        formatted = suggester.format_suggestions_for_display([])

        assert formatted == ""


class TestGetStats:
    """Tests for get_stats method."""

    def test_returns_stats(self):
        """Returns suggester statistics."""
        suggester = Suggester()
        suggester.suggestions["s1"] = Suggestion(
            suggestion_id="s1",
            suggestion_type="tip",
            priority=3,
            title="Tip",
            description="Test",
            confidence=0.8
        )

        stats = suggester.get_stats()

        assert stats["total_suggestions"] == 1
        assert "by_type" in stats


class TestClearSession:
    """Tests for clear_session method."""

    def test_clears_session_data(self):
        """Clears session-specific data."""
        suggester = Suggester()
        suggester.shown_this_session.add("s1")
        suggester.current_context.task_description = "test"

        suggester.clear_session()

        assert len(suggester.shown_this_session) == 0
        assert suggester.current_context.task_description is None
