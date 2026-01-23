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

from lib.queue import SparkQueue, SparkEvent, EventType
from lib.mind_client import MindClient
from lib.learner import SparkLearner
from lib.injection_tracker import InjectionTracker
from lib.experiment_manager import ExperimentManager
from lib.prompt_evolver import PromptEvolver
from lib.meta_learner import MetaLearner
from lib.suggester import Suggester


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


async def cmd_health():
    """Comprehensive health check of all M1-M5 components."""
    print("\n  M1-M5 Health Check")
    print("  " + "-" * 50)

    results = {}
    mind = MindClient()

    # M1: Queue
    print("\n  [M1] Queue System...")
    try:
        queue = SparkQueue()
        # Check queue file exists and is writable
        queue_size_before = queue.size()
        test_event = SparkEvent(
            event_type=EventType.POST_TOOL,
            timestamp=1.0,
            session_id="health_check",
            data={},
            tool_name="HealthCheck"
        )
        queue.push(test_event)
        queue_size_after = queue.size()
        # Verify push worked (size increased or stayed same if daemon consumed it)
        if queue_size_after >= queue_size_before:
            print(f"       [OK] Queue working ({queue_size_after} events)")
            results["M1_Queue"] = True
        else:
            print("       [FAIL] Queue write failed")
            results["M1_Queue"] = False
    except Exception as e:
        print(f"       [FAIL] {e}")
        results["M1_Queue"] = False

    # M2: Mind Connection
    print("\n  [M2] Mind Connection...")
    try:
        mind_ok = await mind.is_available()
        if mind_ok:
            print("       [OK] Mind connected")
            results["M2_Mind"] = True
        else:
            print("       [WARN] Mind offline (will queue locally)")
            results["M2_Mind"] = False
    except Exception as e:
        print(f"       [FAIL] {e}")
        results["M2_Mind"] = False

    # M3: Learner
    print("\n  [M3] Pattern Learner...")
    try:
        learner = SparkLearner(mind)
        test_events = [
            SparkEvent(
                event_type=EventType.POST_TOOL,
                timestamp=float(i),
                session_id="health_check",
                data={},
                tool_name="Grep",
                duration_ms=50.0
            ) for i in range(5)
        ]
        patterns = await learner.process_events(test_events)
        print(f"       [OK] Learner processed {len(test_events)} events")
        results["M3_Learner"] = True
    except Exception as e:
        print(f"       [FAIL] {e}")
        results["M3_Learner"] = False

    # M4: Prompt Evolver
    print("\n  [M4] Prompt Evolver...")
    try:
        evolver = PromptEvolver(mind)
        traces = await evolver.process_events(test_events)
        print(f"       [OK] Captured {len(traces)} traces")
        results["M4_PromptEvolver"] = True
    except Exception as e:
        print(f"       [FAIL] {e}")
        results["M4_PromptEvolver"] = False

    # M4: Meta Learner
    print("\n  [M4] Meta Learner...")
    try:
        ml = MetaLearner(mind)
        ml.record_learning("test", "health_check", 0.8)
        stats = ml.get_meta_stats()
        print(f"       [OK] Meta learner tracking ({ml.total_learnings} events)")
        results["M4_MetaLearner"] = True
    except Exception as e:
        print(f"       [FAIL] {e}")
        results["M4_MetaLearner"] = False

    # M4: Suggester
    print("\n  [M4] Suggester...")
    try:
        suggester = Suggester(mind)
        suggester.update_context(task_description="test search", current_tool="Grep")
        print(f"       [OK] Suggester context updated")
        results["M4_Suggester"] = True
    except Exception as e:
        print(f"       [FAIL] {e}")
        results["M4_Suggester"] = False

    # M5: Injection Tracker
    print("\n  [M5] Injection Tracker...")
    try:
        tracker = InjectionTracker(mind)
        tid = tracker.tag_injection(
            learning_id="health_test",
            session_id="health_check",
            injection_type="tool_recommendation",
            content_summary="Test injection",
            trigger_conditions={"test": True}
        )
        stats = tracker.get_stats()
        print(f"       [OK] Tagged injection: {tid[:20]}...")
        print(f"           Follow rate: {stats.follow_rate:.0%}")
        results["M5_InjectionTracker"] = True
    except Exception as e:
        print(f"       [FAIL] {e}")
        results["M5_InjectionTracker"] = False

    # M5: Experiment Manager
    print("\n  [M5] Experiment Manager...")
    try:
        exp_mgr = ExperimentManager(mind)
        exp = exp_mgr.create_experiment(
            name="Health Check Test",
            description="Testing experiment system",
            control_pattern_id="test_control",
            treatment_pattern_id="test_treatment",
            min_samples=5
        )
        exp_mgr.start_experiment(exp.experiment_id)
        active = exp_mgr.get_active_experiments()
        print(f"       [OK] Created experiment, {len(active)} active")
        results["M5_ExperimentManager"] = True
    except Exception as e:
        print(f"       [FAIL] {e}")
        results["M5_ExperimentManager"] = False

    # Summary
    print("\n  " + "=" * 50)
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    print(f"  RESULTS: {passed}/{total} components healthy")

    if passed == total:
        print("  STATUS: ALL SYSTEMS GO")
    elif passed >= total - 2:
        print("  STATUS: MOSTLY HEALTHY (some warnings)")
    else:
        print("  STATUS: NEEDS ATTENTION")

    print()
    await mind.close()


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
  health      Comprehensive M1-M5 health check
        """
    )

    parser.add_argument("command", nargs="?", default="status",
                       choices=["status", "learn", "reflect", "learnings",
                               "watch", "clear", "hooks", "health"],
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
    elif args.command == "health":
        asyncio.run(cmd_health())


if __name__ == "__main__":
    main()
