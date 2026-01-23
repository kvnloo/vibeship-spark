"""
Spark MCP Server: MCP protocol server for real-time Spark integration.

Provides tools for:
- Querying Spark status
- Getting suggestions mid-session
- Triggering reflection
- Managing patterns
- Pre-tool warnings

This can be run as a standalone server or integrated into the existing MCP infrastructure.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any, Callable
from enum import Enum
from datetime import datetime
import asyncio
import json

from .mind_client import MindClient
from .suggester import Suggester, Suggestion
from .prompt_evolver import PromptEvolver, PromptPattern
from .realtime_advisor import RealTimeAdvisor, Warning, RecoverySuggestion
from .queue import SparkQueue


class SparkToolName(Enum):
    """Available Spark MCP tools."""
    STATUS = "spark_status"
    SUGGEST = "spark_suggest"
    REFLECT = "spark_reflect"
    ACCEPT = "spark_accept"
    REJECT = "spark_reject"
    CREATE = "spark_create"
    WARN = "spark_warn"


@dataclass
class ToolResponse:
    """Response from a Spark MCP tool."""
    success: bool
    data: Dict[str, Any]
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        result = {
            "success": self.success,
            "data": self.data
        }
        if self.error:
            result["error"] = self.error
        return result


@dataclass
class SparkStatus:
    """Current Spark system status."""
    is_operational: bool
    mind_connected: bool
    queue_size: int
    patterns_active: int
    suggestions_ready: int
    current_session_id: Optional[str]
    last_learning_at: Optional[float]
    version: str = "1.0.0"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "is_operational": self.is_operational,
            "mind_connected": self.mind_connected,
            "queue_size": self.queue_size,
            "patterns_active": self.patterns_active,
            "suggestions_ready": self.suggestions_ready,
            "current_session_id": self.current_session_id,
            "last_learning_at": self.last_learning_at,
            "version": self.version
        }


@dataclass
class ToolDefinition:
    """MCP tool definition."""
    name: str
    description: str
    input_schema: Dict[str, Any]


class SparkMCPServer:
    """
    MCP Server for Spark integration with Claude Code.

    Provides tools for:
    - Querying Spark status
    - Getting suggestions mid-session
    - Triggering reflection
    - Managing patterns
    - Pre-tool warnings
    """

    VERSION = "1.0.0"

    def __init__(
        self,
        mind_client: Optional[MindClient] = None,
        suggester: Optional[Suggester] = None,
        evolver: Optional[PromptEvolver] = None,
        advisor: Optional[RealTimeAdvisor] = None
    ):
        self.mind = mind_client or MindClient()
        self.suggester = suggester or Suggester(self.mind)
        self.evolver = evolver or PromptEvolver(self.mind)
        self.advisor = advisor or RealTimeAdvisor(self.suggester, self.evolver, None)
        self.queue = SparkQueue()

        self.current_session_id: Optional[str] = None
        self.last_learning_at: Optional[float] = None
        self._tools: Dict[str, Callable] = {}
        self._register_tools()

    def _register_tools(self):
        """Register all MCP tools."""
        self._tools = {
            SparkToolName.STATUS.value: self.tool_status,
            SparkToolName.SUGGEST.value: self.tool_suggest,
            SparkToolName.REFLECT.value: self.tool_reflect,
            SparkToolName.ACCEPT.value: self.tool_accept,
            SparkToolName.REJECT.value: self.tool_reject,
            SparkToolName.CREATE.value: self.tool_create,
            SparkToolName.WARN.value: self.tool_warn,
        }

    async def handle_tool_call(
        self,
        tool_name: str,
        arguments: Dict[str, Any]
    ) -> ToolResponse:
        """
        Handle an incoming MCP tool call.

        Args:
            tool_name: Name of the tool to invoke
            arguments: Tool arguments

        Returns:
            ToolResponse with result or error
        """
        handler = self._tools.get(tool_name)

        if not handler:
            return ToolResponse(
                success=False,
                data={},
                error=f"Unknown tool: {tool_name}"
            )

        try:
            return await handler(arguments)
        except Exception as e:
            return ToolResponse(
                success=False,
                data={},
                error=str(e)
            )

    async def tool_status(self, arguments: Dict) -> ToolResponse:
        """
        Get current Spark status.

        Arguments: None

        Returns:
            SparkStatus as dict
        """
        mind_connected = await self.mind.is_available()

        status = SparkStatus(
            is_operational=True,
            mind_connected=mind_connected,
            queue_size=self.queue.size(),
            patterns_active=len(self.evolver.patterns),
            suggestions_ready=len(self.suggester.suggestions),
            current_session_id=self.current_session_id,
            last_learning_at=self.last_learning_at,
            version=self.VERSION
        )

        return ToolResponse(
            success=True,
            data=status.to_dict()
        )

    async def tool_suggest(self, arguments: Dict) -> ToolResponse:
        """
        Get suggestions for current task.

        Arguments:
            task_description: str - What the user is trying to do
            current_tool: Optional[str] - Tool about to be used
            max_suggestions: int - Maximum suggestions to return (default: 3)

        Returns:
            List of suggestion dicts
        """
        task_description = arguments.get("task_description", "")
        current_tool = arguments.get("current_tool")
        max_suggestions = arguments.get("max_suggestions", 3)

        # Update suggester context
        self.suggester.update_context(
            task_description=task_description,
            current_tool=current_tool
        )

        # Get relevant suggestions
        suggestions = self.suggester.get_relevant_suggestions(max_suggestions=max_suggestions)

        # Also check for alternatives
        alternative = None
        if current_tool and task_description:
            alternative = self.advisor.suggest_alternative(current_tool, task_description)

        result = {
            "suggestions": [
                {
                    "id": s.suggestion_id,
                    "type": s.suggestion_type,
                    "title": s.title,
                    "description": s.description,
                    "confidence": s.confidence,
                    "priority": s.priority
                }
                for s in suggestions
            ],
            "alternative": alternative,
            "task_guidance": None
        }

        # Add task guidance if available
        task_category = self._infer_task_category(task_description)
        if task_category:
            guidance = self.advisor.get_task_guidance(task_category)
            if guidance:
                result["task_guidance"] = {
                    "category": guidance.task_category,
                    "tips": guidance.tips[:2],  # Top 2 tips
                    "recommended_tools": guidance.recommended_tools
                }

        return ToolResponse(success=True, data=result)

    def _infer_task_category(self, task_description: str) -> Optional[str]:
        """Infer task category from description."""
        task_lower = task_description.lower()

        # Check more specific categories first
        if any(x in task_lower for x in ["git", "commit", "push", "pull", "branch", "merge"]):
            return "git"
        elif any(x in task_lower for x in ["test", "pytest", "jest", "spec"]):
            return "testing"
        elif any(x in task_lower for x in ["search", "find", "grep", "look for"]):
            return "search"
        elif any(x in task_lower for x in ["edit", "modify", "change", "update"]):
            return "edit"
        elif any(x in task_lower for x in ["run", "execute", "command", "shell"]):
            return "shell"

        return None

    async def tool_reflect(self, arguments: Dict) -> ToolResponse:
        """
        Trigger reflection on session.

        Arguments:
            session_id: str - Session to reflect on
            include_patterns: bool - Include identified patterns (default: True)
            include_improvements: bool - Include improvement suggestions (default: True)

        Returns:
            ReflectionResult as dict
        """
        session_id = arguments.get("session_id", self.current_session_id or "default")
        include_patterns = arguments.get("include_patterns", True)
        include_improvements = arguments.get("include_improvements", True)

        # Run reflection
        result = self.evolver.reflect_on_session(session_id)

        response_data = {
            "session_id": session_id,
            "traces_analyzed": result.traces_analyzed,
            "insights": result.insights
        }

        if include_patterns:
            response_data["patterns"] = [
                {
                    "id": p.pattern_id,
                    "type": p.pattern_type,
                    "description": p.description,
                    "success_rate": p.success_rate
                }
                for p in result.patterns_identified
            ]

        if include_improvements:
            response_data["improvements"] = result.improvements_proposed

        self.last_learning_at = datetime.now().timestamp()

        return ToolResponse(success=True, data=response_data)

    async def tool_accept(self, arguments: Dict) -> ToolResponse:
        """
        Accept a suggested pattern.

        Arguments:
            pattern_id: str - ID of pattern to accept
            feedback: Optional[str] - Optional feedback

        Returns:
            Success status
        """
        pattern_id = arguments.get("pattern_id")
        feedback = arguments.get("feedback", "")

        if not pattern_id:
            return ToolResponse(
                success=False,
                data={},
                error="pattern_id is required"
            )

        # Check pattern exists
        if pattern_id not in self.evolver.patterns:
            return ToolResponse(
                success=False,
                data={},
                error=f"Pattern not found: {pattern_id}"
            )

        pattern = self.evolver.patterns[pattern_id]

        # Record positive outcome
        pattern.success_count += 1
        pattern.total_uses += 1

        # Optionally evolve based on feedback
        if feedback:
            evolved = self.evolver.evolve_pattern(pattern_id, feedback)
            if evolved:
                return ToolResponse(
                    success=True,
                    data={
                        "accepted": pattern_id,
                        "evolved_to": evolved.pattern_id,
                        "feedback_applied": True
                    }
                )

        return ToolResponse(
            success=True,
            data={
                "accepted": pattern_id,
                "new_success_rate": pattern.success_rate,
                "total_uses": pattern.total_uses
            }
        )

    async def tool_reject(self, arguments: Dict) -> ToolResponse:
        """
        Reject a suggested pattern.

        Arguments:
            pattern_id: str - ID of pattern to reject
            reason: str - Reason for rejection

        Returns:
            Success status
        """
        pattern_id = arguments.get("pattern_id")
        reason = arguments.get("reason", "")

        if not pattern_id:
            return ToolResponse(
                success=False,
                data={},
                error="pattern_id is required"
            )

        # Check pattern exists
        if pattern_id not in self.evolver.patterns:
            return ToolResponse(
                success=False,
                data={},
                error=f"Pattern not found: {pattern_id}"
            )

        pattern = self.evolver.patterns[pattern_id]

        # Record negative outcome
        pattern.failure_count += 1
        pattern.total_uses += 1

        return ToolResponse(
            success=True,
            data={
                "rejected": pattern_id,
                "reason": reason,
                "new_success_rate": pattern.success_rate,
                "total_uses": pattern.total_uses
            }
        )

    async def tool_create(self, arguments: Dict) -> ToolResponse:
        """
        Manually create a new pattern.

        Arguments:
            pattern_type: str - Type of pattern
            description: str - Pattern description
            approach: str - Recommended approach
            trigger_conditions: Dict - When to apply

        Returns:
            Created pattern ID
        """
        pattern_type = arguments.get("pattern_type", "manual")
        description = arguments.get("description", "")
        approach = arguments.get("approach", "")
        trigger_conditions = arguments.get("trigger_conditions", {})

        if not description or not approach:
            return ToolResponse(
                success=False,
                data={},
                error="description and approach are required"
            )

        import hashlib
        pattern_id = hashlib.md5(
            f"{description}:{approach}:{datetime.now().timestamp()}".encode()
        ).hexdigest()[:12]

        pattern = PromptPattern(
            pattern_id=pattern_id,
            pattern_type=pattern_type,
            description=description,
            trigger_conditions=trigger_conditions,
            approach=approach,
            generation=0
        )

        self.evolver.patterns[pattern_id] = pattern

        return ToolResponse(
            success=True,
            data={
                "pattern_id": pattern_id,
                "pattern_type": pattern_type,
                "description": description
            }
        )

    async def tool_warn(self, arguments: Dict) -> ToolResponse:
        """
        Get warnings before using a tool.

        Arguments:
            tool_name: str - Tool about to be used
            tool_input: Dict - Planned tool input

        Returns:
            List of warnings if any
        """
        tool_name = arguments.get("tool_name", "")
        tool_input = arguments.get("tool_input", {})

        if not tool_name:
            return ToolResponse(
                success=False,
                data={},
                error="tool_name is required"
            )

        # Get warnings from advisor
        warning = self.advisor.pre_tool_check(tool_name, tool_input)

        warnings = []
        if warning:
            warnings.append({
                "id": warning.warning_id,
                "severity": warning.severity,
                "title": warning.title,
                "description": warning.description,
                "suggestion": warning.suggestion
            })

        return ToolResponse(
            success=True,
            data={
                "tool_name": tool_name,
                "warnings": warnings,
                "warning_count": len(warnings)
            }
        )

    def get_tool_definitions(self) -> List[Dict]:
        """
        Get MCP tool definitions for registration.

        Returns:
            List of tool definition dicts for MCP protocol
        """
        definitions = [
            {
                "name": SparkToolName.STATUS.value,
                "description": "Get current Spark system status including Mind connection, queue size, and active patterns",
                "inputSchema": {
                    "type": "object",
                    "properties": {},
                    "required": []
                }
            },
            {
                "name": SparkToolName.SUGGEST.value,
                "description": "Get suggestions and guidance for the current task",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "task_description": {
                            "type": "string",
                            "description": "What the user is trying to do"
                        },
                        "current_tool": {
                            "type": "string",
                            "description": "Tool about to be used (optional)"
                        },
                        "max_suggestions": {
                            "type": "integer",
                            "description": "Maximum suggestions to return",
                            "default": 3
                        }
                    },
                    "required": ["task_description"]
                }
            },
            {
                "name": SparkToolName.REFLECT.value,
                "description": "Trigger reflection on a session to identify patterns and improvements",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "session_id": {
                            "type": "string",
                            "description": "Session to reflect on"
                        },
                        "include_patterns": {
                            "type": "boolean",
                            "description": "Include identified patterns",
                            "default": True
                        },
                        "include_improvements": {
                            "type": "boolean",
                            "description": "Include improvement suggestions",
                            "default": True
                        }
                    },
                    "required": ["session_id"]
                }
            },
            {
                "name": SparkToolName.ACCEPT.value,
                "description": "Accept a suggested pattern, recording positive feedback",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "pattern_id": {
                            "type": "string",
                            "description": "ID of pattern to accept"
                        },
                        "feedback": {
                            "type": "string",
                            "description": "Optional feedback for improvement"
                        }
                    },
                    "required": ["pattern_id"]
                }
            },
            {
                "name": SparkToolName.REJECT.value,
                "description": "Reject a suggested pattern with reason",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "pattern_id": {
                            "type": "string",
                            "description": "ID of pattern to reject"
                        },
                        "reason": {
                            "type": "string",
                            "description": "Reason for rejection"
                        }
                    },
                    "required": ["pattern_id", "reason"]
                }
            },
            {
                "name": SparkToolName.CREATE.value,
                "description": "Manually create a new pattern",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "pattern_type": {
                            "type": "string",
                            "description": "Type of pattern (tool_sequence, error_recovery, etc.)"
                        },
                        "description": {
                            "type": "string",
                            "description": "Pattern description"
                        },
                        "approach": {
                            "type": "string",
                            "description": "Recommended approach"
                        },
                        "trigger_conditions": {
                            "type": "object",
                            "description": "When to apply this pattern"
                        }
                    },
                    "required": ["description", "approach"]
                }
            },
            {
                "name": SparkToolName.WARN.value,
                "description": "Get warnings before using a tool",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "tool_name": {
                            "type": "string",
                            "description": "Tool about to be used"
                        },
                        "tool_input": {
                            "type": "object",
                            "description": "Planned tool input"
                        }
                    },
                    "required": ["tool_name"]
                }
            }
        ]

        return definitions

    def set_session_id(self, session_id: str):
        """Set current session ID."""
        self.current_session_id = session_id
        self.suggester.update_context(session_id=session_id)

    async def initialize(self):
        """Initialize the server and load existing data."""
        if await self.mind.is_available():
            await self.evolver.load_existing_data()

    async def close(self):
        """Clean up resources."""
        await self.mind.close()

    def get_stats(self) -> Dict[str, Any]:
        """Get server statistics."""
        return {
            "version": self.VERSION,
            "session_id": self.current_session_id,
            "patterns_count": len(self.evolver.patterns),
            "suggestions_count": len(self.suggester.suggestions),
            "queue_size": self.queue.size(),
            "last_learning_at": self.last_learning_at,
            "advisor_stats": self.advisor.get_stats()
        }
