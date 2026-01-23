#!/usr/bin/env python3
"""
Spark Observation Hook: Ultra-fast event capture.

This script is called by Claude Code hooks.
It MUST complete in < 50ms to avoid any slowdown.

Design:
1. Read stdin (hook input)
2. Append to queue file
3. Exit 0 immediately

NO network calls. NO heavy processing. Just capture and go.
"""

import sys
import json
import time
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.queue import quick_capture, EventType


def get_event_type(hook_event_name: str) -> EventType:
    """Map Claude Code hook event to Spark event type."""
    mapping = {
        "SessionStart": EventType.SESSION_START,
        "UserPromptSubmit": EventType.USER_PROMPT,
        "PreToolUse": EventType.PRE_TOOL,
        "PostToolUse": EventType.POST_TOOL,
        "PostToolUseFailure": EventType.POST_TOOL_FAILURE,
        "Stop": EventType.STOP,
        "SessionEnd": EventType.SESSION_END,
    }
    return mapping.get(hook_event_name, EventType.POST_TOOL)


def main():
    """
    Main hook entry point.

    Reads hook data from stdin, queues it, exits fast.
    """
    start = time.time()

    try:
        # Read hook input from stdin
        input_data = json.load(sys.stdin)
    except (json.JSONDecodeError, Exception):
        # If we can't read input, just exit cleanly
        sys.exit(0)

    # Extract key fields
    session_id = input_data.get("session_id", "unknown")
    hook_event = input_data.get("hook_event_name", "unknown")
    tool_name = input_data.get("tool_name")
    tool_input = input_data.get("tool_input", {})

    # Get event type
    event_type = get_event_type(hook_event)

    # Build minimal event data
    data = {
        "hook_event": hook_event,
        "cwd": input_data.get("cwd"),
        "permission_mode": input_data.get("permission_mode"),
    }

    # For tool events, include tool info
    kwargs = {}
    if tool_name:
        kwargs["tool_name"] = tool_name
        kwargs["tool_input"] = tool_input

        # Enhanced tracking for Skill and Task tools
        if tool_name == "Skill":
            data["skill_id"] = tool_input.get("skill", "unknown")
            data["skill_args"] = tool_input.get("args")
        elif tool_name == "Task":
            data["agent_type"] = tool_input.get("subagent_type", "general-purpose")
            data["agent_prompt"] = (tool_input.get("prompt", "")[:200]
                                    if tool_input.get("prompt") else None)

    # For failure events, include error info
    if "tool_error" in input_data:
        kwargs["error"] = input_data.get("tool_error")

    # Queue the event (fast file append)
    quick_capture(event_type, session_id, data, **kwargs)

    # Calculate timing (for debugging)
    elapsed_ms = (time.time() - start) * 1000

    # Exit cleanly - Claude continues immediately
    # No output = no interference
    sys.exit(0)


if __name__ == "__main__":
    main()
