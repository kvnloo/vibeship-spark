#!/usr/bin/env python3
"""
Spark Live Witness - Watch Spark learn in real-time.

This tool lets you observe Spark's self-improvement loop as it happens:
  OBSERVE -> DECIDE -> ACT -> MEASURE -> LEARN -> IMPROVE

Usage:
  python spark_witness.py baseline    # Capture starting state
  python spark_witness.py watch       # Show queue activity
  python spark_witness.py process     # Trigger learning
  python spark_witness.py delta       # Show what was learned since baseline
  python spark_witness.py live        # All-in-one: watch -> process -> delta
"""

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path

# Add lib to path
sys.path.insert(0, str(Path(__file__).parent))

from lib.queue import SparkQueue
from lib.mind_client import MindClient

# State file for tracking baseline
STATE_FILE = Path.home() / ".spark" / "witness_state.json"


def save_state(state: dict):
    """Save witness state."""
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2, default=str)


def load_state() -> dict:
    """Load witness state."""
    if STATE_FILE.exists():
        with open(STATE_FILE) as f:
            return json.load(f)
    return {}


def get_learnings(limit: int = 100) -> list:
    """Get learnings from Mind. Note: API max limit is 100."""
    limit = min(limit, 100)  # API enforces max 100
    import requests
    try:
        resp = requests.post(
            "http://localhost:8080/v1/memories/retrieve",
            json={"query": "LEARNING", "limit": limit},
            timeout=5
        )
        return resp.json().get("memories", [])
    except Exception as e:
        print(f"  [!] Mind query failed: {e}")
        return []


def get_queue_events(limit: int = 10) -> list:
    """Get recent events from queue."""
    events = []
    queue_file = Path.home() / ".spark" / "queue" / "events.jsonl"
    if queue_file.exists():
        with open(queue_file) as f:
            lines = f.readlines()
            for line in lines[-limit:]:
                try:
                    events.append(json.loads(line.strip()))
                except:
                    pass
    return events


def cmd_baseline(args):
    """Capture baseline state."""
    print("")
    print("  +=========================================+")
    print("  |   SPARK WITNESS - Baseline Capture      |")
    print("  +=========================================+")
    print("")

    q = SparkQueue()
    queue_size = q.size()
    learnings = get_learnings(100)
    timestamp = datetime.now().isoformat()

    # Get learning IDs for delta comparison
    learning_ids = [l.get("memory_id") for l in learnings]

    state = {
        "timestamp": timestamp,
        "queue_size": queue_size,
        "learning_count": len(learnings),
        "learning_ids": learning_ids
    }
    save_state(state)

    print(f"  Timestamp:     {timestamp}")
    print(f"  Queue size:    {queue_size} events")
    print(f"  Learnings:     {len(learnings)} stored")
    print(f"")
    print(f"  [OK] Baseline saved. Now do some work, then run:")
    print(f"       python spark_witness.py live")


def cmd_watch(args):
    """Show queue activity."""
    print("")
    print("  +=========================================+")
    print("  |   SPARK WITNESS - Queue Activity        |")
    print("  +=========================================+")
    print("")

    q = SparkQueue()
    queue_size = q.size()
    events = get_queue_events(args.limit)

    print(f"  Queue size: {queue_size} events")
    print("")

    if events:
        print("  Recent events:")
        print("  " + "-" * 50)
        for e in events[-args.limit:]:
            tool = e.get("tool_name", "?")
            ts_raw = e.get("timestamp", 0)
            ts = datetime.fromtimestamp(ts_raw).strftime("%H:%M:%S") if isinstance(ts_raw, (int, float)) else str(ts_raw)[:19]
            success = "[OK]" if e.get("success", True) else "[FAIL]"
            duration = e.get("duration_ms") or 0
            print(f"  {success} [{ts}] {tool} ({duration:.0f}ms)")
    else:
        print("  (no events in queue)")


def cmd_process(args):
    """Trigger learning from queue."""
    print("")
    print("  +=========================================+")
    print("  |   SPARK WITNESS - Processing            |")
    print("  +=========================================+")
    print("")

    q = SparkQueue()
    before_size = q.size()
    print(f"  Queue before: {before_size} events")

    if before_size == 0:
        print("  (nothing to process)")
        return

    # Process events via processor.py
    import subprocess
    print("  Running processor...")
    result = subprocess.run(
        [sys.executable, "processor.py", "--mode", "once"],
        capture_output=True,
        text=True,
        cwd=Path(__file__).parent
    )

    if result.returncode == 0:
        # Extract key info from output
        output_lines = result.stdout.strip().split('\n')
        for line in output_lines[-5:]:
            if 'pattern' in line.lower() or 'learning' in line.lower() or 'processed' in line.lower():
                print(f"  {line.strip()}")
        print(f"")
        print(f"  [OK] Processing complete")
    else:
        print(f"  [!] Processor error: {result.stderr[:200]}")


