"""
Unit tests for lib/realtime_advisor.py
"""

import pytest
from unittest.mock import MagicMock, AsyncMock

from lib.realtime_advisor import (
    RealTimeAdvisor, Warning, RecoverySuggestion, TaskGuidance
)


@pytest.fixture
def advisor():
    """Create a default advisor."""
    return RealTimeAdvisor()


@pytest.fixture
def advisor_with_mocks():
    """Create advisor with mock dependencies."""
    suggester = MagicMock()
    evolver = MagicMock()
    learner = MagicMock()
    return RealTimeAdvisor(suggester, evolver, learner)


class TestRealTimeAdvisorInit:
    """Tests for RealTimeAdvisor initialization."""

    def test_init_default(self):
        """Initializes with defaults."""
        advisor = RealTimeAdvisor()

        assert advisor.suggester is None
        assert advisor.evolver is None
        assert advisor.learner is None
        assert advisor.warning_count == 0

    def test_init_with_dependencies(self):
        """Accepts injected dependencies."""
        suggester = MagicMock()
        evolver = MagicMock()

        advisor = RealTimeAdvisor(suggester=suggester, evolver=evolver)

        assert advisor.suggester == suggester
        assert advisor.evolver == evolver


class TestPreToolCheckBash:
    """Tests for pre_tool_check with Bash commands."""

    def test_warns_on_rm_rf(self, advisor):
        """Warns about rm -rf command."""
        warning = advisor.pre_tool_check(
            "Bash",
            {"command": "rm -rf /tmp/old_files"}
        )

        assert warning is not None
        assert warning.severity == "error"
        assert "rm -rf" in warning.title.lower()

    def test_warns_on_sudo(self, advisor):
        """Warns about sudo command."""
        warning = advisor.pre_tool_check(
            "Bash",
            {"command": "sudo apt update"}
        )

        assert warning is not None
        assert warning.severity == "info"

    def test_warns_on_git_push_force(self, advisor):
        """Warns about force push."""
        warning = advisor.pre_tool_check(
            "Bash",
            {"command": "git push -f origin main"}
        )

        assert warning is not None
        assert warning.severity == "warning"

    def test_warns_on_drop_table(self, advisor):
        """Warns about SQL DROP TABLE."""
        warning = advisor.pre_tool_check(
            "Bash",
            {"command": "psql -c 'DROP TABLE users'"}
        )

        assert warning is not None
        assert warning.severity == "error"

    def test_warns_on_long_running_find(self, advisor):
        """Warns about potentially long find command."""
        warning = advisor.pre_tool_check(
            "Bash",
            {"command": "find / -name '*.py'"}
        )

        assert warning is not None
        assert warning.severity == "info"
        assert "long" in warning.title.lower()

    def test_no_warning_safe_command(self, advisor):
        """No warning for safe commands."""
        warning = advisor.pre_tool_check(
            "Bash",
            {"command": "ls -la"}
        )

        assert warning is None

    def test_no_warning_empty_command(self, advisor):
        """No warning for empty command."""
        warning = advisor.pre_tool_check(
            "Bash",
            {"command": ""}
        )

        assert warning is None

    def test_no_duplicate_warnings(self, advisor):
        """Same pattern doesn't warn twice in session."""
        # First warning
        warning1 = advisor.pre_tool_check(
            "Bash",
            {"command": "sudo apt update"}
        )

        # Second time - should not warn
        warning2 = advisor.pre_tool_check(
            "Bash",
            {"command": "sudo apt upgrade"}
        )

        assert warning1 is not None
        assert warning2 is None


class TestPreToolCheckFile:
    """Tests for pre_tool_check with file operations."""

    def test_warns_on_env_file(self, advisor):
        """Warns about .env file modification."""
        warning = advisor.pre_tool_check(
            "Edit",
            {"file_path": "/project/.env"}
        )

        assert warning is not None
        assert warning.severity == "warning"
        assert "sensitive" in warning.title.lower()

    def test_warns_on_credentials_file(self, advisor):
        """Warns about credentials file."""
        warning = advisor.pre_tool_check(
            "Write",
            {"file_path": "/config/credentials.json"}
        )

        assert warning is not None
        assert "credential" in warning.pattern_match

    def test_warns_on_private_key(self, advisor):
        """Warns about private key file."""
        warning = advisor.pre_tool_check(
            "Edit",
            {"file_path": "~/.ssh/id_rsa"}
        )

        assert warning is not None

    def test_warns_on_system_path(self, advisor):
        """Warns about system path modification."""
        warning = advisor.pre_tool_check(
            "Write",
            {"file_path": "/etc/hosts"}
        )

        assert warning is not None
        assert "system" in warning.title.lower()

    def test_no_warning_normal_file(self, advisor):
        """No warning for normal files."""
        warning = advisor.pre_tool_check(
            "Edit",
            {"file_path": "/project/src/main.py"}
        )

        assert warning is None


