#!/usr/bin/env python3
"""
Spark Session Start Hook: Inject intelligence into Claude.

This hook runs when a Claude Code session starts.
It pulls learnings from Mind via ContextInjector and feeds
them back to Claude - closing the learning loop.

Also uses Suggester for proactive warnings.

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
from lib.suggester import Suggester


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


async def load_and_inject(project_name: Optional[str], session_id: Optional[str] = None) -> Optional[str]:
    """Load context from Mind and format for injection."""
    injector = ContextInjector()
    suggester = Suggester()

    try:
        # Load context and suggestions in parallel
        context_task = injector.get_injection_string(project_name)
        suggestions_task = suggester.load_suggestions_from_mind()

        context, _ = await asyncio.gather(context_task, suggestions_task)

        # Update suggester context
        if session_id:
            suggester.update_context(session_id=session_id, project_name=project_name)

        # Get proactive warnings
        warnings = suggester.get_relevant_suggestions(max_suggestions=2, min_confidence=0.7)

        # Combine context and warnings
        parts = []
        if context:
            parts.append(context)

        if warnings:
            warning_text = suggester.format_suggestions_for_display(warnings, compact=True)
            if warning_text:
                parts.append(warning_text)

        return "\n".join(parts) if parts else None

    finally:
        await injector.close()


def main():
    """Main hook entry point."""
    try:
        # Read hook input
        input_data = json.load(sys.stdin)
    except Exception:
        sys.exit(0)

    # Extract context
    cwd = input_data.get("cwd", os.getcwd())
    project_name = extract_project_name(cwd)
    session_id = input_data.get("session_id")

    # Load context with timeout
    try:
        context = asyncio.run(asyncio.wait_for(
            load_and_inject(project_name, session_id),
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
