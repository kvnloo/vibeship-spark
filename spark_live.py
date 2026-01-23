#!/usr/bin/env python3
"""
Spark Live - Real-time intelligence dashboard.

See everything Spark is learning as it happens:
- Goals being tracked
- Predictions being made
- Advice being followed (or not)
- Patterns being extracted
- Strategies being learned

Usage:
  python spark_live.py          # Full dashboard
  python spark_live.py goals    # Just goals
  python spark_live.py predict  # Just predictions
  python spark_live.py advice   # Just advice tracking
  python spark_live.py learn    # Just learnings
  python spark_live.py process  # Process queue and show new learnings
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

# Add lib to path
sys.path.insert(0, str(Path(__file__).parent))

from lib.queue import SparkQueue

# File paths
SPARK_DIR = Path.home() / ".spark"
PREDICTIONS_FILE = SPARK_DIR / "predictions.json"
INJECTIONS_FILE = SPARK_DIR / "active_injections.json"
GOALS_FILE = SPARK_DIR / "active_goals.json"


def load_json(path: Path) -> dict:
    """Load JSON file safely."""
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text())
    except:
        return {}


def format_time(ts: float) -> str:
    """Format timestamp as readable time."""
    return datetime.fromtimestamp(ts).strftime("%H:%M:%S")


def format_duration(seconds: float) -> str:
    """Format duration as readable string."""
    if seconds < 60:
        return f"{seconds:.0f}s"
    elif seconds < 3600:
        return f"{seconds/60:.1f}m"
    else:
        return f"{seconds/3600:.1f}h"


def show_header():
    """Show dashboard header."""
    print()
    print("  +=============================================+")
    print("  |   SPARK LIVE - Intelligence Dashboard      |")
    print("  +=============================================+")
    print()


def show_goals():
    """Show goal tracking status."""
    print("  GOALS (What you're trying to achieve)")
    print("  " + "-" * 50)

    goals = load_json(GOALS_FILE)
    if not goals:
        print("  (no goals tracked yet)")
        return

    active = []
    completed = []

    for g_id, g in goals.items():
        if g.get("status") == "active":
            active.append(g)
        elif g.get("status") == "completed":
            completed.append(g)

    if active:
        print("  Active:")
        for g in active:
            goal_type = g.get("goal_type", "?")
            desc = g.get("description", "?")[:40]
            actions = len(g.get("actions", []))
            duration = datetime.now().timestamp() - g.get("created_at", 0)
            print(f"    [{goal_type.upper()}] {desc}")
            print(f"      Actions: {actions} | Duration: {format_duration(duration)}")

    if completed:
        print("  Completed:")
        for g in completed[-3:]:  # Last 3
            goal_type = g.get("goal_type", "?")
            desc = g.get("description", "?")[:35]
            success = g.get("success_score", 0)
            actions = len(g.get("actions", []))
            print(f"    [{goal_type.upper()}] {desc}...")
            print(f"      Success: {success:.0%} | Actions: {actions}")

    print()


def show_predictions():
    """Show prediction tracking status."""
    print("  PREDICTIONS (What I expect to happen)")
    print("  " + "-" * 50)

    predictions = load_json(PREDICTIONS_FILE)
    if not predictions:
        print("  (no active predictions)")
        return

    for key, pred in list(predictions.items())[:5]:
        tool = pred.get("tool_name", "?")
        intent = pred.get("intent", "?")[:30]
        confidence = pred.get("confidence", 0)
        risks = pred.get("risks", [])

        print(f"    {tool}: {intent}")
        print(f"      Confidence: {confidence:.0%}", end="")
        if risks:
            print(f" | Risks: {risks[0]}")
        else:
            print()

    print()


def show_advice():
    """Show advice feedback status."""
    print("  ADVICE FEEDBACK (Is my advice being followed?)")
    print("  " + "-" * 50)

    injections = load_json(INJECTIONS_FILE)
    if not injections:
        print("  (no advice tracked)")
        return

    followed = 0
    ignored = 0
    pending = 0

    for inj_id, inj in injections.items():
        outcome = inj.get("outcome", "pending")
        if outcome == "followed":
            followed += 1
        elif outcome == "ignored":
            ignored += 1
        else:
            pending += 1

    total = followed + ignored + pending
    follow_rate = followed / (followed + ignored) if (followed + ignored) > 0 else 0

    print(f"    Total advice given: {total}")
    print(f"    Followed: {followed} | Ignored: {ignored} | Pending: {pending}")
    print(f"    Follow rate: {follow_rate:.0%}")

    # Show recent
    print()
    print("    Recent advice:")
    for inj_id, inj in list(injections.items())[-3:]:
        summary = inj.get("content_summary", "?")[:35]
        outcome = inj.get("outcome", "pending")
        status_icon = {"followed": "[OK]", "ignored": "[--]", "pending": "[..]"}.get(outcome, "[?]")
        print(f"      {status_icon} {summary}")

    print()


def show_learnings():
    """Show what's been learned."""
    print("  LEARNINGS (What I've figured out)")
    print("  " + "-" * 50)

    import requests
    try:
        resp = requests.post(
            "http://localhost:8080/v1/memories/retrieve",
            json={"query": "LEARNING", "limit": 20},
            timeout=3
        )
        memories = resp.json().get("memories", [])
    except:
        print("  (Mind not available)")
        return

    if not memories:
        print("  (no learnings yet)")
        return

    # Group by type
    by_type = {}
    for m in memories:
        content = m.get("content", "")
        if "[" in content and "]" in content:
            ptype = content.split("[")[1].split("]")[0]
            if ptype not in by_type:
                by_type[ptype] = []
            by_type[ptype].append(content)

    # Show by type
    for ptype, contents in by_type.items():
        print(f"    {ptype}: {len(contents)} patterns")
        # Show first example
        if contents:
            example = contents[0]
            if "]:" in example:
                example = example.split("]:")[1].strip()[:50]
            print(f"      e.g., {example}...")

    print()


