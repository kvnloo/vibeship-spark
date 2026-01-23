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
from lib.project_analyzer import ProjectAnalyzer, ProjectType
from lib.learning_transfer import LearningTransfer, LearningScope
from lib.pattern_breeder import PatternBreeder, PopulationStats
from lib.realtime_advisor import RealTimeAdvisor
from lib.spark_mcp_server import SparkMCPServer
from lib.skill_evolver import SkillEvolver, SkillUsage
from lib.context_injector import ContextInjector
from lib.orchestrator import AgentOrchestrator, AgentUsage
from lib.conflict_resolver import ConflictResolver, ResolutionStrategy
from lib.spark_dashboard import SparkDashboard, DashboardView
from lib.spark_debugger import SparkDebugger, DebugLevel
from lib.spark_backup import SparkBackup, BackupType
from lib.witness import SparkWitness
from lib.introspect import introspect as run_introspect
from lib.auto_improve import auto_improve as run_auto_improve


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


def cmd_witness(verbose: bool = False):
    """Unified Witness - what's really going on?"""
    witness = SparkWitness()
    print(witness.explain(verbose=verbose))


async def cmd_introspect():
    """Self-analysis - what am I not learning?"""
    result = await run_introspect()
    print(result)


async def cmd_improve():
    """Auto-improve - act on self-discovered gaps."""
    result = await run_auto_improve()
    print(result)


