#!/usr/bin/env python3
"""
Spark Observation Hook: Ultra-fast event capture with reasoning.

This script is called by Claude Code hooks.
It MUST complete in < 50ms to avoid any slowdown.

Design:
1. Read stdin (hook input)
2. On PRE_TOOL: Infer intent, store prediction
3. On POST_TOOL: Resolve prediction, capture learning
4. Append to queue file
5. Exit 0 immediately

NO network calls. NO heavy processing. Just capture and go.
"""

import sys
import json
import time
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.queue import quick_capture, EventType
from lib.intent_inferrer import infer_intent, predict_outcome
from lib.goal_classifier import classify_goal, should_track_as_goal, GoalType

# Fast file-based prediction storage
PREDICTIONS_FILE = Path.home() / ".spark" / "predictions.json"
# Active injections file (for feedback tracking)
INJECTIONS_FILE = Path.home() / ".spark" / "active_injections.json"
# Active goals file (for goal tracking)
GOALS_FILE = Path.home() / ".spark" / "active_goals.json"
# Warning history file (avoid duplicate warnings)
WARNINGS_FILE = Path.home() / ".spark" / "warning_history.json"


# ============================================================================
# REALTIME ADVISOR - Fast pre-tool warnings
# ============================================================================

# Dangerous command patterns (severity, description)
DANGEROUS_PATTERNS = {
    "rm -rf": ("error", "Recursive force delete can cause data loss"),
    "rm -r": ("warning", "Recursive delete - verify path carefully"),
    "> /": ("error", "Redirecting to root path can corrupt system"),
    "chmod 777": ("warning", "Setting world-writable permissions is insecure"),
    "DROP TABLE": ("error", "SQL table drop is destructive"),
    "DELETE FROM": ("warning", "SQL delete without WHERE affects all rows"),
    "git push -f": ("warning", "Force push can overwrite remote history"),
    "git reset --hard": ("warning", "Hard reset discards uncommitted changes"),
    "--no-verify": ("info", "Skipping git hooks"),
    "eval(": ("warning", "eval() can execute arbitrary code"),
    "exec(": ("warning", "exec() can execute arbitrary code"),
}

# Patterns that suggest potential issues
RISKY_FILE_PATTERNS = {
    ".env": ("warning", "Modifying environment file - contains secrets?"),
    "credentials": ("warning", "Modifying credentials file"),
    "password": ("warning", "File may contain sensitive data"),
    "/etc/": ("error", "Modifying system configuration"),
    "node_modules": ("info", "Modifying vendor code - usually not recommended"),
}


def fast_pre_tool_warning(tool_name: str, tool_input: dict) -> dict:
    """
    Fast pre-tool warning check. Must complete in <5ms.

    Returns warning dict if issue detected, empty dict otherwise.
    """
    warning = {}

    try:
        if tool_name == "Bash":
            command = tool_input.get("command", "").lower()
            for pattern, (severity, desc) in DANGEROUS_PATTERNS.items():
                if pattern.lower() in command:
                    warning = {
                        "severity": severity,
                        "pattern": pattern,
                        "description": desc
                    }
                    break

        elif tool_name in ("Write", "Edit"):
            file_path = tool_input.get("file_path", "").lower()
            for pattern, (severity, desc) in RISKY_FILE_PATTERNS.items():
                if pattern.lower() in file_path:
                    warning = {
                        "severity": severity,
                        "pattern": pattern,
                        "description": desc
                    }
                    break
    except Exception:
        pass  # Never fail - just skip warning

    return warning


def get_recovery_suggestion(tool_name: str, error: str) -> dict:
    """
    Fast recovery suggestion based on error type. Must complete in <5ms.

    Returns suggestion dict if applicable, empty dict otherwise.
    """
    suggestion = {}

    try:
        error_lower = error.lower() if error else ""

        # String not found (Edit tool) - check BEFORE general "not found"
        if "old_string" in error_lower or "not found in file" in error_lower:
            suggestion = {
                "category": "string_not_found",
                "approach": "Read the file first to verify exact content",
                "alternative_tools": ["Read", "Grep"]
            }

        # File not found
        elif "not found" in error_lower or "no such file" in error_lower:
            suggestion = {
                "category": "not_found",
                "approach": "Use Glob to search for the file",
                "alternative_tools": ["Glob", "Grep"]
            }

        # Permission denied
        elif "permission denied" in error_lower or "access denied" in error_lower:
            suggestion = {
                "category": "permission",
                "approach": "Check file permissions or run with appropriate access",
                "alternative_tools": []
            }

        # Syntax error
        elif "syntax error" in error_lower or "syntaxerror" in error_lower:
            suggestion = {
                "category": "syntax",
                "approach": "Review the code syntax, check for missing brackets/quotes",
                "alternative_tools": ["Read"]
            }

        # Timeout
        elif "timeout" in error_lower or "timed out" in error_lower:
            suggestion = {
                "category": "timeout",
                "approach": "Try with a smaller scope or run in background",
                "alternative_tools": []
            }

    except Exception:
        pass  # Never fail

    return suggestion


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


