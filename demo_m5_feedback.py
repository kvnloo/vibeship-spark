#!/usr/bin/env python3
"""
M5 Feedback Loop Demo - Live Test

This script demonstrates the feedback loop in action:
1. Inject advice (tag it for tracking)
2. Simulate tool usage (observe events)
3. See outcomes determined
4. Watch confidence adjust

Run this while streaming to show M5 working!
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from lib.injection_tracker import InjectionTracker, InjectionOutcome
from lib.experiment_manager import ExperimentManager
from lib.queue import SparkEvent, EventType
from lib.mind_client import MindClient


async def demo_injection_tracking():
    """Demo the injection tracking feedback loop."""
    print("\n" + "=" * 60)
    print("  M5 FEEDBACK LOOP DEMO - Injection Tracking")
    print("=" * 60)

    # Create tracker (optionally with Mind for persistence)
    mind = MindClient()
    mind_available = await mind.is_available()

    if mind_available:
        print("\n[Mind connected - feedback will persist]")
        tracker = InjectionTracker(mind_client=mind)
    else:
        print("\n[Mind offline - feedback in memory only]")
        tracker = InjectionTracker()

    # 1. INJECT ADVICE
    print("\n--- Step 1: Inject Advice ---")

    # Tag a tool recommendation
    tracking_id_1 = tracker.tag_injection(
        learning_id="grep_effective_for_search",
        session_id="demo_session",
        injection_type="tool_recommendation",
        content_summary="Use Grep for code search",
        trigger_conditions={"recommended_tool": "Grep", "task": "search"}
    )
    print(f"  Tagged: 'Use Grep for code search' -> {tracking_id_1}")

    # Tag an error warning
    tracking_id_2 = tracker.tag_injection(
        learning_id="timeout_warning",
        session_id="demo_session",
        injection_type="error_warning",
        content_summary="Avoid long-running commands",
        trigger_conditions={"warned_error": "timeout", "warned_tool": "Bash"}
    )
    print(f"  Tagged: 'Avoid timeout errors' -> {tracking_id_2}")

    print(f"\n  Stats: {tracker.stats.total_injections} injections tagged")

    # 2. SIMULATE EVENTS
    print("\n--- Step 2: Simulate Tool Usage ---")

    # Event: User uses Grep (follows recommendation!)
    event1 = SparkEvent(
        event_type=EventType.POST_TOOL,
        timestamp=1.0,
        session_id="demo_session",
        data={},
        tool_name="Grep"
    )
    result1 = tracker.observe_event(event1)
    print(f"  Event: Grep used")
    if result1:
        print(f"    -> Outcome determined for {result1}!")

    # Event: User uses Bash successfully (heeds warning!)
    event2 = SparkEvent(
        event_type=EventType.POST_TOOL,
        timestamp=2.0,
        session_id="demo_session",
        data={},
        tool_name="Bash"
    )
    result2 = tracker.observe_event(event2)
    print(f"  Event: Bash used successfully")

    # Manually determine the error warning outcome
    tracker.determine_outcome(
        tracking_id_2,
        InjectionOutcome.FOLLOWED,
        ["Bash used without timeout"]
    )
    print(f"    -> Warning was heeded (no timeout occurred)")

    # 3. CHECK OUTCOMES
    print("\n--- Step 3: Check Outcomes ---")

    for inj in tracker.completed_injections:
        delta_str = f"+{inj.confidence_delta:.0%}" if inj.confidence_delta > 0 else f"{inj.confidence_delta:.0%}"
        print(f"  {inj.content_summary}")
        print(f"    Outcome: {inj.outcome.value} | Confidence delta: {delta_str}")

    # 4. SHOW STATS
    print("\n--- Step 4: Feedback Loop Stats ---")
    stats = tracker.get_stats()
    print(f"  Total injections: {stats.total_injections}")
    print(f"  Outcomes determined: {stats.outcomes_determined}")
    print(f"  Followed: {stats.followed_count}")
    print(f"  Ignored: {stats.ignored_count}")
    print(f"  Follow rate: {stats.follow_rate:.0%}")

    # 5. UPDATE CONFIDENCE (persist to Mind)
    print("\n--- Step 5: Update Learning Confidence ---")
    for inj in tracker.completed_injections:
        delta = await tracker.update_learning_confidence(inj.tracking_id)
        if delta != 0:
            print(f"  Updated '{inj.content_summary}' confidence by {delta:+.0%}")

    await mind.close()
    print("\n" + "=" * 60)
    print("  FEEDBACK LOOP COMPLETE")
    print("=" * 60)


async def demo_experiment():
    """Demo the A/B experimentation system."""
    print("\n" + "=" * 60)
    print("  M5 FEEDBACK LOOP DEMO - A/B Experiments")
    print("=" * 60)

    manager = ExperimentManager()

    # 1. CREATE EXPERIMENT
    print("\n--- Step 1: Create Experiment ---")
    exp = manager.create_experiment(
        name="Grep vs Glob for Search",
        description="Which tool works better for code search?",
        control_pattern_id="grep_pattern",
        treatment_pattern_id="glob_pattern",
        min_samples=10,  # Low for demo
        task_category="search"
    )
    print(f"  Created: '{exp.name}'")
    print(f"  Control: {exp.control.pattern_id}")
    print(f"  Treatment: {exp.treatment.pattern_id}")

    # 2. START EXPERIMENT
    print("\n--- Step 2: Start Experiment ---")
    manager.start_experiment(exp.experiment_id)
    print(f"  Status: {exp.status.value}")

    # 3. SIMULATE SESSIONS
    print("\n--- Step 3: Simulate 20 Sessions ---")

    for i in range(20):
        session_id = f"session_{i}"

        # Random assignment
        arm = manager.assign_session(session_id, exp.experiment_id)

        # Simulate outcome (treatment is 20% better)
        import random
        if arm == "control":
            success = random.random() < 0.6  # 60% success
        else:
            success = random.random() < 0.8  # 80% success (treatment is better)

        manager.record_outcome(session_id, exp.experiment_id, success)

        if i % 5 == 4:
            print(f"  After {i+1} sessions:")
            print(f"    Control: {exp.control.success_rate:.0%} ({exp.control.total_trials} trials)")
            print(f"    Treatment: {exp.treatment.success_rate:.0%} ({exp.treatment.total_trials} trials)")

    # 4. ANALYZE
    print("\n--- Step 4: Statistical Analysis ---")
    result = manager.analyze(exp.experiment_id)

    if result:
        print(f"  Control success rate: {result.control_success_rate:.0%}")
        print(f"  Treatment success rate: {result.treatment_success_rate:.0%}")
        print(f"  Relative improvement: {result.relative_improvement:+.0%}")
        print(f"  P-value: {result.p_value:.4f}")
        print(f"  Significant: {result.is_significant}")
        print(f"  Recommended winner: {result.recommended_winner}")

    # 5. AUTO-CONCLUDE
    print("\n--- Step 5: Conclude ---")
    auto_result = manager.auto_conclude_if_significant(exp.experiment_id)

    if auto_result:
        print(f"  Experiment concluded!")
        print(f"  Winner: {exp.winner}")
        print(f"  Status: {exp.status.value}")
    else:
        print(f"  Not yet significant, need more data")

    print("\n" + "=" * 60)
    print("  EXPERIMENT COMPLETE")
    print("=" * 60)


async def main():
    """Run all demos."""
    print("\n" + "#" * 60)
    print("#  M5 FEEDBACK LOOP - LIVE DEMO")
    print("#" * 60)

    await demo_injection_tracking()
    await demo_experiment()

    print("\n" + "#" * 60)
    print("#  M5 IS WORKING!")
    print("#" * 60)
    print("\nThe feedback loop is now active in Spark.")
    print("Every injection will be tracked.")
    print("Every outcome will adjust confidence.")
    print("Experiments will prove which patterns work best.\n")


if __name__ == "__main__":
    asyncio.run(main())