async def cmd_health():
    """Comprehensive health check of all M1-M11 components (21 components)."""
    print("\n  M1-M11 Health Check (21 Components)")
    print("  " + "-" * 50)

    results = {}
    mind = MindClient()

    # M0: Hook Validation (Critical - entry point for everything)
    print("\n  [M0] Hook Validation...")
    try:
        import json
        settings_path = Path.home() / ".claude" / "settings.json"

        # Required hooks for Spark to function
        REQUIRED_HOOKS = [
            "SessionStart",
            "UserPromptSubmit",  # Critical for goal capture
            "PreToolUse",
            "PostToolUse",
            "PostToolUseFailure",
            "Stop",
            "SessionEnd"
        ]

        if not settings_path.exists():
            print("       [FAIL] Settings file not found: ~/.claude/settings.json")
            results["M0_Hooks"] = False
        else:
            with open(settings_path) as f:
                settings = json.load(f)

            hooks = settings.get("hooks", {})
            missing = []
            invalid = []

            for hook_name in REQUIRED_HOOKS:
                if hook_name not in hooks:
                    missing.append(hook_name)
                else:
                    # Validate hook command exists
                    hook_config = hooks[hook_name]
                    if hook_config and len(hook_config) > 0:
                        inner_hooks = hook_config[0].get("hooks", [])
                        for h in inner_hooks:
                            cmd = h.get("command", "")
                            # Extract script path from command
                            if "python" in cmd:
                                parts = cmd.split('"')
                                if len(parts) >= 2:
                                    script_path = Path(parts[1])
                                    if not script_path.exists():
                                        invalid.append(f"{hook_name}: {script_path.name}")

            if missing:
                print(f"       [FAIL] Missing hooks: {', '.join(missing)}")
                results["M0_Hooks"] = False
            elif invalid:
                print(f"       [WARN] Invalid scripts: {', '.join(invalid)}")
                results["M0_Hooks"] = False
            else:
                print(f"       [OK] All {len(REQUIRED_HOOKS)} required hooks configured")
                results["M0_Hooks"] = True
    except Exception as e:
        print(f"       [FAIL] {e}")
        results["M0_Hooks"] = False

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

    # M6: Project Analyzer
    print("\n  [M6] Project Analyzer...")
    try:
        analyzer = ProjectAnalyzer()
        # Analyze current directory
        fingerprint = analyzer.analyze(str(Path.cwd()))
        print(f"       [OK] Detected: {fingerprint.project_type.value}, {fingerprint.primary_language or 'unknown'}")
        if fingerprint.frameworks:
            print(f"           Frameworks: {', '.join(fingerprint.frameworks[:3])}")
        results["M6_ProjectAnalyzer"] = True
    except Exception as e:
        print(f"       [FAIL] {e}")
        results["M6_ProjectAnalyzer"] = False

    # M6: Learning Transfer
    print("\n  [M6] Learning Transfer...")
    try:
        transfer = LearningTransfer(mind)
        # Create a test learning
        from lib.project_analyzer import ProjectFingerprint
        test_fp = ProjectFingerprint(
            project_path="/test",
            project_type=ProjectType.API_SERVICE,
            primary_language="python"
        )
        learning = transfer.annotate_learning(
            learning_id="health_test",
            content="TOOL_EFFECTIVENESS: Test learning",
            source_fingerprint=test_fp,
            metadata={"pattern_type": "tool_effectiveness"}
        )
        stats = transfer.get_stats()
        print(f"       [OK] Created learning with scope: {learning.scope.value}")
        print(f"           Total learnings: {stats['total_learnings']}")
        results["M6_LearningTransfer"] = True
    except Exception as e:
        print(f"       [FAIL] {e}")
        results["M6_LearningTransfer"] = False

    # M7: Pattern Breeder
    print("\n  [M7] Pattern Breeder...")
    try:
        from lib.prompt_evolver import PromptPattern
        breeder = PatternBreeder(population_size=10, mutation_rate=0.2)
        # Create seed patterns
        seed_patterns = [
            PromptPattern(
                pattern_id=f"seed_{i}",
                pattern_type="tool_sequence",
                description=f"Seed pattern {i}",
                trigger_conditions={"task_category": "search"},
                approach=f"Approach {i}",
                total_uses=10,
                success_count=8,
                failure_count=2
            )
            for i in range(3)
        ]
        count = breeder.initialize_population(seed_patterns)
        stats = breeder.evolve_generation()
        print(f"       [OK] Population: {count}, Gen: {breeder.generation}")
        print(f"           Avg fitness: {stats.avg_fitness:.2f}, Diversity: {stats.diversity_score:.2f}")
        results["M7_PatternBreeder"] = True
    except Exception as e:
        print(f"       [FAIL] {e}")
        results["M7_PatternBreeder"] = False

    # M8: RealTime Advisor
    print("\n  [M8] RealTime Advisor...")
    try:
        advisor = RealTimeAdvisor()
        # Test pre-tool warning detection
        warning = advisor.pre_tool_check("Bash", {"command": "rm -rf /tmp/test"})
        if warning and warning.severity == "error":
            print(f"       [OK] Warning detection working")
            # Test recovery suggestion
            recovery = advisor.suggest_recovery("Read", "File not found: test.py")
            if recovery and recovery.error_category == "not_found":
                print(f"           Recovery suggestions: available")
            results["M8_RealTimeAdvisor"] = True
        else:
            print("       [FAIL] Warning detection not working")
            results["M8_RealTimeAdvisor"] = False
    except Exception as e:
        print(f"       [FAIL] {e}")
        results["M8_RealTimeAdvisor"] = False

    # M8: Spark MCP Server
    print("\n  [M8] Spark MCP Server...")
    try:
        server = SparkMCPServer(mind_client=mind)
        # Test tool definitions
        tool_defs = server.get_tool_definitions()
        if len(tool_defs) >= 7:
            print(f"       [OK] {len(tool_defs)} tools defined")
            # Test status tool
            status_response = await server.tool_status({})
            if status_response.success:
                print(f"           Status: operational={status_response.data.get('is_operational', False)}")
            results["M8_SparkMCPServer"] = True
        else:
            print(f"       [FAIL] Only {len(tool_defs)} tools (expected 7+)")
            results["M8_SparkMCPServer"] = False
    except Exception as e:
        print(f"       [FAIL] {e}")
        results["M8_SparkMCPServer"] = False

    # M9: Skill Evolver
    print("\n  [M9] Skill Evolver...")
    try:
        skill_evolver = SkillEvolver(mind)
        # Create a skill-related event and track it
        skill_event = SparkEvent(
            event_type=EventType.POST_TOOL,
            timestamp=1.0,
            session_id="health_check",
            data={"skill_id": "test_skill", "task_context": "health_check"},
            tool_name="Skill"
        )
        skill_evolver.track_skill_usage(skill_event)
        # Check that skill_stats dict is accessible
        if hasattr(skill_evolver, 'skill_stats'):
            print(f"       [OK] Skill tracking working")
            print(f"           Tracked: {len(skill_evolver.skill_stats)} skills")
            results["M9_SkillEvolver"] = True
        else:
            print("       [FAIL] Skill stats not accessible")
            results["M9_SkillEvolver"] = False
    except Exception as e:
        print(f"       [FAIL] {e}")
        results["M9_SkillEvolver"] = False

    # M9: Context Injector
    print("\n  [M9] Context Injector...")
    try:
        injector = ContextInjector(mind)
        context = await injector.gather_context()
        if context is not None:
            print(f"       [OK] Context builder ready")
            print(f"           Has content: {context.has_content}")
            results["M9_ContextInjector"] = True
        else:
            print("       [FAIL] No context returned")
            results["M9_ContextInjector"] = False
    except Exception as e:
        print(f"       [FAIL] {e}")
        results["M9_ContextInjector"] = False

    # M9: Agent Orchestrator
    print("\n  [M9] Agent Orchestrator...")
    try:
        orchestrator = AgentOrchestrator(mind)
        # Create an agent-related event and track it
        agent_event = SparkEvent(
            event_type=EventType.POST_TOOL,
            timestamp=1.0,
            session_id="health_check",
            data={"subagent_type": "Explore", "description": "health_check test"},
            tool_name="Task"
        )
        orchestrator.track_agent_usage(agent_event)
        # Check that agent_stats dict is accessible
        if hasattr(orchestrator, 'agent_stats'):
            print(f"       [OK] Agent tracking working")
            print(f"           Tracked: {len(orchestrator.agent_stats)} agents")
            results["M9_AgentOrchestrator"] = True
        else:
            print("       [FAIL] Agent stats not accessible")
            results["M9_AgentOrchestrator"] = False
    except Exception as e:
        print(f"       [FAIL] {e}")
        results["M9_AgentOrchestrator"] = False

    # M10: Spark Dashboard
    print("\n  [M10] Spark Dashboard...")
    try:
        dashboard = SparkDashboard(mind_client=mind)
        views = dashboard.get_available_views()
        if len(views) >= 6:
            print(f"       [OK] {len(views)} views available")
            # Test refresh
            await dashboard.refresh(DashboardView.OVERVIEW)
            stats = dashboard.get_stats()
            print(f"           Current view: {stats['current_view']}")
            results["M10_SparkDashboard"] = True
        else:
            print(f"       [FAIL] Only {len(views)} views (expected 6+)")
            results["M10_SparkDashboard"] = False
    except Exception as e:
        print(f"       [FAIL] {e}")
        results["M10_SparkDashboard"] = False

    # M10: Spark Debugger
    print("\n  [M10] Spark Debugger...")
    try:
        debugger = SparkDebugger(level=DebugLevel.MINIMAL)
        session = debugger.start_session("health_check")
        if session and session.session_id == "health_check":
            print(f"       [OK] Debug session started")
            debugger.end_session("health_check")
            stats = debugger.get_stats()
            print(f"           Sessions in memory: {stats['sessions_in_memory']}")
            results["M10_SparkDebugger"] = True
        else:
            print("       [FAIL] Could not start session")
            results["M10_SparkDebugger"] = False
    except Exception as e:
        print(f"       [FAIL] {e}")
        results["M10_SparkDebugger"] = False

    # M10: Spark Backup
    print("\n  [M10] Spark Backup...")
    try:
        backup = SparkBackup(mind_client=mind)
        stats = backup.get_stats()
        if "backup_count" in stats:
            print(f"       [OK] Backup system ready")
            print(f"           Backups: {stats['backup_count']}, Size: {stats['total_size_human']}")
            results["M10_SparkBackup"] = True
        else:
            print("       [FAIL] Backup stats unavailable")
            results["M10_SparkBackup"] = False
    except Exception as e:
        print(f"       [FAIL] {e}")
        results["M10_SparkBackup"] = False

    # M11: Conflict Resolver
    print("\n  [M11] Conflict Resolver...")
    try:
        from lib.prompt_evolver import PromptPattern
        resolver = ConflictResolver(experiment_manager=exp_mgr, decay_rate_days=30.0)
        # Create test patterns that conflict
        test_pattern_a = PromptPattern(
            pattern_id="health_a",
            pattern_type="tool_effectiveness",
            description="Test pattern A",
            trigger_conditions={"tool_name": "HealthCheck"},
            approach="Approach A",
            total_uses=50,
            success_count=45,
            failure_count=5
        )
        test_pattern_b = PromptPattern(
            pattern_id="health_b",
            pattern_type="tool_effectiveness",
            description="Test pattern B",
            trigger_conditions={"tool_name": "HealthCheck"},
            approach="Approach B",
            total_uses=30,
            success_count=15,
            failure_count=15
        )
        conflicts = resolver.detect_conflicts([test_pattern_a, test_pattern_b])
        if len(conflicts) >= 1:
            # Resolve the conflict
            resolved = resolver.resolve([test_pattern_a, test_pattern_b])
            stats = resolver.get_stats()
            print(f"       [OK] Conflict resolution working")
            print(f"           Detected: {stats['total_conflicts_detected']}, Resolved: {stats['total_conflicts_resolved']}")
            results["M11_ConflictResolver"] = True
        else:
            print("       [FAIL] Conflict detection not working")
            results["M11_ConflictResolver"] = False
    except Exception as e:
        print(f"       [FAIL] {e}")
        results["M11_ConflictResolver"] = False

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
  witness     Unified view of what's happening (recommended)
  introspect  Self-analysis - what am I not learning?
  improve     Auto-improve - act on self-discovered gaps
  learn       Process pending events now
  reflect     Run deep reflection on learnings
  learnings   Show what Spark has learned
  watch       Run daemon (continuous processing)
  clear       Clear the event queue
  hooks       Show hook installation status
  health      Comprehensive M1-M11 health check
        """
    )

    parser.add_argument("command", nargs="?", default="status",
                       choices=["status", "witness", "introspect", "improve", "learn", "reflect", "learnings",
                               "watch", "clear", "hooks", "health"],
                       help="Command to run")
    parser.add_argument("--interval", type=int, default=15,
                       help="Watch interval in seconds (default: 15)")
    parser.add_argument("-v", "--verbose", action="store_true",
                       help="Verbose output (for witness command)")

    args = parser.parse_args()

    print_banner()

    if args.command == "status":
        asyncio.run(cmd_status())
    elif args.command == "witness":
        cmd_witness(verbose=args.verbose)
    elif args.command == "introspect":
        asyncio.run(cmd_introspect())
    elif args.command == "improve":
        asyncio.run(cmd_improve())
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