def show_queue():
    """Show queue status."""
    print("  QUEUE (Pending events)")
    print("  " + "-" * 50)

    q = SparkQueue()
    size = q.size()
    print(f"    Events waiting: {size}")

    # Show recent events from file
    queue_file = SPARK_DIR / "queue" / "events.jsonl"
    if queue_file.exists():
        lines = queue_file.read_text().strip().split("\n")
        if lines and lines[0]:
            print(f"    Recent events:")
            for line in lines[-5:]:
                try:
                    e = json.loads(line)
                    tool = e.get("tool_name", "?")
                    event_type = e.get("event_type", "?")
                    print(f"      {event_type}: {tool}")
                except:
                    pass

    print()


def show_strategies():
    """Show learned strategies."""
    print("  STRATEGIES (What works for what)")
    print("  " + "-" * 50)

    goals = load_json(GOALS_FILE)

    # Group completed goals by type
    by_type = {}
    for g_id, g in goals.items():
        if g.get("status") == "completed":
            goal_type = g.get("goal_type", "unknown")
            if goal_type not in by_type:
                by_type[goal_type] = []
            by_type[goal_type].append(g)

    if not by_type:
        print("  (not enough data yet - complete more goals)")
        return

    for goal_type, completed in by_type.items():
        if len(completed) >= 1:
            # Get average success
            success_scores = [g.get("success_score", 0.5) for g in completed]
            avg_success = sum(success_scores) / len(success_scores)

            # Get common tool sequence
            sequences = []
            for g in completed:
                actions = g.get("actions", [])
                seq = [a.get("tool") for a in actions if a.get("tool")][:5]
                if seq:
                    sequences.append(" -> ".join(seq))

            print(f"    {goal_type.upper()}: {len(completed)} completed ({avg_success:.0%} avg success)")
            if sequences:
                print(f"      Approach: {sequences[-1]}")

    print()


def process_and_learn():
    """Process queue and show new learnings."""
    print("  PROCESSING QUEUE...")
    print("  " + "-" * 50)

    import subprocess
    result = subprocess.run(
        [sys.executable, "processor.py", "--mode", "once"],
        capture_output=True,
        text=True,
        cwd=Path(__file__).parent
    )

    if result.returncode == 0:
        print("  [OK] Processing complete")
        # Show relevant output
        for line in result.stdout.split("\n"):
            if "pattern" in line.lower() or "learning" in line.lower():
                print(f"  {line.strip()}")
    else:
        print(f"  [!] Error: {result.stderr[:100]}")

    print()


def show_full_dashboard():
    """Show full dashboard."""
    show_header()
    show_goals()
    show_predictions()
    show_advice()
    show_queue()
    show_learnings()
    show_strategies()

    print("  " + "=" * 50)
    print("  Commands: goals | predict | advice | learn | process")
    print()


def main():
    parser = argparse.ArgumentParser(description="Spark Live Intelligence Dashboard")
    parser.add_argument("view", nargs="?", default="all",
                       choices=["all", "goals", "predict", "advice", "learn", "process", "queue", "strategies"],
                       help="What to show")

    args = parser.parse_args()

    if args.view == "all":
        show_full_dashboard()
    elif args.view == "goals":
        show_header()
        show_goals()
    elif args.view == "predict":
        show_header()
        show_predictions()
    elif args.view == "advice":
        show_header()
        show_advice()
    elif args.view == "learn":
        show_header()
        show_learnings()
    elif args.view == "queue":
        show_header()
        show_queue()
    elif args.view == "strategies":
        show_header()
        show_strategies()
    elif args.view == "process":
        show_header()
        process_and_learn()
        show_learnings()


if __name__ == "__main__":
    main()
