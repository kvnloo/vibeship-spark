#!/usr/bin/env python3
"""
Spark Session End Hook: Finalize goals and trigger learning.

This hook runs when a Claude Code session ends.
It:
1. Finalizes any active goals for this session
2. Triggers the background processor to learn from the session

Runs in background so Claude can exit immediately.
"""

import sys
import json
import subprocess
import time
from pathlib import Path

# Goal storage
SPARK_DIR = Path.home() / ".spark"
GOALS_FILE = SPARK_DIR / "active_goals.json"


def finalize_session_goals(session_id: str):
    """
    Finalize any active goals for this session.

    If a session ends normally (not crashed), assume the active goal
    was completed successfully. This closes the goal tracking loop.
    """
    if not GOALS_FILE.exists():
        return

    try:
        goals = json.loads(GOALS_FILE.read_text())
        updated = False

        for g_id, g in goals.items():
            if g.get("session_id") == session_id and g.get("status") == "active":
                # Session ended with this goal active
                # Mark as completed (session ended normally = assumed success)
                g["status"] = "completed"
                g["completed_at"] = time.time()

                # Calculate success score based on actions
                actions = g.get("actions", [])
                success_count = sum(1 for a in actions if a.get("success", False))
                total_actions = len(actions)

                if total_actions > 0:
                    # Base score from action success rate
                    base_score = success_count / total_actions
                    # Bonus for completing (session ended normally)
                    g["success_score"] = min(base_score + 0.1, 1.0)
                else:
                    # No actions tracked = moderate success
                    g["success_score"] = 0.6

                updated = True

        if updated:
            GOALS_FILE.write_text(json.dumps(goals))

    except Exception:
        pass  # Never fail the hook


def main():
    """Main hook entry point."""
    try:
        # Read hook input (for session info)
        input_data = json.load(sys.stdin)
        session_id = input_data.get("session_id", "unknown")
    except Exception:
        session_id = "unknown"

    # FIRST: Finalize any active goals for this session
    finalize_session_goals(session_id)

    # Get processor path
    processor_path = Path(__file__).parent.parent / "processor.py"

    if processor_path.exists():
        try:
            # Run processor in background (fire and forget)
            # Using subprocess.Popen with no wait
            subprocess.Popen(
                [sys.executable, str(processor_path), "--mode", "once"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True  # Detach from parent
            )
        except Exception:
            pass  # Never fail the hook

    # Exit cleanly
    sys.exit(0)


if __name__ == "__main__":
    main()
