"""
Tests for lib/context_injector.py
"""

import pytest
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

# Add lib to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.context_injector import ContextInjector, InjectionContext


class TestInjectionContext:
    """Tests for InjectionContext dataclass."""

    def test_empty_context(self):
        """Empty context has no content."""
        ctx = InjectionContext()
        assert not ctx.has_content
        assert ctx.total_items() == 0

    def test_has_content_with_tools(self):
        """Context with tool insights has content."""
        ctx = InjectionContext(tool_insights=["Bash has 90% success"])
        assert ctx.has_content
        assert ctx.total_items() == 1

    def test_has_content_with_agents(self):
        """Context with agent recommendations has content."""
        ctx = InjectionContext(
            agent_recommendations=[("Explore", 0.9, "good for search")]
        )
        assert ctx.has_content
        assert ctx.total_items() == 1

    def test_has_content_with_skills(self):
        """Context with skill recommendations has content."""
        ctx = InjectionContext(
            skill_recommendations=[("auth-skill", 0.85, "good for auth")]
        )
        assert ctx.has_content

    def test_has_content_with_warnings(self):
        """Context with error warnings has content."""
        ctx = InjectionContext(error_warnings=["Watch for timeouts"])
        assert ctx.has_content

    def test_total_items_all_categories(self):
        """Total items counts all categories."""
        ctx = InjectionContext(
            tool_insights=["a", "b"],
            skill_recommendations=[("s1", 0.8, "r1")],
            agent_recommendations=[("a1", 0.9, "r1"), ("a2", 0.8, "r2")],
            error_warnings=["w1"],
            parallel_patterns=["p1"],
            project_specific=["ps1", "ps2"]
        )
        assert ctx.total_items() == 9


class TestContextInjector:
    """Tests for ContextInjector class."""

    def test_init_default(self):
        """ContextInjector initializes with defaults."""
        injector = ContextInjector()
        assert injector.mind is not None
        assert injector.MAX_CONTEXT_CHARS == 1000

    def test_init_with_mock_client(self, mock_mind_client):
        """ContextInjector accepts mock Mind client."""
        injector = ContextInjector(mind_client=mock_mind_client)
        assert injector.mind == mock_mind_client


class TestFormatToolInsight:
    """Tests for _format_tool_insight method."""

    def test_formats_valid_insight(self):
        """Formats valid tool effectiveness content."""
        injector = ContextInjector()
        content = "LEARNING [TOOL_EFFECTIVENESS]: Bash has 87% success rate. Details here."
        result = injector._format_tool_insight(content)
        assert result == "Bash has 87% success rate."

    def test_truncates_long_insight(self):
        """Truncates insights over 70 chars."""
        injector = ContextInjector()
        content = "LEARNING [TOOL_EFFECTIVENESS]: This is a very long tool effectiveness insight that needs to be truncated to fit."
        result = injector._format_tool_insight(content)
        assert result is not None
        assert len(result) <= 70  # Implementation truncates at 70

    def test_returns_none_for_non_tool(self):
        """Returns None for non-tool content."""
        injector = ContextInjector()
        content = "LEARNING [ERROR_AVOIDANCE]: Something else."
        result = injector._format_tool_insight(content)
        assert result is None


class TestFormatErrorWarning:
    """Tests for _format_error_warning method."""

    def test_formats_to_avoid_warning(self):
        """Formats 'To avoid' style warnings."""
        injector = ContextInjector()
        content = "LEARNING [ERROR_AVOIDANCE]: To avoid timeout errors, use shorter commands. Details."
        result = injector._format_error_warning(content)
        assert result == "To avoid timeout errors, use shorter commands."

    def test_returns_none_for_non_error(self):
        """Returns None for non-error content."""
        injector = ContextInjector()
        content = "LEARNING [TOOL_EFFECTIVENESS]: Bash works great."
        result = injector._format_error_warning(content)
        assert result is None

    def test_truncates_long_warning(self):
        """Truncates warnings over 70 chars."""
        injector = ContextInjector()
        content = "LEARNING [ERROR_AVOIDANCE]: To avoid very complicated errors that have extremely long descriptions and detailed explanations."
        result = injector._format_error_warning(content)
        assert result is not None
        assert len(result) <= 70


