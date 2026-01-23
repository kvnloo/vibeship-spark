"""
Spark RealTime Advisor: Provides real-time guidance during Claude Code sessions.

Capabilities:
- Pre-tool warnings: Detect potential issues before tool execution
- Post-failure recovery: Suggest recovery strategies after failures
- Mid-task recommendations: Provide alternative approaches
- Task guidance: Tips for specific task categories
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any, Set
from datetime import datetime

from .suggester import Suggester, Suggestion
from .prompt_evolver import PromptEvolver, PromptPattern
from .learner import SparkLearner


@dataclass
class Warning:
    """A warning about a potential issue."""
    warning_id: str
    severity: str  # "info", "warning", "error"
    title: str
    description: str
    suggestion: Optional[str] = None
    tool_name: Optional[str] = None
    pattern_match: Optional[str] = None


@dataclass
class RecoverySuggestion:
    """A suggestion for recovering from a failure."""
    suggestion_id: str
    failed_tool: str
    error_category: str
    recovery_approach: str
    alternative_tools: List[str] = field(default_factory=list)
    confidence: float = 0.5


@dataclass
class TaskGuidance:
    """Guidance for a specific task category."""
    task_category: str
    tips: List[str]
    recommended_tools: List[str]
    common_pitfalls: List[str]


class RealTimeAdvisor:
    """
    Provides real-time guidance during Claude Code sessions.

    Capabilities:
    - Pre-tool warnings
    - Post-failure recovery suggestions
    - Mid-task recommendations
    """

    # Tools that commonly need warnings
    WARN_TOOLS = {"Bash", "Write", "Edit", "Task"}

    # Dangerous command patterns
    DANGEROUS_PATTERNS = {
        "rm -rf": ("error", "Recursive force delete can cause data loss"),
        "rm -r": ("warning", "Recursive delete - verify path carefully"),
        "> /": ("error", "Redirecting to root path can corrupt system"),
        "chmod 777": ("warning", "Setting world-writable permissions is insecure"),
        "sudo": ("info", "Using elevated privileges"),
        "DROP TABLE": ("error", "SQL table drop is destructive"),
        "DELETE FROM": ("warning", "SQL delete without WHERE affects all rows"),
        "git push -f": ("warning", "Force push can overwrite remote history"),
        "git reset --hard": ("warning", "Hard reset discards uncommitted changes"),
        "--no-verify": ("info", "Skipping git hooks"),
        "eval(": ("warning", "eval() can execute arbitrary code"),
        "exec(": ("warning", "exec() can execute arbitrary code"),
    }

    # Long-running command patterns
    LONG_RUNNING_PATTERNS = [
        "find /",
        "grep -r /",
        "npm install",
        "pip install",
        "docker build",
        "cargo build",
        "make",
        "mvn",
        "gradle",
    ]

    # Error category to recovery mapping
    ERROR_RECOVERY = {
        "not_found": {
            "approach": "Use Glob to search for the file with similar names or patterns",
            "tools": ["Glob", "Grep"],
            "confidence": 0.8
        },
        "permission": {
            "approach": "Check file permissions or try alternative access methods",
            "tools": ["Bash", "Read"],
            "confidence": 0.6
        },
        "timeout": {
            "approach": "Break operation into smaller chunks or increase timeout",
            "tools": ["Bash", "Task"],
            "confidence": 0.7
        },
        "syntax": {
            "approach": "Validate syntax before execution, check for typos",
            "tools": ["Read", "Edit"],
            "confidence": 0.75
        },
        "conflict": {
            "approach": "Check current state and resolve conflicts before retry",
            "tools": ["Read", "Bash"],
            "confidence": 0.65
        },
        "network": {
            "approach": "Check connectivity, retry with exponential backoff",
            "tools": ["Bash"],
            "confidence": 0.5
        },
    }

    # Task category guidance
    TASK_GUIDANCE = {
        "search": TaskGuidance(
            task_category="search",
            tips=[
                "Use Grep for content search, Glob for file patterns",
                "Start with specific patterns, broaden if needed",
                "Limit results to avoid overwhelming output",
            ],
            recommended_tools=["Grep", "Glob", "Read"],
            common_pitfalls=[
                "Searching too broadly (e.g., entire filesystem)",
                "Not using appropriate file type filters",
                "Case sensitivity mismatches",
            ]
        ),
        "edit": TaskGuidance(
            task_category="edit",
            tips=[
                "Always Read the file first to understand context",
                "Make minimal, focused changes",
                "Verify edits by reading after",
            ],
            recommended_tools=["Read", "Edit", "Write"],
            common_pitfalls=[
                "Editing without reading first",
                "Making too many changes at once",
                "Not preserving file formatting",
            ]
        ),
        "testing": TaskGuidance(
            task_category="testing",
            tips=[
                "Run specific tests before full suite",
                "Check test output for specific failures",
                "Use verbose mode for debugging",
            ],
            recommended_tools=["Bash", "Read"],
            common_pitfalls=[
                "Running entire test suite for one change",
                "Not reading error messages carefully",
                "Missing test dependencies",
            ]
        ),
        "git": TaskGuidance(
            task_category="git",
            tips=[
                "Check status before committing",
                "Review diff before pushing",
                "Use descriptive commit messages",
            ],
            recommended_tools=["Bash"],
            common_pitfalls=[
                "Committing sensitive files",
                "Force pushing to shared branches",
                "Not pulling before pushing",
            ]
        ),
        "shell": TaskGuidance(
            task_category="shell",
            tips=[
                "Use absolute paths when possible",
                "Quote arguments with spaces",
                "Check command exists before running",
            ],
            recommended_tools=["Bash"],
            common_pitfalls=[
                "Running destructive commands without verification",
                "Not handling command failures",
                "Assuming current directory",
            ]
        ),
    }

    def __init__(
        self,
        suggester: Optional[Suggester] = None,
        evolver: Optional[PromptEvolver] = None,
        learner: Optional[SparkLearner] = None
    ):
        self.suggester = suggester
        self.evolver = evolver
        self.learner = learner
        self.recent_warnings: List[Warning] = []
        self.warning_count = 0
        self._warning_history: Set[str] = set()  # Avoid duplicate warnings

    def pre_tool_check(
        self,
        tool_name: str,
        tool_input: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> Optional[Warning]:
        """
        Check before tool execution for potential issues.

        Args:
            tool_name: Tool about to be used
            tool_input: Planned input to tool
            context: Additional context

        Returns:
            Warning if issue detected, None otherwise
        """
        warning = None

        if tool_name == "Bash":
            warning = self._check_bash_command(tool_input.get("command", ""))
        elif tool_name in ("Write", "Edit"):
            warning = self._check_file_operation(tool_name, tool_input.get("file_path", ""))
        elif tool_name == "Task":
            warning = self._check_task_operation(tool_input)

        if warning:
            self._record_warning(warning)

        return warning

    def _check_bash_command(self, command: str) -> Optional[Warning]:
        """Check Bash command for common issues."""
        if not command:
            return None

        command_lower = command.lower()

        # Check dangerous patterns
        for pattern, (severity, description) in self.DANGEROUS_PATTERNS.items():
            if pattern.lower() in command_lower:
                warning_id = f"bash_{pattern.replace(' ', '_')}_{self.warning_count}"
                self.warning_count += 1

                # Don't warn twice for same pattern in session
                pattern_key = f"bash:{pattern}"
                if pattern_key in self._warning_history:
                    return None
                self._warning_history.add(pattern_key)

                return Warning(
                    warning_id=warning_id,
                    severity=severity,
                    title=f"Potentially dangerous: {pattern}",
                    description=description,
                    suggestion="Verify this is intentional and the path is correct",
                    tool_name="Bash",
                    pattern_match=pattern
                )

        # Check long-running patterns
        for pattern in self.LONG_RUNNING_PATTERNS:
            if pattern.lower() in command_lower:
                warning_id = f"bash_long_{self.warning_count}"
                self.warning_count += 1

                pattern_key = f"bash_long:{pattern}"
                if pattern_key in self._warning_history:
                    return None
                self._warning_history.add(pattern_key)

                return Warning(
                    warning_id=warning_id,
                    severity="info",
                    title="Potentially long-running command",
                    description=f"'{pattern}' may take a while to complete",
                    suggestion="Consider setting a timeout or running in background",
                    tool_name="Bash",
                    pattern_match=pattern
                )

        return None

    def _check_file_operation(
        self,
        tool_name: str,
        file_path: str
    ) -> Optional[Warning]:
        """Check file operations for issues."""
        if not file_path:
            return None

        warnings = []

        # Check for sensitive paths
        sensitive_patterns = [
            (".env", "Environment file may contain secrets"),
            ("credentials", "File may contain credentials"),
            ("secret", "File may contain secrets"),
            ("password", "File may contain passwords"),
            (".pem", "Private key file"),
            (".key", "Key file"),
            ("id_rsa", "SSH private key"),
        ]

        path_lower = file_path.lower()

        for pattern, description in sensitive_patterns:
            if pattern in path_lower:
                warning_id = f"file_{pattern}_{self.warning_count}"
                self.warning_count += 1

                pattern_key = f"file:{pattern}"
                if pattern_key in self._warning_history:
                    continue
                self._warning_history.add(pattern_key)

                return Warning(
                    warning_id=warning_id,
                    severity="warning",
                    title=f"Sensitive file: {pattern}",
                    description=description,
                    suggestion="Ensure this file should be modified and won't be committed",
                    tool_name=tool_name,
                    pattern_match=pattern
                )

        # Check for system paths
        system_paths = ["/etc/", "/usr/", "/bin/", "/sbin/", "C:\\Windows\\", "C:\\Program Files\\"]
        for sys_path in system_paths:
            if file_path.startswith(sys_path):
                warning_id = f"file_system_{self.warning_count}"
                self.warning_count += 1

                return Warning(
                    warning_id=warning_id,
                    severity="warning",
                    title="System path modification",
                    description=f"Modifying files in {sys_path} affects the system",
                    suggestion="Verify you have permission and this is intentional",
                    tool_name=tool_name,
                    pattern_match=sys_path
                )

        return None

    def _check_task_operation(self, tool_input: Dict[str, Any]) -> Optional[Warning]:
        """Check Task operations for issues."""
        prompt = tool_input.get("prompt", "")

        # Check for very broad prompts
        if len(prompt) < 20:
            return Warning(
                warning_id=f"task_short_{self.warning_count}",
                severity="info",
                title="Short task prompt",
                description="Very short prompts may lead to ambiguous results",
                suggestion="Provide more context for better agent performance",
                tool_name="Task"
            )

        return None

    def suggest_recovery(
        self,
        failed_tool: str,
        error_message: str,
        context: Optional[Dict[str, Any]] = None
    ) -> Optional[RecoverySuggestion]:
        """
        Suggest recovery after a tool failure.

        Args:
            failed_tool: Tool that failed
            error_message: Error that occurred
            context: Additional context

        Returns:
            RecoverySuggestion if available
        """
        # Categorize the error
        error_category = self._categorize_error(error_message)

        # Get recovery strategy
        recovery = self.ERROR_RECOVERY.get(error_category)

        if not recovery:
            return None

        # Check if we have learned patterns for this error
        if self.evolver:
            pattern = self.evolver.get_pattern_for_task(f"error_{error_category}")
            if pattern and pattern.success_rate > 0.6:
                return RecoverySuggestion(
                    suggestion_id=f"recovery_{error_category}_{failed_tool}",
                    failed_tool=failed_tool,
                    error_category=error_category,
                    recovery_approach=pattern.approach,
                    alternative_tools=pattern.tool_sequence or recovery["tools"],
                    confidence=pattern.success_rate
                )

        return RecoverySuggestion(
            suggestion_id=f"recovery_{error_category}_{failed_tool}",
            failed_tool=failed_tool,
            error_category=error_category,
            recovery_approach=recovery["approach"],
            alternative_tools=recovery["tools"],
            confidence=recovery["confidence"]
        )

    def _categorize_error(self, error: str) -> str:
        """Categorize an error message."""
        error_lower = error.lower()

        if any(x in error_lower for x in ["not found", "no such", "missing", "does not exist"]):
            return "not_found"
        elif any(x in error_lower for x in ["permission", "denied", "access", "forbidden"]):
            return "permission"
        elif any(x in error_lower for x in ["timeout", "timed out", "took too long"]):
            return "timeout"
        elif any(x in error_lower for x in ["syntax", "parse", "invalid", "unexpected token"]):
            return "syntax"
        elif any(x in error_lower for x in ["conflict", "already exists", "duplicate"]):
            return "conflict"
        elif any(x in error_lower for x in ["network", "connection", "refused", "unreachable"]):
            return "network"

        return "other"

    def suggest_alternative(
        self,
        current_tool: str,
        task_description: str
    ) -> Optional[str]:
        """
        Suggest alternative tool for task.

        Args:
            current_tool: Tool currently being considered
            task_description: What user is trying to do

        Returns:
            Alternative suggestion if better option exists
        """
        task_lower = task_description.lower()

        # Tool effectiveness hints
        alternatives = {
            "Bash": {
                "search": ("Grep", "Grep is more efficient for searching file contents"),
                "find": ("Glob", "Glob is faster for finding files by pattern"),
                "read": ("Read", "Read tool is designed for viewing files"),
            },
            "Read": {
                "search": ("Grep", "Grep can search across many files efficiently"),
            },
            "Write": {
                "modify": ("Edit", "Edit is better for modifying existing files"),
                "change": ("Edit", "Edit preserves file structure better"),
            },
        }

        tool_alternatives = alternatives.get(current_tool, {})

        for keyword, (alt_tool, reason) in tool_alternatives.items():
            if keyword in task_lower:
                # Check learned effectiveness if available
                if self.learner:
                    ranking = self.learner.get_tool_ranking()
                    alt_rank = next((r for t, r in ranking if t == alt_tool), 0)
                    curr_rank = next((r for t, r in ranking if t == current_tool), 0)

                    if alt_rank > curr_rank:
                        return f"Consider using {alt_tool}: {reason}"

                return f"Consider using {alt_tool}: {reason}"

        return None

    def get_task_guidance(self, task_category: str) -> Optional[TaskGuidance]:
        """
        Get guidance tips for a task category.

        Args:
            task_category: Type of task (search, edit, etc.)

        Returns:
            TaskGuidance with tips, tools, and pitfalls
        """
        return self.TASK_GUIDANCE.get(task_category)

    def get_all_guidance(self) -> Dict[str, TaskGuidance]:
        """Get all available task guidance."""
        return self.TASK_GUIDANCE.copy()

    def _record_warning(self, warning: Warning):
        """Record a warning for history."""
        self.recent_warnings.append(warning)
        # Keep only last 50 warnings
        if len(self.recent_warnings) > 50:
            self.recent_warnings = self.recent_warnings[-50:]

    def get_recent_warnings(self, limit: int = 10) -> List[Warning]:
        """Get recent warnings."""
        return self.recent_warnings[-limit:]

    def clear_session(self):
        """Clear session-specific data."""
        self.recent_warnings = []
        self._warning_history.clear()

    def get_stats(self) -> Dict[str, Any]:
        """Get advisor statistics."""
        return {
            "total_warnings": self.warning_count,
            "recent_warnings": len(self.recent_warnings),
            "warning_categories": len(self._warning_history),
            "has_suggester": self.suggester is not None,
            "has_evolver": self.evolver is not None,
            "has_learner": self.learner is not None,
        }
