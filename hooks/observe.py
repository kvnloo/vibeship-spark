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

    # Queue the event (fast file append)
    quick_capture(event_type, session_id, data, **kwargs)

    # Calculate timing (for debugging)
    elapsed_ms = (time.time() - start) * 1000

    # Exit cleanly - Claude continues immediately
    # No output = no interference
    sys.exit(0)


if __name__ == "__main__":
    main()