def store_prediction(session_id: str, tool_name: str, tool_input: dict) -> dict:
    """
    Store a prediction for later resolution. Fast file write.

    Returns the prediction dict for inclusion in event data.
    """
    try:
        PREDICTIONS_FILE.parent.mkdir(parents=True, exist_ok=True)

        # Infer intent and predict
        intent, confidence, risks = infer_intent(tool_name, tool_input)
        expected_outcome = predict_outcome(tool_name, tool_input)

        prediction = {
            "session_id": session_id,
            "tool_name": tool_name,
            "timestamp": time.time(),
            "intent": intent,
            "confidence": confidence,
            "risks": risks,
            "expected_outcome": expected_outcome
        }

        # Load existing predictions
        predictions = {}
        if PREDICTIONS_FILE.exists():
            try:
                predictions = json.loads(PREDICTIONS_FILE.read_text())
            except:
                predictions = {}

        # Store by session:tool key (most recent wins)
        key = f"{session_id}:{tool_name}"
        predictions[key] = prediction

        # Keep only last 20 predictions
        if len(predictions) > 20:
            sorted_keys = sorted(predictions.keys(),
                                 key=lambda k: predictions[k].get("timestamp", 0))
            for old_key in sorted_keys[:-20]:
                del predictions[old_key]

        PREDICTIONS_FILE.write_text(json.dumps(predictions))
        return prediction

    except Exception:
        return {}


def resolve_prediction(session_id: str, tool_name: str, success: bool, error: str = None) -> dict:
    """
    Resolve a prediction and return the learning.

    Returns learning data to include in event.
    """
    try:
        if not PREDICTIONS_FILE.exists():
            return {}

        predictions = json.loads(PREDICTIONS_FILE.read_text())
        key = f"{session_id}:{tool_name}"

        if key not in predictions:
            return {}

        prediction = predictions[key]
        del predictions[key]
        PREDICTIONS_FILE.write_text(json.dumps(predictions))

        # Calculate accuracy
        expected_success = prediction["confidence"] >= 0.5
        was_correct = (expected_success == success)

        # Generate learning from gap
        learning = None
        if not was_correct:
            if expected_success and not success:
                # Predicted success, got failure
                learning = f"PREDICTION_WRONG: Expected {prediction['intent']} to succeed " \
                          f"(confidence: {prediction['confidence']:.0%}), but failed"
                if error:
                    learning += f". Error: {error[:50]}"
                if prediction["risks"]:
                    learning += f". Missed risk: {prediction['risks'][0]}"
            else:
                # Predicted failure, got success
                learning = f"PREDICTION_PESSIMISTIC: {prediction['intent']} succeeded " \
                          f"despite low confidence ({prediction['confidence']:.0%})"

        return {
            "prediction": prediction,
            "actual_success": success,
            "was_correct": was_correct,
            "learning": learning
        }

    except Exception:
        return {}


