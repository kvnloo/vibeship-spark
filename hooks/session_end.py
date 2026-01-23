#!/usr/bin/env python3
"""
Spark Session End Hook: Trigger learning processing.

This hook runs when a Claude Code session ends.
It triggers the background processor to analyze the session.

Runs in background so Claude can exit immediately.
"""

import sys
import json
import subprocess
from pathlib import Path


def main():
    """Main hook entry point."""
    try:
        # Read hook input (for session info)
        input_data = json.load(sys.stdin)
        session_id = input_data.get("session_id", "unknown")
    except Exception:
        session_id = "unknown"

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