class TestPreToolCheckTask:
    """Tests for pre_tool_check with Task operations."""

    def test_warns_on_short_prompt(self, advisor):
        """Warns about very short task prompts."""
        warning = advisor.pre_tool_check(
            "Task",
            {"prompt": "fix bug"}
        )

        assert warning is not None
        assert warning.severity == "info"
        assert "short" in warning.title.lower()

    def test_no_warning_detailed_prompt(self, advisor):
        """No warning for detailed prompts."""
        warning = advisor.pre_tool_check(
            "Task",
            {"prompt": "Search for all Python files that contain the function 'process_data' and read their contents"}
        )

        assert warning is None


class TestSuggestRecovery:
    """Tests for suggest_recovery method."""

    def test_suggests_recovery_for_not_found(self, advisor):
        """Suggests recovery for file not found errors."""
        recovery = advisor.suggest_recovery(
            failed_tool="Read",
            error_message="File not found: /nonexistent/path.py"
        )

        assert recovery is not None
        assert recovery.error_category == "not_found"
        assert "Glob" in recovery.alternative_tools
        assert recovery.confidence > 0

    def test_suggests_recovery_for_permission(self, advisor):
        """Suggests recovery for permission errors."""
        recovery = advisor.suggest_recovery(
            failed_tool="Bash",
            error_message="Permission denied: cannot write to /etc/config"
        )

        assert recovery is not None
        assert recovery.error_category == "permission"

    def test_suggests_recovery_for_timeout(self, advisor):
        """Suggests recovery for timeout errors."""
        recovery = advisor.suggest_recovery(
            failed_tool="Bash",
            error_message="Command timed out after 120 seconds"
        )

        assert recovery is not None
        assert recovery.error_category == "timeout"
        assert "smaller" in recovery.recovery_approach.lower() or "chunk" in recovery.recovery_approach.lower()

    def test_suggests_recovery_for_syntax(self, advisor):
        """Suggests recovery for syntax errors."""
        recovery = advisor.suggest_recovery(
            failed_tool="Bash",
            error_message="SyntaxError: invalid syntax at line 10"
        )

        assert recovery is not None
        assert recovery.error_category == "syntax"

    def test_suggests_recovery_for_network(self, advisor):
        """Suggests recovery for network errors."""
        recovery = advisor.suggest_recovery(
            failed_tool="WebFetch",
            error_message="Connection refused: could not reach server"
        )

        assert recovery is not None
        assert recovery.error_category == "network"

    def test_returns_none_for_unknown_error(self, advisor):
        """Returns None for unrecognized errors."""
        recovery = advisor.suggest_recovery(
            failed_tool="Task",
            error_message="Some completely unknown error type xyz123"
        )

        # Returns None for "other" category
        assert recovery is None

    def test_uses_evolver_pattern_if_available(self, advisor_with_mocks):
        """Uses learned pattern if available."""
        # Set up mock pattern
        mock_pattern = MagicMock()
        mock_pattern.success_rate = 0.85
        mock_pattern.approach = "Use specific search pattern"
        mock_pattern.tool_sequence = ["Grep", "Read"]

        advisor_with_mocks.evolver.get_pattern_for_task.return_value = mock_pattern

        recovery = advisor_with_mocks.suggest_recovery(
            failed_tool="Read",
            error_message="File not found"
        )

        assert recovery is not None
        assert recovery.confidence == 0.85


class TestSuggestAlternative:
    """Tests for suggest_alternative method."""

    def test_suggests_grep_for_bash_search(self, advisor):
        """Suggests Grep for search tasks using Bash."""
        alternative = advisor.suggest_alternative(
            current_tool="Bash",
            task_description="search for function definitions"
        )

        assert alternative is not None
        assert "Grep" in alternative

    def test_suggests_glob_for_bash_find(self, advisor):
        """Suggests Glob for find tasks using Bash."""
        alternative = advisor.suggest_alternative(
            current_tool="Bash",
            task_description="find all test files"
        )

        assert alternative is not None
        assert "Glob" in alternative

    def test_suggests_edit_for_write_modify(self, advisor):
        """Suggests Edit for modify tasks using Write."""
        alternative = advisor.suggest_alternative(
            current_tool="Write",
            task_description="modify the config file"
        )

        assert alternative is not None
        assert "Edit" in alternative

    def test_no_alternative_for_optimal_tool(self, advisor):
        """No alternative when tool is already optimal."""
        alternative = advisor.suggest_alternative(
            current_tool="Grep",
            task_description="search for function definitions"
        )

        assert alternative is None


class TestGetTaskGuidance:
    """Tests for get_task_guidance method."""

    def test_returns_search_guidance(self, advisor):
        """Returns guidance for search tasks."""
        guidance = advisor.get_task_guidance("search")

        assert guidance is not None
        assert guidance.task_category == "search"
        assert len(guidance.tips) > 0
        assert len(guidance.recommended_tools) > 0
        assert "Grep" in guidance.recommended_tools

    def test_returns_edit_guidance(self, advisor):
        """Returns guidance for edit tasks."""
        guidance = advisor.get_task_guidance("edit")

        assert guidance is not None
        assert "Read" in guidance.recommended_tools

    def test_returns_testing_guidance(self, advisor):
        """Returns guidance for testing tasks."""
        guidance = advisor.get_task_guidance("testing")

        assert guidance is not None
        assert len(guidance.common_pitfalls) > 0

    def test_returns_git_guidance(self, advisor):
        """Returns guidance for git tasks."""
        guidance = advisor.get_task_guidance("git")

        assert guidance is not None

    def test_returns_none_for_unknown(self, advisor):
        """Returns None for unknown task category."""
        guidance = advisor.get_task_guidance("unknown_category")

        assert guidance is None