def capture_goal(session_id: str, user_prompt: str) -> dict:
    """
    Capture a user goal from their prompt.

    This is the strategic layer - understanding WHAT the user wants to achieve.
    Uses the shared goal_classifier for consistent classification.
    """
    try:
        GOALS_FILE.parent.mkdir(parents=True, exist_ok=True)

        # Load existing goals
        goals = {}
        if GOALS_FILE.exists():
            try:
                goals = json.loads(GOALS_FILE.read_text())
            except:
                goals = {}

        # Classify the goal using shared classifier
        goal_type_enum, confidence = classify_goal(user_prompt)
        goal_type = goal_type_enum.value
        description = user_prompt[:100].split('.')[0].strip()

        goal_id = f"goal_{hash(f'{session_id}:{user_prompt[:50]}:{time.time()}') % 100000000:08x}"

        # Check if this is a conversational prompt (not a real goal)
        is_conversational = not should_track_as_goal(goal_type_enum)

        goal = {
            "goal_id": goal_id,
            "session_id": session_id,
            "created_at": time.time(),
            "goal_type": goal_type,
            "confidence": confidence,
            "description": description,
            "actions": [],
            "status": "active",
            "is_conversational": is_conversational
        }

        # Only mark previous goals as abandoned if this is a REAL goal
        # Conversational prompts shouldn't invalidate active goals
        if not is_conversational:
            for g_id, g in list(goals.items()):
                if g.get("session_id") == session_id and g.get("status") == "active":
                    # Only abandon if the previous goal wasn't conversational
                    if not g.get("is_conversational", False):
                        g["status"] = "abandoned"

        goals[goal_id] = goal

        # Keep only last 50 goals
        if len(goals) > 50:
            sorted_ids = sorted(goals.keys(), key=lambda k: goals[k].get("created_at", 0))
            for old_id in sorted_ids[:-50]:
                del goals[old_id]

        GOALS_FILE.write_text(json.dumps(goals))

        return {
            "goal_captured": True,
            "goal_id": goal_id,
            "goal_type": goal_type,
            "confidence": confidence,
            "is_conversational": is_conversational
        }

    except Exception:
        return {}


# _classify_goal removed - now using shared lib/goal_classifier.py


def track_goal_progress(session_id: str, tool_name: str, success: bool) -> dict:
    """
    Track progress toward the current goal.

    Returns progress info. Skips conversational goals.
    """
    try:
        if not GOALS_FILE.exists():
            return {}

        goals = json.loads(GOALS_FILE.read_text())

        # Find active REAL goal for this session (not conversational)
        active_goal = None
        for g_id, g in goals.items():
            if (g.get("session_id") == session_id and
                g.get("status") == "active" and
                not g.get("is_conversational", False)):
                active_goal = g
                break

        if not active_goal:
            return {}

        # Track action
        active_goal["actions"].append({
            "tool": tool_name,
            "success": success,
            "timestamp": time.time()
        })

        GOALS_FILE.write_text(json.dumps(goals))

        return {
            "goal_type": active_goal.get("goal_type"),
            "actions_count": len(active_goal["actions"]),
            "is_conversational": False
        }

    except Exception:
        return {}


def check_goal_completion(session_id: str, user_message: str) -> dict:
    """
    Check if user message signals goal completion.

    Only checks real goals, not conversational ones.
    """
    try:
        if not GOALS_FILE.exists():
            return {}

        goals = json.loads(GOALS_FILE.read_text())

        # Find active REAL goal (not conversational)
        active_goal = None
        goal_id = None
        for g_id, g in goals.items():
            if (g.get("session_id") == session_id and
                g.get("status") == "active" and
                not g.get("is_conversational", False)):
                active_goal = g
                goal_id = g_id
                break

        if not active_goal:
            return {}

        message_lower = user_message.lower()

        # Completion signals
        POSITIVE = ["thanks", "perfect", "great", "works", "done", "fixed", "awesome"]

        if any(sig in message_lower for sig in POSITIVE):
            active_goal["status"] = "completed"
            active_goal["completed_at"] = time.time()
            active_goal["success"] = True

            # Calculate success score
            duration = active_goal["completed_at"] - active_goal["created_at"]
            actions = len(active_goal.get("actions", []))
            score = 0.8 if duration < 300 else 0.6  # Bonus for quick

            active_goal["success_score"] = score

            GOALS_FILE.write_text(json.dumps(goals))

            return {
                "goal_completed": True,
                "goal_type": active_goal.get("goal_type"),
                "success_score": score,
                "duration_sec": duration,
                "actions_count": actions
            }

        return {}

    except Exception:
        return {}


