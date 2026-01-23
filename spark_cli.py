#!/usr/bin/env python3
"""
Spark CLI: Talk to your learning system.

Usage:
    python spark_cli.py status      # What am I doing?
    python spark_cli.py learn       # Process queue now
    python spark_cli.py reflect     # Deep reflection
    python spark_cli.py learnings   # What have I learned?
    python spark_cli.py watch       # Run daemon
    python spark_cli.py clear       # Clear queue
"""

import sys
import asyncio
import argparse
from pathlib import Path

# Add lib to path
sys.path.insert(0, str(Path(__file__).parent))

from lib.queue import SparkQueue
from lib.mind_client import MindClient


def print_banner():
    """Print Spark banner."""
    print("""
    +=====================================+
    |  SPARK - Self-Evolving Intelligence |
    +=====================================+
    """)


async def cmd_status():
    """Show current status."""
    queue = SparkQueue()
    mind = MindClient()

    mind_ok = await mind.is_available()

    print("\n  Status")
    print("  " + "-" * 35)
    print(f"  Mind:        {'Connected' if mind_ok else 'Offline'}")
    print(f"  Queue:       {queue.size()} events pending")

    # Get learning count from Mind
    if mind_ok:
        learnings = await mind.retrieve("LEARNING", limit=100)
        print(f"  Learnings:   {len(learnings)} stored")

    await mind.close()
    print()


async def cmd_learn():
    """Process queue once."""
    from processor import SparkProcessor

    print("\n  Processing queue...")
    processor = SparkProcessor()
    await processor.initialize()
    count = await processor.process_once()
    await processor.mind.close()

    print(f"  Processed {count} events")
    print()


async def cmd_reflect():
    """Run deep reflection."""
    from processor import SparkProcessor

    print("\n  Running reflection...")
    processor = SparkProcessor()
    await processor.initialize()
    await processor.run_reflection()
    await processor.mind.close()

    print("  Reflection complete")
    print()


async def cmd_learnings():
    """Show what Spark has learned."""
    mind = MindClient()

    if not await mind.is_available():
        print("\n  Mind is offline. Cannot retrieve learnings.")
        return

    learnings = await mind.retrieve("LEARNING", limit=20)

    print(f"\n  Recent Learnings ({len(learnings)} found)")
    print("  " + "-" * 50)

    if not learnings:
        print("  No learnings yet. Use Claude Code more!")
    else:
        for i, learning in enumerate(learnings[:10], 1):
            content = learning.get("content", "")
            # Extract first line or summary
            first_line = content.split("\n")[0][:60]
            print(f"  {i}. {first_line}...")

    await mind.close()
    print()


async def cmd_watch(interval: int = 15):
    """Run as daemon."""
    from processor import SparkProcessor

    print(f"\n  Watching for events (every {interval}s)...")
    print("  Press Ctrl+C to stop\n")

    processor = SparkProcessor()
    await processor.initialize()

    try:
        await processor.run_daemon(interval)
    except KeyboardInterrupt:
        processor.stop()
        print("\n  Stopped watching")

    await processor.mind.close()


def cmd_clear():
    """Clear the queue."""
    queue = SparkQueue()
    size = queue.size()

    if size == 0:
        print("\n  Queue is already empty")
        return

    # Pop all events
    queue.pop_batch(size)
    print(f"\n  Cleared {size} events from queue")
    print()


def cmd_hooks():
    """Show hook status."""
    import json

    user_settings = Path.home() / ".claude" / "settings.json"

    print("\n  Hook Status")
    print("  " + "-" * 35)

    if user_settings.exists():
        with open(user_settings) as f:
            settings = json.load(f)

        hooks = settings.get("hooks", {})
        if hooks:
            print(f"  Hooks installed: {len(hooks)} types")
            for hook_type in hooks:
                print(f"    - {hook_type}")
        else:
            print("  No hooks installed")
    else:
        print("  Settings file not found")

    print()


def main():
    parser = argparse.ArgumentParser(
        description="Spark CLI - Talk to your learning system",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Commands:
  status      Show current Spark status
  learn       Process pending events now
  reflect     Run deep reflection on learnings
  learnings   Show what Spark has learned
  watch       Run daemon (continuous processing)
  clear       Clear the event queue
  hooks       Show hook installation status
        """
    )

    parser.add_argument("command", nargs="?", default="status",
                       choices=["status", "learn", "reflect", "learnings",
                               "watch", "clear", "hooks"],
                       help="Command to run")
    parser.add_argument("--interval", type=int, default=15,
                       help="Watch interval in seconds (default: 15)")

    args = parser.parse_args()

    print_banner()

    if args.command == "status":
        asyncio.run(cmd_status())
    elif args.command == "learn":
        asyncio.run(cmd_learn())
    elif args.command == "reflect":
        asyncio.run(cmd_reflect())
    elif args.command == "learnings":
        asyncio.run(cmd_learnings())
    elif args.command == "watch":
        asyncio.run(cmd_watch(args.interval))
    elif args.command == "clear":
        cmd_clear()
    elif args.command == "hooks":
        cmd_hooks()


if __name__ == "__main__":
    main()