class TestGetAllGuidance:
    """Tests for get_all_guidance method."""

    def test_returns_all_categories(self, advisor):
        """Returns guidance for all categories."""
        all_guidance = advisor.get_all_guidance()

        assert "search" in all_guidance
        assert "edit" in all_guidance
        assert "testing" in all_guidance
        assert "git" in all_guidance
        assert "shell" in all_guidance


class TestWarningHistory:
    """Tests for warning history management."""

    def test_records_warnings(self, advisor):
        """Records warnings in history."""
        advisor.pre_tool_check("Bash", {"command": "rm -rf /tmp/test"})

        warnings = advisor.get_recent_warnings()

        assert len(warnings) >= 1

    def test_limits_warning_history(self, advisor):
        """Limits warning history size."""
        # Generate many warnings
        for i in range(60):
            # Clear history to allow new warnings
            advisor._warning_history.clear()
            advisor.pre_tool_check("Bash", {"command": f"sudo command_{i}"})

        # Should be limited
        warnings = advisor.get_recent_warnings(limit=100)
        assert len(warnings) <= 50


class TestClearSession:
    """Tests for clear_session method."""

    def test_clears_warnings(self, advisor):
        """Clears session warnings."""
        advisor.pre_tool_check("Bash", {"command": "sudo test"})
        advisor.clear_session()

        warnings = advisor.get_recent_warnings()
        assert len(warnings) == 0

    def test_allows_new_warnings_after_clear(self, advisor):
        """Allows same warnings after clear."""
        advisor.pre_tool_check("Bash", {"command": "sudo test"})
        advisor.clear_session()

        # Should warn again after clear
        warning = advisor.pre_tool_check("Bash", {"command": "sudo test2"})
        assert warning is not None


class TestGetStats:
    """Tests for get_stats method."""

    def test_returns_stats(self, advisor):
        """Returns advisor statistics."""
        advisor.pre_tool_check("Bash", {"command": "sudo test"})

        stats = advisor.get_stats()

        assert "total_warnings" in stats
        assert "recent_warnings" in stats
        assert stats["total_warnings"] >= 1


class TestWarningDataclass:
    """Tests for Warning dataclass."""

    def test_creation(self):
        """Warning creates with required fields."""
        warning = Warning(
            warning_id="w1",
            severity="warning",
            title="Test Warning",
            description="This is a test"
        )

        assert warning.warning_id == "w1"
        assert warning.severity == "warning"


class TestRecoverySuggestionDataclass:
    """Tests for RecoverySuggestion dataclass."""

    def test_creation(self):
        """RecoverySuggestion creates with required fields."""
        suggestion = RecoverySuggestion(
            suggestion_id="r1",
            failed_tool="Read",
            error_category="not_found",
            recovery_approach="Use Glob to find the file"
        )

        assert suggestion.failed_tool == "Read"
        assert suggestion.confidence == 0.5  # default


class TestTaskGuidanceDataclass:
    """Tests for TaskGuidance dataclass."""

    def test_creation(self):
        """TaskGuidance creates with required fields."""
        guidance = TaskGuidance(
            task_category="search",
            tips=["Tip 1", "Tip 2"],
            recommended_tools=["Grep", "Glob"],
            common_pitfalls=["Pitfall 1"]
        )

        assert guidance.task_category == "search"
        assert len(guidance.tips) == 2


class TestErrorCategorization:
    """Tests for error categorization."""

    def test_categorizes_not_found(self, advisor):
        """Correctly categorizes not found errors."""
        category = advisor._categorize_error("File not found: /test.py")
        assert category == "not_found"

        category = advisor._categorize_error("No such file or directory")
        assert category == "not_found"

    def test_categorizes_permission(self, advisor):
        """Correctly categorizes permission errors."""
        category = advisor._categorize_error("Permission denied")
        assert category == "permission"

        category = advisor._categorize_error("Access forbidden")
        assert category == "permission"

    def test_categorizes_timeout(self, advisor):
        """Correctly categorizes timeout errors."""
        category = advisor._categorize_error("Connection timed out")
        assert category == "timeout"

    def test_categorizes_syntax(self, advisor):
        """Correctly categorizes syntax errors."""
        category = advisor._categorize_error("SyntaxError: unexpected token")
        assert category == "syntax"

    def test_categorizes_other(self, advisor):
        """Categorizes unknown errors as other."""
        category = advisor._categorize_error("Some random error message")
        assert category == "other"