def track_injection_feedback(session_id: str, tool_name: str, success: bool) -> dict:
    """
    Track tool usage against active injections (advice feedback).

    This closes the feedback loop - we learn if injected advice was followed
    and whether it helped.

    Returns feedback data to include in event.
    """
    try:
        if not INJECTIONS_FILE.exists():
            return {}

        injections = json.loads(INJECTIONS_FILE.read_text())
        feedback = {}

        # Check each active injection for this session
        updated = False
        for inj_id, inj in list(injections.items()):
            if inj.get("session_id") != session_id:
                continue

            trigger = inj.get("trigger_conditions", {})
            outcome_events = inj.get("outcome_events", [])

            # Track this tool usage
            outcome_events.append({
                "tool": tool_name,
                "success": success,
                "timestamp": time.time()
            })
            inj["outcome_events"] = outcome_events
            updated = True

            # Check if this tool matches advice
            recommended_tool = trigger.get("recommended_tool")
            if recommended_tool and tool_name == recommended_tool:
                inj["followed"] = True
                feedback["advice_followed"] = recommended_tool

            # Check for warned errors
            warned_error = trigger.get("warned_error", "")
            if not success and warned_error:
                # User hit an error we warned about
                inj["warning_relevant"] = True
                feedback["warning_hit"] = warned_error[:40]

            # Determine outcome if we have enough events (3+)
            if len(outcome_events) >= 3 and inj.get("outcome") == "pending":
                if inj.get("followed"):
                    inj["outcome"] = "followed"
                    feedback["outcome_determined"] = "followed"
                elif inj.get("warning_relevant"):
                    inj["outcome"] = "warning_ignored"
                    feedback["outcome_determined"] = "warning_ignored"
                else:
                    inj["outcome"] = "ignored"

        if updated:
            INJECTIONS_FILE.write_text(json.dumps(injections))

        return feedback

    except Exception:
        return {}


def main():
    """
    Main hook entry point.

    Reads hook data from stdin, queues it, exits fast.
    With reasoning: captures predictions on PRE_TOOL, resolves on POST_TOOL.
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

    # REASONING: On PRE_TOOL, store a prediction
    if event_type == EventType.PRE_TOOL and tool_name:
        prediction = store_prediction(session_id, tool_name, tool_input)
        if prediction:
            data["prediction"] = {
                "intent": prediction.get("intent"),
                "confidence": prediction.get("confidence"),
                "risks": prediction.get("risks", [])
            }

        # REALTIME ADVISOR: Check for dangerous patterns before execution
        warning = fast_pre_tool_warning(tool_name, tool_input)
        if warning:
            data["pre_tool_warning"] = warning

    # For failure events, include error info
    # Claude Code may send error in different fields - check all possibilities
    error = None
    if event_type == EventType.POST_TOOL_FAILURE:
        # Try multiple possible error field names
        error = (
            input_data.get("tool_error") or
            input_data.get("error") or
            input_data.get("tool_result") or
            input_data.get("result") or
            input_data.get("message") or
            input_data.get("stderr") or
            ""
        )
        # If still no error but we know it failed, create a generic one
        if not error and tool_name:
            error = f"{tool_name} failed (no error message provided)"
        if error:
            kwargs["error"] = str(error)[:500]  # Truncate long errors

    # REASONING: On POST_TOOL/POST_TOOL_FAILURE, resolve prediction
    if event_type in (EventType.POST_TOOL, EventType.POST_TOOL_FAILURE) and tool_name:
        success = (event_type == EventType.POST_TOOL)
        resolution = resolve_prediction(session_id, tool_name, success, error)
        if resolution:
            data["prediction_resolution"] = {
                "was_correct": resolution.get("was_correct"),
                "learning": resolution.get("learning")
            }
            # If there's a learning, include it prominently
            if resolution.get("learning"):
                data["reasoning_learning"] = resolution["learning"]

        # FEEDBACK: Track tool usage against injected advice
        feedback = track_injection_feedback(session_id, tool_name, success)
        if feedback:
            data["advice_feedback"] = feedback

        # GOALS: Track progress toward current goal
        goal_progress = track_goal_progress(session_id, tool_name, success)
        if goal_progress:
            data["goal_progress"] = goal_progress

        # REALTIME ADVISOR: On failure, suggest recovery
        if event_type == EventType.POST_TOOL_FAILURE and error:
            recovery = get_recovery_suggestion(tool_name, error)
            if recovery:
                data["recovery_suggestion"] = recovery

    # GOALS: Capture goal from user prompt
    if event_type == EventType.USER_PROMPT:
        user_message = input_data.get("prompt", "")  # Claude Code sends 'prompt', not 'message'
        if user_message:
            # Capture new goal
            goal_info = capture_goal(session_id, user_message)
            if goal_info:
                data["goal_captured"] = goal_info

            # Also check if this completes a previous goal
            completion = check_goal_completion(session_id, user_message)
            if completion:
                data["goal_completed"] = completion

    # Queue the event (fast file append)
    quick_capture(event_type, session_id, data, **kwargs)

    # Calculate timing (for debugging)
    elapsed_ms = (time.time() - start) * 1000

    # Exit cleanly - Claude continues immediately
    # No output = no interference
    sys.exit(0)


if __name__ == "__main__":
    main()
