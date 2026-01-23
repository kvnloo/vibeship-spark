#!/usr/bin/env python3
"""
Spark Session Start Hook: Inject intelligence into Claude.

This hook runs when a Claude Code session starts.
It pulls learnings from Mind via ContextInjector and feeds
them back to Claude - closing the learning loop.

Target: < 200ms to avoid slowing session start.
"""

import sys
import json
import asyncio
import os
from pathlib import Path
from typing import Optional

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.context_injector import ContextInjector


def extract_project_name(cwd: str) -> Optional[str]:
    """Extract project name from working directory."""
    if not cwd:
        return None
    parts = Path(cwd).parts
    # Skip common root paths
    skip = {"Users", "Desktop", "Documents", "Projects", "repos", "code", "home", "USER"}
    for part in reversed(parts):
        if part.lower() not in {s.lower() for s in skip} and part:
            return part
    return None


async def load_and_inject(project_name: Optional[str]) -> Optional[str]:
    """Load context from Mind and format for injection."""
    injector = ContextInjector()
    try:
        return await injector.get_injection_string(project_name)
    finally:
        await injector.close()


def main():
    """Main hook entry point."""
    try:
        # Read hook input
        input_data = json.load(sys.stdin)
    except Exception:
        sys.exit(0)

    # Extract project context
    cwd = input_data.get("cwd", os.getcwd())
    project_name = extract_project_name(cwd)

    # Load context with timeout
    try:
        context = asyncio.run(asyncio.wait_for(
            load_and_inject(project_name),
            timeout=2.0
        ))
    except asyncio.TimeoutError:
        context = None
    except Exception:
        context = None

    # Output context for Claude
    if context:
        output = {
            "continue": True,
            "hookSpecificOutput": {
                "additionalContext": context
            }
        }
        print(json.dumps(output))

    sys.exit(0)


if __name__ == "__main__":
    main()