def cmd_delta(args):
    """Show what was learned since baseline."""
    print("")
    print("  +=========================================+")
    print("  |   SPARK WITNESS - Learning Delta        |")
    print("  +=========================================+")
    print("")

    state = load_state()
    if not state:
        print("  [!] No baseline found. Run: python spark_witness.py baseline")
        return

    baseline_ts = state.get("timestamp", "?")
    baseline_count = state.get("learning_count", 0)
    baseline_ids = set(state.get("learning_ids", []))

    print(f"  Baseline: {baseline_ts}")
    print(f"  Baseline learnings: {baseline_count}")
    print("")

    # Get current learnings
    current_learnings = get_learnings(200)
    current_ids = set(l.get("memory_id") for l in current_learnings)

    # Find new learnings
    new_ids = current_ids - baseline_ids
    new_learnings = [l for l in current_learnings if l.get("memory_id") in new_ids]

    print(f"  Current learnings: {len(current_learnings)}")
    print(f"  NEW learnings: {len(new_learnings)}")

    if new_learnings:
        print("")
        print("  " + "=" * 50)
        print("  NEW LEARNINGS (what Spark just learned):")
        print("  " + "=" * 50)
        for l in new_learnings[:10]:
            content = l.get("content", "")[:80]
            print(f"")
            print(f"  * {content}...")
    else:
        print("")
        print("  (no new learnings yet - try 'process' first)")


def cmd_live(args):
    """All-in-one: watch -> process -> delta."""
    print("")
    print("  +=========================================+")
    print("  |   SPARK WITNESS - Live Learning         |")
    print("  +=========================================+")
    print("")

    state = load_state()
    baseline_ts = state.get("timestamp", "none")
    baseline_ids = set(state.get("learning_ids", []))

    print(f"  Baseline: {baseline_ts}")
    print("")

    # 1. Show queue
    q = SparkQueue()
    queue_size = q.size()
    events = get_queue_events(5)

    print(f"  +-- QUEUE ({queue_size} events)")
    if events:
        for e in events[-5:]:
            tool = e.get("tool_name", "?")
            success = "[OK]" if e.get("success", True) else "[FAIL]"
            print(f"  |   {success} {tool}")
    else:
        print("  |   (empty)")
    print("  +" + "-" * 30)

    # 2. Process
    if queue_size > 0:
        print(f"")
        print(f"  Processing {queue_size} events...")
        import subprocess
        result = subprocess.run(
            [sys.executable, "processor.py", "--mode", "once"],
            capture_output=True,
            text=True,
            cwd=Path(__file__).parent
        )
        if result.returncode == 0:
            # Count patterns from output
            output = result.stdout
            if 'pattern' in output.lower():
                print(f"  -> Patterns extracted!")
            else:
                print(f"  -> Processing complete")

    # 3. Show delta
    print("")
    print("  +-- NEW LEARNINGS (this session)")
    current_learnings = get_learnings(200)
    current_ids = set(l.get("memory_id") for l in current_learnings)
    new_ids = current_ids - baseline_ids
    new_learnings = [l for l in current_learnings if l.get("memory_id") in new_ids]

    if new_learnings:
        for l in new_learnings[:5]:
            content = l.get("content", "")
            # Extract the pattern type
            if "[" in content and "]" in content:
                ptype = content.split("[")[1].split("]")[0]
                rest = content.split("]:")[1][:50] if "]:" in content else content[:50]
                print(f"  |   [{ptype}] {rest}...")
            else:
                print(f"  |   {content[:60]}...")
        if len(new_learnings) > 5:
            print(f"  |   ... and {len(new_learnings) - 5} more")
    else:
        print("  |   (none yet)")
    print("  +" + "-" * 30)

    print(f"")
    print(f"  Total learnings: {len(current_learnings)} (+{len(new_learnings)} new)")


def main():
    parser = argparse.ArgumentParser(
        description="Watch Spark learn in real-time",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )

    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # baseline
    p_baseline = subparsers.add_parser("baseline", help="Capture starting state")
    p_baseline.set_defaults(func=cmd_baseline)

    # watch
    p_watch = subparsers.add_parser("watch", help="Show queue activity")
    p_watch.add_argument("-n", "--limit", type=int, default=10, help="Number of events")
    p_watch.set_defaults(func=cmd_watch)

    # process
    p_process = subparsers.add_parser("process", help="Trigger learning")
    p_process.set_defaults(func=cmd_process)

    # delta
    p_delta = subparsers.add_parser("delta", help="Show new learnings")
    p_delta.set_defaults(func=cmd_delta)

    # live
    p_live = subparsers.add_parser("live", help="All-in-one: watch -> process -> delta")
    p_live.set_defaults(func=cmd_live)

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        return

    args.func(args)


if __name__ == "__main__":
    main()