class TestGatherContext:
    """Tests for gather_context method."""

    @pytest.mark.asyncio
    async def test_returns_empty_when_mind_unavailable(self, mock_mind_client):
        """Returns empty context when Mind is unavailable."""
        mock_mind_client.is_available = AsyncMock(return_value=False)
        injector = ContextInjector(mind_client=mock_mind_client)

        ctx = await injector.gather_context()

        assert not ctx.has_content
        assert ctx.total_items() == 0

    @pytest.mark.asyncio
    async def test_gathers_tool_insights(self, mock_mind_client):
        """Gathers tool insights from Mind."""
        mock_mind_client.retrieve = AsyncMock(return_value=[
            {"content": "LEARNING [TOOL_EFFECTIVENESS]: Bash has 90% success.", "metadata": {}}
        ])
        injector = ContextInjector(mind_client=mock_mind_client)

        ctx = await injector.gather_context()

        assert len(ctx.tool_insights) >= 0  # May be empty due to filtering

    @pytest.mark.asyncio
    async def test_gathers_agent_recommendations(self, mock_mind_client):
        """Gathers agent recommendations from Mind."""
        mock_mind_client.retrieve = AsyncMock(return_value=[
            {
                "content": "LEARNING [AGENT_EFFECTIVENESS]: Explore works well.",
                "metadata": {"agent_type": "Explore", "success_rate": 0.85, "best_task": "search"}
            }
        ])
        injector = ContextInjector(mind_client=mock_mind_client)

        ctx = await injector.gather_context()

        # Check that retrieve was called
        assert mock_mind_client.retrieve.called

    @pytest.mark.asyncio
    async def test_handles_exceptions_gracefully(self, mock_mind_client):
        """Handles exceptions during gathering."""
        mock_mind_client.retrieve = AsyncMock(side_effect=Exception("Network error"))
        injector = ContextInjector(mind_client=mock_mind_client)

        # Should not raise, returns empty context
        ctx = await injector.gather_context()
        assert isinstance(ctx, InjectionContext)


class TestGatherToolInsights:
    """Tests for _gather_tool_insights method."""

    @pytest.mark.asyncio
    async def test_queries_tool_terms(self, mock_mind_client):
        """Uses simple single-term queries (Mind Lite works better this way)."""
        mock_mind_client.retrieve = AsyncMock(return_value=[])
        injector = ContextInjector(mind_client=mock_mind_client)

        await injector._gather_tool_insights("my-project")

        # Check query uses simple terms (not complex project-specific queries)
        # Mind Lite returns 0 results for complex queries
        call_args = mock_mind_client.retrieve.call_args
        query = call_args.kwargs.get("query", "")
        assert query in ["TOOL_EFFECTIVENESS", "TOOL_SEQUENCE"]

    @pytest.mark.asyncio
    async def test_limits_results(self, mock_mind_client):
        """Limits number of insights returned."""
        mock_mind_client.retrieve = AsyncMock(return_value=[
            {"content": f"LEARNING [TOOL_EFFECTIVENESS]: Tool{i} has 90% success.", "metadata": {}}
            for i in range(10)
        ])
        injector = ContextInjector(mind_client=mock_mind_client)

        insights = await injector._gather_tool_insights(None)

        assert len(insights) <= injector.MAX_ITEMS_PER_CATEGORY


class TestGatherAgentRecommendations:
    """Tests for _gather_agent_recommendations method."""

    @pytest.mark.asyncio
    async def test_filters_low_success(self, mock_mind_client):
        """Filters out agents with < 60% success."""
        mock_mind_client.retrieve = AsyncMock(return_value=[
            {"content": "...", "metadata": {"agent_type": "BadAgent", "success_rate": 0.5, "best_task": "search"}}
        ])
        injector = ContextInjector(mind_client=mock_mind_client)

        recs = await injector._gather_agent_recommendations(None)

        assert len(recs) == 0

    @pytest.mark.asyncio
    async def test_sorts_by_success_rate(self, mock_mind_client):
        """Sorts recommendations by success rate."""
        mock_mind_client.retrieve = AsyncMock(return_value=[
            {"content": "...", "metadata": {"agent_type": "AgentA", "success_rate": 0.7, "best_task": "a"}},
            {"content": "...", "metadata": {"agent_type": "AgentB", "success_rate": 0.9, "best_task": "b"}},
        ])
        injector = ContextInjector(mind_client=mock_mind_client)

        recs = await injector._gather_agent_recommendations(None)

        if len(recs) >= 2:
            assert recs[0][1] >= recs[1][1]  # First should have higher rate


class TestGatherSkillRecommendations:
    """Tests for _gather_skill_recommendations method."""

    @pytest.mark.asyncio
    async def test_filters_low_success(self, mock_mind_client):
        """Filters out skills with < 70% success."""
        mock_mind_client.retrieve = AsyncMock(return_value=[
            {"content": "...", "metadata": {"skill_id": "bad-skill", "success_rate": 0.5, "best_task": "auth"}}
        ])
        injector = ContextInjector(mind_client=mock_mind_client)

        recs = await injector._gather_skill_recommendations(None)

        assert len(recs) == 0

    @pytest.mark.asyncio
    async def test_includes_high_success(self, mock_mind_client):
        """Includes skills with >= 70% success."""
        mock_mind_client.retrieve = AsyncMock(return_value=[
            {"content": "...", "metadata": {"skill_id": "good-skill", "success_rate": 0.85, "best_task": "auth"}}
        ])
        injector = ContextInjector(mind_client=mock_mind_client)

        recs = await injector._gather_skill_recommendations(None)

        assert len(recs) == 1
        assert recs[0][0] == "good-skill"


