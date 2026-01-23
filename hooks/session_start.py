#!/usr/bin/env python3
"""
Spark Session Start Hook: Load context from Mind.

This hook runs when a Claude Code session starts.
It loads relevant learnings and injects them as context.

MUST be fast (< 100ms target) but can do async work.
"""

import sys
import json
import asyncio
import os
from pathlib import Path
from typing import Optional, Dict, Any, List

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.mind_client import MindClient, TemporalLevel, ContentType

# Maximum context size to avoid overloading Claude
MAX_CONTEXT_CHARS = 800


def extract_project_name(cwd: str) -> Optional[str]:
    """Extract project name from working directory."""
    if not cwd:
        return None
    parts = Path(cwd).parts
    # Skip common root paths
    skip = {"Users", "Desktop", "Documents", "Projects", "repos", "code"}
    for part in reversed(parts):
        if part.lower() not in {s.lower() for s in skip} and part:
            return part
    return None


def format_tool_effectiveness(content: str) -> Optional[str]:
    """Format a tool effectiveness learning for context."""
    # Parse: "LEARNING [TOOL_EFFECTIVENESS]: Bash has 87% success rate..."
    if "TOOL_EFFECTIVENESS" not in content:
        return None

    try:
        # Extract tool name and success rate
        parts = content.split(":")
        if len(parts) < 2:
            return None
        insight = parts[1].strip()
        # Get first sentence
        if "." in insight:
            insight = insight.split(".")[0] + "."
        if len(insight) > 80:
            insight = insight[:77] + "..."
        return insight
    except Exception:
        return None


def format_error_avoidance(content: str) -> Optional[str]:
    """Format an error avoidance learning for context."""
    if "ERROR_AVOIDANCE" not in content:
        return None

    try:
        # Extract the avoidance tip
        if "To avoid" in content:
            start = content.find("To avoid")
            end = content.find(".", start)
            if end > start:
                return content[start:end + 1]
        return None
    except Exception:
        return None


async def load_context(project_name: Optional[str] = None) -> Optional[str]:
    """Load relevant context from Mind."""
    mind = MindClient(timeout=2.0)  # Short timeout to stay fast

    try:
        # Check if Mind is available
        if not await mind.is_available():
            return None

        # Build search query - include project name if available
        tool_query = "tool effectiveness LEARNING"
        if project_name:
            tool_query = f"{project_name} {tool_query}"

        # Load recent learnings (limit to stay fast)
        learnings = await mind.retrieve(
            query=tool_query,
            limit=5,
            temporal_level=TemporalLevel.IDENTITY,
            content_type=ContentType.REFLECTION
        )

        # Load any error avoidance patterns
        error_patterns = await mind.retrieve(
            query="error avoidance LEARNING",
            limit=3,
            temporal_level=TemporalLevel.IDENTITY,
            content_type=ContentType.REFLECTION
        )

        # Build context with size limit
        context_parts: List[str] = []
        total_chars = 0

        # Tool effectiveness section
        tool_insights: List[str] = []
        for l in learnings[:4]:
            content = l.get("content", "")
            formatted = format_tool_effectiveness(content)
            if formatted:
                tool_insights.append(formatted)

        if tool_insights:
            header = "Spark Tool Insights:"
            context_parts.append(header)
            total_chars += len(header)

            for insight in tool_insights[:3]:
                if total_chars + len(insight) + 4 > MAX_CONTEXT_CHARS:
                    break
                line = f"  - {insight}"
                context_parts.append(line)
                total_chars += len(line)

        # Error avoidance section
        error_tips: List[str] = []
        for p in error_patterns[:3]:
            content = p.get("content", "")
            formatted = format_error_avoidance(content)
            if formatted:
                error_tips.append(formatted)

        if error_tips and total_chars < MAX_CONTEXT_CHARS - 100:
            header = "\nError Prevention:"
            context_parts.append(header)
            total_chars += len(header)

            for tip in error_tips[:2]:
                if total_chars + len(tip) + 4 > MAX_CONTEXT_CHARS:
                    break
                line = f"  - {tip}"
                context_parts.append(line)
                total_chars += len(line)

        return "\n".join(context_parts) if context_parts else None

    except Exception:
        return None
    finally:
        await mind.close()


def main():
    """Main hook entry point."""
    try:
        # Read hook input
        input_data = json.load(sys.stdin)
    except Exception:
        sys.exit(0)

    # Extract project context from hook data
    cwd = input_data.get("cwd", os.getcwd())
    project_name = extract_project_name(cwd)

    # Try to load context (with timeout)
    try:
        context = asyncio.run(asyncio.wait_for(
            load_context(project_name),
            timeout=2.0
        ))
    except asyncio.TimeoutError:
        context = None
    except Exception:
        context = None

    # If we have context, output it for Claude to see
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
