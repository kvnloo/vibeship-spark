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

# Fast file-based prediction storage
PREDICTIONS_FILE = Path.home() / ".spark" / "predictions.json"
# Active injections file (for feedback tracking)
INJECTIONS_FILE = Path.home() / ".spark" / "active_injections.json"
# Active goals file (for goal tracking)
GOALS_FILE = Path.home() / ".spark" / "active_goals.json"


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

        # Classify the goal
        goal_type = _classify_goal(user_prompt)
        description = user_prompt[:100].split('.')[0].strip()

        goal_id = f"goal_{hash(f'{session_id}:{user_prompt[:50]}:{time.time()}') % 100000000:08x}"

        goal = {
            "goal_id": goal_id,
            "session_id": session_id,
            "created_at": time.time(),
            "goal_type": goal_type,
            "description": description,
            "actions": [],
            "status": "active"
        }

        # Mark any previous goal for this session as abandoned
        for g_id, g in list(goals.items()):
            if g.get("session_id") == session_id and g.get("status") == "active":
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
            "goal_type": goal_type
        }

    except Exception:
        return {}


def _classify_goal(prompt: str) -> str:
    """Classify goal type from prompt."""
    prompt_lower = prompt.lower()

    DEBUG = ["fix", "bug", "error", "broken", "fail", "crash", "issue", "wrong", "debug"]
    FEATURE = ["add", "create", "implement", "build", "new", "feature", "make"]
    REFACTOR = ["refactor", "improve", "clean", "optimize", "simplify", "rename"]
    EXPLORE = ["find", "search", "where", "what", "how", "understand", "look", "show", "analyze", "check", "review", "examine", "inspect"]
    TEST = ["test", "spec", "coverage", "verify"]

    scores = {
        "debug": sum(1 for k in DEBUG if k in prompt_lower),
        "feature": sum(1 for k in FEATURE if k in prompt_lower),
        "refactor": sum(1 for k in REFACTOR if k in prompt_lower),
        "explore": sum(1 for k in EXPLORE if k in prompt_lower),
        "test": sum(1 for k in TEST if k in prompt_lower),
    }

    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else "unknown"


def track_goal_progress(session_id: str, tool_name: str, success: bool) -> dict:
    """
    Track progress toward the current goal.

    Returns progress info.
    """
    try:
        if not GOALS_FILE.exists():
            return {}

        goals = json.loads(GOALS_FILE.read_text())

        # Find active goal for this session
        active_goal = None
        for g_id, g in goals.items():
            if g.get("session_id") == session_id and g.get("status") == "active":
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
            "actions_count": len(active_goal["actions"])
        }

    except Exception:
        return {}


def check_goal_completion(session_id: str, user_message: str) -> dict:
    """
    Check if user message signals goal completion.
    """
    try:
        if not GOALS_FILE.exists():
            return {}

        goals = json.loads(GOALS_FILE.read_text())

        # Find active goal
        active_goal = None
        goal_id = None
        for g_id, g in goals.items():
            if g.get("session_id") == session_id and g.get("status") == "active":
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

    # For failure events, include error info
    error = None
    if "tool_error" in input_data:
        error = input_data.get("tool_error")
        kwargs["error"] = error

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
