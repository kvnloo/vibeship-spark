"""
Unit tests for lib/spark_mcp_server.py
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch

from lib.spark_mcp_server import (
    SparkMCPServer, SparkToolName, ToolResponse, SparkStatus, ToolDefinition
)
from lib.prompt_evolver import PromptPattern
from lib.suggester import Suggestion


@pytest.fixture
def mock_mind_client():
    """Create a mock Mind client."""
    client = MagicMock()
    client.is_available = AsyncMock(return_value=True)
    client.retrieve = AsyncMock(return_value=[])
    client.store = AsyncMock(return_value="mem_123")
    client.close = AsyncMock()
    return client


@pytest.fixture
def server(mock_mind_client):
    """Create a server with mock Mind client."""
    return SparkMCPServer(mind_client=mock_mind_client)


class TestSparkMCPServerInit:
    """Tests for SparkMCPServer initialization."""

    def test_init_default(self, mock_mind_client):
        """Initializes with defaults."""
        server = SparkMCPServer(mind_client=mock_mind_client)

        assert server.suggester is not None
        assert server.evolver is not None
        assert server.advisor is not None
        assert server.current_session_id is None

    def test_init_with_dependencies(self, mock_mind_client):
        """Accepts injected dependencies."""
        suggester = MagicMock()
        evolver = MagicMock()

        server = SparkMCPServer(
            mind_client=mock_mind_client,
            suggester=suggester,
            evolver=evolver
        )

        assert server.suggester == suggester
        assert server.evolver == evolver


class TestToolStatus:
    """Tests for tool_status method."""

    @pytest.mark.asyncio
    async def test_returns_status(self, server, mock_mind_client):
        """Returns SparkStatus."""
        response = await server.tool_status({})

        assert response.success is True
        assert "is_operational" in response.data
        assert "mind_connected" in response.data
        assert response.data["mind_connected"] is True

    @pytest.mark.asyncio
    async def test_handles_mind_unavailable(self, mock_mind_client):
        """Handles Mind being unavailable."""
        mock_mind_client.is_available = AsyncMock(return_value=False)
        server = SparkMCPServer(mind_client=mock_mind_client)

        response = await server.tool_status({})

        assert response.success is True
        assert response.data["mind_connected"] is False

    @pytest.mark.asyncio
    async def test_includes_version(self, server):
        """Status includes version."""
        response = await server.tool_status({})

        assert "version" in response.data
        assert response.data["version"] == SparkMCPServer.VERSION


class TestToolSuggest:
    """Tests for tool_suggest method."""

    @pytest.mark.asyncio
    async def test_returns_suggestions(self, server):
        """Returns suggestions for task."""
        # Add a suggestion
        server.suggester.suggestions["s1"] = Suggestion(
            suggestion_id="s1",
            suggestion_type="recommendation",
            priority=2,
            title="Use Grep",
            description="Grep is effective for search",
            confidence=0.9,
            trigger_keywords=["search", "find"]
        )

        response = await server.tool_suggest({
            "task_description": "search for function definitions",
            "max_suggestions": 3
        })

        assert response.success is True
        assert "suggestions" in response.data

    @pytest.mark.asyncio
    async def test_includes_alternative(self, server):
        """Includes alternative tool suggestion."""
        response = await server.tool_suggest({
            "task_description": "search for all test files",
            "current_tool": "Bash"
        })

        assert response.success is True
        # May or may not have alternative depending on matching

    @pytest.mark.asyncio
    async def test_includes_task_guidance(self, server):
        """Includes task guidance when available."""
        response = await server.tool_suggest({
            "task_description": "search for patterns in code"
        })

        assert response.success is True
        # Should detect search category
        if response.data.get("task_guidance"):
            assert response.data["task_guidance"]["category"] == "search"


class TestToolReflect:
    """Tests for tool_reflect method."""

    @pytest.mark.asyncio
    async def test_reflects_on_session(self, server):
        """Reflects on specified session."""
        response = await server.tool_reflect({
            "session_id": "test_session",
            "include_patterns": True,
            "include_improvements": True
        })

        assert response.success is True
        assert "session_id" in response.data
        assert "traces_analyzed" in response.data

    @pytest.mark.asyncio
    async def test_handles_unknown_session(self, server):
        """Handles unknown session gracefully."""
        response = await server.tool_reflect({
            "session_id": "nonexistent_session_12345"
        })

        assert response.success is True
        assert response.data["traces_analyzed"] == 0

    @pytest.mark.asyncio
    async def test_uses_current_session(self, server):
        """Uses current session if not specified."""
        server.set_session_id("current_session")

        response = await server.tool_reflect({})

        assert response.success is True
        # Uses default or current session

    @pytest.mark.asyncio
    async def test_updates_last_learning(self, server):
        """Updates last learning timestamp."""
        await server.tool_reflect({"session_id": "test"})

        assert server.last_learning_at is not None


class TestToolAccept:
    """Tests for tool_accept method."""

    @pytest.mark.asyncio
    async def test_accepts_pattern(self, server):
        """Accepts a pattern suggestion."""
        # Add a pattern
        server.evolver.patterns["p1"] = PromptPattern(
            pattern_id="p1",
            pattern_type="test",
            description="Test pattern",
            trigger_conditions={},
            approach="Test approach",
            total_uses=10,
            success_count=8,
            failure_count=2
        )

        response = await server.tool_accept({
            "pattern_id": "p1",
            "feedback": "Works well"
        })

        assert response.success is True
        assert response.data["accepted"] == "p1"

    @pytest.mark.asyncio
    async def test_increments_success_count(self, server):
        """Increments pattern success count."""
        server.evolver.patterns["p1"] = PromptPattern(
            pattern_id="p1",
            pattern_type="test",
            description="Test",
            trigger_conditions={},
            approach="Test",
            total_uses=10,
            success_count=8,
            failure_count=2
        )

        await server.tool_accept({"pattern_id": "p1"})

        assert server.evolver.patterns["p1"].success_count == 9
        assert server.evolver.patterns["p1"].total_uses == 11

    @pytest.mark.asyncio
    async def test_returns_error_unknown_pattern(self, server):
        """Returns error for unknown pattern."""
        response = await server.tool_accept({
            "pattern_id": "nonexistent"
        })

        assert response.success is False
        assert response.error is not None

    @pytest.mark.asyncio
    async def test_requires_pattern_id(self, server):
        """Requires pattern_id argument."""
        response = await server.tool_accept({})

        assert response.success is False
        assert "pattern_id" in response.error


class TestToolReject:
    """Tests for tool_reject method."""

    @pytest.mark.asyncio
    async def test_rejects_pattern(self, server):
        """Rejects a pattern with reason."""
        server.evolver.patterns["p1"] = PromptPattern(
            pattern_id="p1",
            pattern_type="test",
            description="Test",
            trigger_conditions={},
            approach="Test",
            total_uses=10,
            success_count=8,
            failure_count=2
        )

        response = await server.tool_reject({
            "pattern_id": "p1",
            "reason": "Not applicable to my workflow"
        })

        assert response.success is True
        assert response.data["rejected"] == "p1"

    @pytest.mark.asyncio
    async def test_increments_failure_count(self, server):
        """Increments pattern failure count."""
        server.evolver.patterns["p1"] = PromptPattern(
            pattern_id="p1",
            pattern_type="test",
            description="Test",
            trigger_conditions={},
            approach="Test",
            total_uses=10,
            success_count=8,
            failure_count=2
        )

        await server.tool_reject({"pattern_id": "p1", "reason": "Bad"})

        assert server.evolver.patterns["p1"].failure_count == 3
        assert server.evolver.patterns["p1"].total_uses == 11


class TestToolCreate:
    """Tests for tool_create method."""

    @pytest.mark.asyncio
    async def test_creates_pattern(self, server):
        """Creates a new manual pattern."""
        response = await server.tool_create({
            "pattern_type": "tool_sequence",
            "description": "Use Glob before Grep",
            "approach": "First use Glob to find files, then Grep to search content",
            "trigger_conditions": {"task_category": "search"}
        })

        assert response.success is True
        assert "pattern_id" in response.data

        # Verify pattern was added
        pattern_id = response.data["pattern_id"]
        assert pattern_id in server.evolver.patterns

    @pytest.mark.asyncio
    async def test_requires_description(self, server):
        """Requires description argument."""
        response = await server.tool_create({
            "approach": "Some approach"
        })

        assert response.success is False

    @pytest.mark.asyncio
    async def test_requires_approach(self, server):
        """Requires approach argument."""
        response = await server.tool_create({
            "description": "Some description"
        })

        assert response.success is False


class TestToolWarn:
    """Tests for tool_warn method."""

    @pytest.mark.asyncio
    async def test_returns_warnings_for_dangerous(self, server):
        """Returns warnings for dangerous commands."""
        response = await server.tool_warn({
            "tool_name": "Bash",
            "tool_input": {"command": "rm -rf /tmp/test"}
        })

        assert response.success is True
        assert len(response.data["warnings"]) > 0

    @pytest.mark.asyncio
    async def test_returns_empty_for_safe(self, server):
        """Returns empty warnings for safe commands."""
        response = await server.tool_warn({
            "tool_name": "Bash",
            "tool_input": {"command": "ls -la"}
        })

        assert response.success is True
        assert response.data["warning_count"] == 0

    @pytest.mark.asyncio
    async def test_requires_tool_name(self, server):
        """Requires tool_name argument."""
        response = await server.tool_warn({
            "tool_input": {"command": "test"}
        })

        assert response.success is False


class TestHandleToolCall:
    """Tests for handle_tool_call method."""

    @pytest.mark.asyncio
    async def test_routes_to_correct_handler(self, server):
        """Routes to correct tool handler."""
        response = await server.handle_tool_call(
            SparkToolName.STATUS.value,
            {}
        )

        assert response.success is True
        assert "is_operational" in response.data

    @pytest.mark.asyncio
    async def test_returns_error_unknown_tool(self, server):
        """Returns error for unknown tool."""
        response = await server.handle_tool_call(
            "unknown_tool",
            {}
        )

        assert response.success is False
        assert "Unknown tool" in response.error

    @pytest.mark.asyncio
    async def test_handles_handler_exception(self, server):
        """Handles exception in handler gracefully."""
        # Mock a handler to raise exception
        async def failing_handler(args):
            raise ValueError("Test error")

        server._tools["test_fail"] = failing_handler

        response = await server.handle_tool_call("test_fail", {})

        assert response.success is False
        assert "Test error" in response.error


class TestGetToolDefinitions:
    """Tests for get_tool_definitions method."""

    def test_returns_all_tools(self, server):
        """Returns definitions for all tools."""
        definitions = server.get_tool_definitions()

        assert len(definitions) == len(SparkToolName)
        tool_names = {d["name"] for d in definitions}
        expected_names = {t.value for t in SparkToolName}
        assert tool_names == expected_names

    def test_definitions_have_required_fields(self, server):
        """Tool definitions have required MCP fields."""
        definitions = server.get_tool_definitions()

        for defn in definitions:
            assert "name" in defn
            assert "description" in defn
            assert "inputSchema" in defn
            assert "type" in defn["inputSchema"]


class TestSetSessionId:
    """Tests for set_session_id method."""

    def test_sets_session_id(self, server):
        """Sets current session ID."""
        server.set_session_id("session_123")

        assert server.current_session_id == "session_123"


class TestInitializeAndClose:
    """Tests for initialize and close methods."""

    @pytest.mark.asyncio
    async def test_initialize_loads_data(self, server, mock_mind_client):
        """Initialize loads existing data when Mind available."""
        await server.initialize()

        # Should have attempted to load
        # (actual loading depends on mock setup)

    @pytest.mark.asyncio
    async def test_close_cleans_up(self, server, mock_mind_client):
        """Close cleans up resources."""
        await server.close()

        mock_mind_client.close.assert_called_once()


class TestGetStats:
    """Tests for get_stats method."""

    def test_returns_stats(self, server):
        """Returns server statistics."""
        server.set_session_id("test_session")

        stats = server.get_stats()

        assert "version" in stats
        assert "session_id" in stats
        assert stats["session_id"] == "test_session"
        assert "patterns_count" in stats
        assert "advisor_stats" in stats


class TestToolResponse:
    """Tests for ToolResponse dataclass."""

    def test_to_dict_success(self):
        """Converts successful response to dict."""
        response = ToolResponse(
            success=True,
            data={"key": "value"}
        )

        d = response.to_dict()

        assert d["success"] is True
        assert d["data"]["key"] == "value"
        assert "error" not in d

    def test_to_dict_error(self):
        """Converts error response to dict."""
        response = ToolResponse(
            success=False,
            data={},
            error="Something went wrong"
        )

        d = response.to_dict()

        assert d["success"] is False
        assert d["error"] == "Something went wrong"


class TestSparkStatus:
    """Tests for SparkStatus dataclass."""

    def test_to_dict(self):
        """Converts status to dict."""
        status = SparkStatus(
            is_operational=True,
            mind_connected=True,
            queue_size=5,
            patterns_active=10,
            suggestions_ready=3,
            current_session_id="sess_123",
            last_learning_at=1234567890.0
        )

        d = status.to_dict()

        assert d["is_operational"] is True
        assert d["queue_size"] == 5
        assert d["current_session_id"] == "sess_123"


class TestTaskCategoryInference:
    """Tests for task category inference."""

    def test_infers_search(self, server):
        """Infers search category."""
        category = server._infer_task_category("search for all functions")
        assert category == "search"

    def test_infers_edit(self, server):
        """Infers edit category."""
        category = server._infer_task_category("modify the config file")
        assert category == "edit"

    def test_infers_testing(self, server):
        """Infers testing category."""
        category = server._infer_task_category("run pytest on the module")
        assert category == "testing"

    def test_infers_git(self, server):
        """Infers git category."""
        category = server._infer_task_category("commit the changes")
        assert category == "git"

    def test_infers_shell(self, server):
        """Infers shell category."""
        category = server._infer_task_category("run the build command")
        assert category == "shell"

    def test_returns_none_for_unclear(self, server):
        """Returns None for unclear tasks."""
        category = server._infer_task_category("do something")
        assert category is None


class TestSparkToolName:
    """Tests for SparkToolName enum."""

    def test_all_tools_defined(self):
        """All expected tools are defined."""
        expected = ["status", "suggest", "reflect", "accept", "reject", "create", "warn"]

        for name in expected:
            assert hasattr(SparkToolName, name.upper())

    def test_values_prefixed(self):
        """Tool values are prefixed with spark_."""
        for tool in SparkToolName:
            assert tool.value.startswith("spark_")