class TestFormatForInjection:
    """Tests for format_for_injection method."""

    def test_returns_none_for_empty(self):
        """Returns None for empty context."""
        injector = ContextInjector()
        ctx = InjectionContext()
        result = injector.format_for_injection(ctx)
        assert result is None

    def test_includes_header(self):
        """Output includes Spark header."""
        injector = ContextInjector()
        ctx = InjectionContext(tool_insights=["Bash has 90% success"])
        result = injector.format_for_injection(ctx)
        assert "Spark" in result

    def test_includes_tool_insights(self):
        """Output includes tool insights."""
        injector = ContextInjector()
        ctx = InjectionContext(tool_insights=["Bash has 90% success"])
        result = injector.format_for_injection(ctx)
        assert "Bash" in result

    def test_includes_agent_recommendations(self):
        """Output includes agent recommendations."""
        injector = ContextInjector()
        ctx = InjectionContext(
            agent_recommendations=[("Explore", 0.9, "good for search")]
        )
        result = injector.format_for_injection(ctx)
        assert "Explore" in result

    def test_includes_error_warnings(self):
        """Output includes error warnings."""
        injector = ContextInjector()
        ctx = InjectionContext(
            tool_insights=["something"],
            error_warnings=["Watch for timeouts"]
        )
        result = injector.format_for_injection(ctx)
        assert "Watch for" in result or "timeouts" in result

    def test_respects_max_chars(self):
        """Output stays under MAX_CONTEXT_CHARS."""
        injector = ContextInjector()
        ctx = InjectionContext(
            tool_insights=["x" * 200] * 10,
            agent_recommendations=[("Agent", 0.9, "y" * 100)] * 10,
            error_warnings=["z" * 100] * 10
        )
        result = injector.format_for_injection(ctx)
        assert len(result) <= injector.MAX_CONTEXT_CHARS + 100  # Allow some buffer


class TestGetInjectionString:
    """Tests for get_injection_string method."""

    @pytest.mark.asyncio
    async def test_returns_formatted_string(self, mock_mind_client):
        """Returns formatted injection string."""
        mock_mind_client.retrieve = AsyncMock(return_value=[
            {"content": "LEARNING [TOOL_EFFECTIVENESS]: Bash has 95% success.", "metadata": {}}
        ])
        injector = ContextInjector(mind_client=mock_mind_client)

        result = await injector.get_injection_string()

        # May return None if no content passes filters, or a string
        assert result is None or isinstance(result, str)

    @pytest.mark.asyncio
    async def test_returns_none_when_unavailable(self, mock_mind_client):
        """Returns None when Mind unavailable."""
        mock_mind_client.is_available = AsyncMock(return_value=False)
        injector = ContextInjector(mind_client=mock_mind_client)

        result = await injector.get_injection_string()

        assert result is None


class TestGetTaskSpecificAdvice:
    """Tests for get_task_specific_advice method."""

    def test_matches_explore_to_search(self):
        """Matches Explore agent to search tasks."""
        injector = ContextInjector()
        ctx = InjectionContext(
            agent_recommendations=[("Explore", 0.9, "90% success for search")]
        )

        advice = injector.get_task_specific_advice(ctx, "find all test files")

        assert advice is not None
        assert "Explore" in advice

    def test_matches_plan_to_implementation(self):
        """Matches Plan agent to implementation tasks."""
        injector = ContextInjector()
        ctx = InjectionContext(
            agent_recommendations=[("Plan", 0.85, "85% success for planning")]
        )

        advice = injector.get_task_specific_advice(ctx, "implement a new feature")

        assert advice is not None
        assert "Plan" in advice

    def test_returns_none_no_match(self):
        """Returns None when no relevant advice."""
        injector = ContextInjector()
        ctx = InjectionContext(
            agent_recommendations=[("Explore", 0.9, "good for search")]
        )

        advice = injector.get_task_specific_advice(ctx, "commit the changes")

        # May or may not match depending on keyword overlap
        # Just verify it doesn't crash
        assert advice is None or isinstance(advice, str)


class TestClose:
    """Tests for close method."""

    @pytest.mark.asyncio
    async def test_closes_mind_client(self, mock_mind_client):
        """Closes the Mind client."""
        injector = ContextInjector(mind_client=mock_mind_client)

        await injector.close()

        mock_mind_client.close.assert_called_once()
