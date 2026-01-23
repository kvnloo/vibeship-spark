#!/usr/bin/env python3
"""
Spark Background Processor: Where the learning happens.

This runs as a separate background process, NOT in hooks.
It reads from the event queue, extracts patterns, stores learnings.

Can run as:
1. Daemon (always running)
2. One-shot (process queue once)
3. Triggered (by SessionEnd hook)
"""

import asyncio
import argparse
import signal
import sys
import time
import logging
from pathlib import Path
from datetime import datetime

# Add lib to path
sys.path.insert(0, str(Path(__file__).parent))

from lib.queue import SparkQueue, EventType
from lib.mind_client import MindClient, Memory, ContentType, TemporalLevel
from lib.learner import SparkLearner
from lib.skill_evolver import SkillEvolver
from lib.orchestrator import AgentOrchestrator
from lib.prompt_evolver import PromptEvolver
from lib.meta_learner import MetaLearner
from lib.suggester import Suggester
from lib.injection_tracker import InjectionTracker
from lib.experiment_manager import ExperimentManager
from lib.auto_improve import SparkAutoImprove
from lib.reasoning_tracker import ReasoningTracker


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='🔥 Spark | %(asctime)s | %(message)s',
    datefmt='%H:%M:%S'
)
log = logging.getLogger("spark")


class SparkProcessor:
    """
    Background processor for Spark events.

    Reads events from queue, processes them, stores learnings.
    """

    def __init__(self):
        self.queue = SparkQueue()
        self.mind = MindClient()
        self.learner = SparkLearner(self.mind)
        self.skill_evolver = SkillEvolver(self.mind)
        self.orchestrator = AgentOrchestrator(self.mind)
        # M4 Autonomy components
        self.prompt_evolver = PromptEvolver(self.mind)
        self.meta_learner = MetaLearner(self.mind)
        self.suggester = Suggester(self.mind)
        # M5 Feedback Loop components
        self.injection_tracker = InjectionTracker(self.mind)
        self.experiment_manager = ExperimentManager(self.mind)
        # Confidence calibration
        self.reasoning_tracker = ReasoningTracker(self.mind)
        self.running = False
        self.processed_count = 0
        self.patterns_found = 0
        self.skills_tracked = 0
        self.agents_tracked = 0
        self.traces_captured = 0
        self.injections_tracked = 0
        self.experiments_concluded = 0
        # Self-improvement tracking
        self.daemon_cycles = 0
        self.introspection_interval = 10  # Run introspection every N cycles
        self.last_improvement_count = 0

    async def initialize(self):
        """Initialize processor, load existing learnings."""
        log.info("Initializing Spark processor...")

        # Check Mind availability
        if await self.mind.is_available():
            log.info("Connected to Vibeship Mind")
            await self.learner.load_existing_learnings()
            await self.skill_evolver.load_existing_data()
            await self.orchestrator.load_existing_data()
            # M4 components
            await self.prompt_evolver.load_existing_data()
            await self.meta_learner.load_existing_data()
            await self.suggester.load_suggestions_from_mind()
            # Load calibration data
            calibration_loaded = await self.reasoning_tracker.load_calibration_from_mind()
            log.info(f"Loaded {len(self.learner.tool_weights)} tool weights, "
                     f"{len(self.skill_evolver.skill_stats)} skill stats, "
                     f"{len(self.orchestrator.agent_stats)} agent stats, "
                     f"{len(self.prompt_evolver.patterns)} prompt patterns, "
                     f"{len(self.suggester.suggestions)} suggestions, "
                     f"{calibration_loaded} calibration factors")
        else:
            log.warning("Mind not available - will retry on next cycle")

    async def process_once(self) -> int:
        """
        Process the current queue once.

        Returns number of events processed.
        """
        # Pop batch from queue
        events = self.queue.pop_batch(max_events=100)

        # Process events if any
        patterns = []
        if events:
            log.info(f"Processing {len(events)} events...")
            # Process events and extract patterns
            patterns = await self.learner.process_events(events)

        # Also extract goal patterns from file (independent of events)
        goal_patterns = self.learner._extract_goal_patterns()
        if goal_patterns:
            patterns.extend(goal_patterns)
            log.info(f"Extracted {len(goal_patterns)} goal patterns")

        if patterns:
            log.info(f"Total {len(patterns)} patterns")

            # Store patterns in Mind
            if await self.mind.is_available():
                stored = await self.learner.store_patterns_in_mind(patterns)
                log.info(f"Stored {stored} learnings in Mind")
                self.patterns_found += stored

        if not events and not patterns:
            return 0

        # Process skill events (only if we have events)
        if not events:
            return len(patterns)  # Return pattern count if no events

        skill_usages = await self.skill_evolver.process_events(events)
        if skill_usages:
            self.skills_tracked += len(skill_usages)
            log.info(f"Tracked {len(skill_usages)} skill usages")

            # Identify gaps and propose improvements periodically
            if self.skills_tracked >= 10:
                gaps = self.skill_evolver.identify_gaps()
                if gaps:
                    log.info(f"Identified {len(gaps)} skill gaps")

                improvements = self.skill_evolver.propose_improvements()
                if improvements:
                    log.info(f"Proposed {len(improvements)} skill improvements")

                # Store skill learnings
                if await self.mind.is_available():
                    stored = await self.skill_evolver.store_learnings_in_mind()
                    if stored:
                        log.info(f"Stored {stored} skill learnings")

        self.processed_count += len(events)

        # Log tool effectiveness summary
        rankings = self.learner.get_tool_ranking()
        if rankings:
            log.info("Tool effectiveness: " + ", ".join(
                f"{t}:{r:.0%}" for t, r in rankings[:5]
            ))

        # Log skill effectiveness if available
        skill_rankings = self.skill_evolver.get_skill_ranking()
        if skill_rankings:
            log.info("Skill effectiveness: " + ", ".join(
                f"{s}:{r:.0%}" for s, r, _ in skill_rankings[:3]
            ))

        # Process agent events
        agent_usages = await self.orchestrator.process_events(events)
        if agent_usages:
            self.agents_tracked += len(agent_usages)
            log.info(f"Tracked {len(agent_usages)} agent usages")

            # Identify parallel patterns periodically
            if self.agents_tracked >= 10:
                parallel_patterns = self.orchestrator.identify_parallel_patterns()
                if parallel_patterns:
                    log.info(f"Identified {len(parallel_patterns)} parallel patterns")

                # Store agent learnings
                if await self.mind.is_available():
                    stored = await self.orchestrator.store_learnings_in_mind()
                    if stored:
                        log.info(f"Stored {stored} agent learnings")

        # Log agent effectiveness if available
        agent_rankings = self.orchestrator.get_agent_ranking()
        if agent_rankings:
            log.info("Agent effectiveness: " + ", ".join(
                f"{a}:{r:.0%}" for a, r, _ in agent_rankings[:3]
            ))

        # M4: Capture execution traces for prompt evolution
        traces = await self.prompt_evolver.process_events(events)
        if traces:
            self.traces_captured += len(traces)

            # Feed learnings to meta-learner
            for pattern in patterns or []:
                self.meta_learner.record_learning(
                    learning_type=pattern.pattern_type,
                    source="learner",
                    confidence=pattern.confidence
                )

            # Periodically reflect and evolve
            if self.traces_captured >= 20:
                # Get unique sessions
                sessions = set(t.session_id for t in traces)
                for session_id in sessions:
                    reflection = self.prompt_evolver.reflect_on_session(session_id)
                    if reflection.insights:
                        log.info(f"Prompt insights: {reflection.insights[:2]}")

                # Store prompt evolution learnings
                if await self.mind.is_available():
                    stored = await self.prompt_evolver.store_learnings_in_mind()
                    if stored:
                        log.info(f"Stored {stored} prompt patterns")

        # M4: Generate meta-insights periodically
        if self.processed_count > 0 and self.processed_count % 50 == 0:
            meta_insights = self.meta_learner.generate_meta_insights()
            if meta_insights:
                actionable = [i for i in meta_insights if i.actionable]
                if actionable:
                    log.info(f"Meta-insights: {[i.description for i in actionable[:2]]}")

                # Store meta-learnings
                if await self.mind.is_available():
                    await self.meta_learner.store_meta_learnings()

        # M5: Track injection outcomes
        for event in events:
            result = self.injection_tracker.observe_event(event)
            if result:
                self.injections_tracked += 1
                # Update learning confidence based on outcome
                await self.injection_tracker.update_learning_confidence(result)

        # M5: Expire stale injections
        expired = self.injection_tracker.expire_stale_injections()
        if expired:
            log.info(f"Expired {expired} stale injections")

        # M5: Check experiments for auto-conclusion
        for exp in self.experiment_manager.get_active_experiments():
            result = self.experiment_manager.auto_conclude_if_significant(exp.experiment_id)
            if result:
                self.experiments_concluded += 1
                log.info(f"Experiment '{exp.name}' concluded: {result.recommended_winner} wins "
                         f"({result.treatment_success_rate:.1%} vs {result.control_success_rate:.1%})")
                if await self.mind.is_available():
                    await self.experiment_manager.persist_experiment(exp.experiment_id)

        # M5: Log feedback loop stats periodically
        if self.processed_count > 0 and self.processed_count % 100 == 0:
            feedback_stats = self.injection_tracker.get_stats()
            if feedback_stats.total_injections > 0:
                log.info(f"Feedback loop: {feedback_stats.follow_rate:.0%} follow rate "
                         f"({feedback_stats.followed_count}/{feedback_stats.total_injections})")

        return len(events)

    async def run_introspection_cycle(self):
        """
        Run the self-improvement cycle: introspect -> improve.

        This is the recursive loop that makes Spark truly self-evolving.
        """
        log.info("=== SELF-IMPROVEMENT CYCLE ===")

        try:
            improver = SparkAutoImprove(self.mind)
            report = await improver.improve()

            if report.gaps_found > 0:
                log.info(f"Introspection found {report.gaps_found} gaps")
                log.info(f"Auto-improve took {len(report.actions_taken)} actions")
                log.info(f"Improvements made: {report.improvements_made}")

                # Log specific actions
                for action in report.actions_taken:
                    status = "OK" if action.success else "FAIL"
                    log.info(f"  [{status}] {action.gap_type}: {action.action_taken[:50]}")

                self.last_improvement_count = report.improvements_made
            else:
                log.info("No gaps found - system is healthy")
                self.last_improvement_count = 0

            # Save confidence calibration
            self.reasoning_tracker.update_calibration_factors()
            if self.reasoning_tracker.calibration_factors:
                saved = await self.reasoning_tracker.save_calibration_to_mind()
                if saved:
                    log.info(f"Calibration saved: {len(self.reasoning_tracker.calibration_factors)} tools")
                    log.info(self.reasoning_tracker.get_calibration_summary())

        except Exception as e:
            log.error(f"Self-improvement error: {e}")

        log.info("=== END SELF-IMPROVEMENT ===")

    async def run_daemon(self, interval_seconds: float = 5.0):
        """
        Run as a daemon, processing queue periodically.

        Args:
            interval_seconds: How often to check the queue
        """
        self.running = True
        log.info(f"Daemon started (interval: {interval_seconds}s, introspection every {self.introspection_interval} cycles)")

        while self.running:
            try:
                await self.process_once()
                self.daemon_cycles += 1

                # Periodic self-improvement
                if self.daemon_cycles % self.introspection_interval == 0:
                    await self.run_introspection_cycle()

            except Exception as e:
                log.error(f"Processing error: {e}")

            # Wait for next cycle
            await asyncio.sleep(interval_seconds)

        log.info(f"Daemon stopped. Processed {self.processed_count} events, found {self.patterns_found} patterns, "
                 f"ran {self.daemon_cycles // self.introspection_interval} introspection cycles")

    def stop(self):
        """Stop the daemon."""
        self.running = False

    async def run_reflection(self):
        """
        Run a deep reflection session.

        This is called periodically (e.g., daily) to:
        - Analyze all patterns
        - Consolidate learnings
        - Prune outdated patterns
        - Update behavior weights
        """
        log.info("Starting reflection session...")

        # Get all learnings from Mind
        if not await self.mind.is_available():
            log.warning("Mind not available for reflection")
            return

        # Retrieve recent learnings
        learnings = await self.mind.retrieve(
            query="LEARNING",
            limit=100,
            temporal_level=TemporalLevel.IDENTITY
        )

        log.info(f"Analyzing {len(learnings)} existing learnings...")

        # Group by pattern type
        by_type = {}
        for learning in learnings:
            metadata = learning.get("metadata", {})
            pattern_type = metadata.get("pattern_type", "unknown")
            if pattern_type not in by_type:
                by_type[pattern_type] = []
            by_type[pattern_type].append(learning)

        # Log summary
        for pattern_type, patterns in by_type.items():
            log.info(f"  {pattern_type}: {len(patterns)} patterns")

        # Skill evolution analysis
        skill_gaps = self.skill_evolver.identify_gaps()
        skill_improvements = self.skill_evolver.propose_improvements()

        if skill_gaps:
            log.info(f"Skill gaps identified: {len(skill_gaps)}")
            for gap in skill_gaps[:3]:
                log.info(f"  - {gap.task_type}: {gap.current_success_rate:.0%} success, potential +{gap.improvement_potential:.0%}")

        if skill_improvements:
            log.info(f"Skill improvements proposed: {len(skill_improvements)}")
            for imp in skill_improvements[:3]:
                log.info(f"  - {imp.skill_id}: {imp.improvement_type} (priority {imp.priority})")

        # M4: Prompt evolution analysis
        evolution_stats = self.prompt_evolver.get_evolution_stats()
        frontier_patterns = self.prompt_evolver.get_frontier_patterns()
        if frontier_patterns:
            log.info(f"Prompt patterns on Pareto frontier: {len(frontier_patterns)}")
            for p in frontier_patterns[:3]:
                log.info(f"  - {p.description}: {p.success_rate:.0%} ({p.total_uses} uses)")

        # M4: Meta-learning analysis
        meta_stats = self.meta_learner.get_meta_stats()
        meta_insights = self.meta_learner.generate_meta_insights()
        prune_candidates = self.meta_learner.identify_prune_candidates()

        if prune_candidates:
            log.info(f"Prune candidates identified: {len(prune_candidates)}")
            # Actually prune old learnings
            pruned = self.meta_learner.prune_learnings(prune_candidates[:10])
            log.info(f"Pruned {pruned} outdated learnings")

        if meta_insights:
            log.info(f"Meta-insights generated: {len(meta_insights)}")
            for insight in meta_insights[:3]:
                log.info(f"  - [{insight.insight_type}] {insight.description}")

        # Store meta-learning about our learning
        skill_summary = f"Skills tracked: {self.skills_tracked}. Gaps: {len(skill_gaps)}. Improvements: {len(skill_improvements)}."
        m4_summary = f"Traces: {self.traces_captured}. Patterns: {len(self.prompt_evolver.patterns)}. Meta-insights: {len(meta_insights)}."
        meta_content = f"""META-REFLECTION [{datetime.now().isoformat()}]:
Spark has accumulated {len(learnings)} learnings across {len(by_type)} pattern types.
Pattern distribution: {', '.join(f'{k}={len(v)}' for k, v in by_type.items())}.
Total events processed: {self.processed_count}.
Patterns extracted this session: {self.patterns_found}.
{skill_summary}
{m4_summary}"""

        await self.mind.store(Memory(
            content=meta_content,
            temporal_level=TemporalLevel.IDENTITY,
            salience=1.0,
            content_type=ContentType.REFLECTION,
            metadata={
                "type": "meta_reflection",
                "learning_count": len(learnings),
                "pattern_types": list(by_type.keys()),
                "processed_count": self.processed_count
            }
        ))

        log.info("Reflection complete")

    async def get_status(self) -> dict:
        """Get processor status."""
        return {
            "queue_size": self.queue.size(),
            "processed_count": self.processed_count,
            "patterns_found": self.patterns_found,
            "skills_tracked": self.skills_tracked,
            "agents_tracked": self.agents_tracked,
            "traces_captured": self.traces_captured,
            "mind_available": await self.mind.is_available(),
            "tool_weights": dict(self.learner.tool_weights),
            "skill_weights": dict(self.learner.skill_weights),
            "skill_stats": {k: v.success_rate for k, v in self.skill_evolver.skill_stats.items()},
            "skill_gaps": len(self.skill_evolver.gaps_identified),
            "skill_improvements": len(self.skill_evolver.improvements_proposed),
            "agent_stats": {k: v.success_rate for k, v in self.orchestrator.agent_stats.items()},
            "parallel_patterns": len(self.orchestrator.parallel_patterns),
            # M4 status
            "prompt_patterns": len(self.prompt_evolver.patterns),
            "pareto_frontier": len(self.prompt_evolver.pareto_frontier),
            "meta_learnings": self.meta_learner.total_learnings,
            "suggestions_loaded": len(self.suggester.suggestions),
            # M5 status
            "injections_tracked": self.injections_tracked,
            "injection_follow_rate": self.injection_tracker.get_stats().follow_rate,
            "active_experiments": len(self.experiment_manager.get_active_experiments()),
            "experiments_concluded": self.experiments_concluded,
            # Self-improvement status
            "daemon_cycles": self.daemon_cycles,
            "introspection_interval": self.introspection_interval,
            "last_improvement_count": self.last_improvement_count,
        }


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Spark Background Processor")
    parser.add_argument(
        "--mode",
        choices=["daemon", "once", "reflect", "status"],
        default="once",
        help="Run mode: daemon (continuous), once (process queue), reflect (deep analysis), status (show status)"
    )
    parser.add_argument(
        "--interval",
        type=float,
        default=5.0,
        help="Daemon interval in seconds"
    )
    parser.add_argument(
        "--introspect-every",
        type=int,
        default=10,
        help="Run self-improvement every N daemon cycles"
    )
    args = parser.parse_args()

    processor = SparkProcessor()
    processor.introspection_interval = args.introspect_every
    await processor.initialize()

    if args.mode == "daemon":
        # Handle graceful shutdown
        def handle_signal(sig, frame):
            log.info("Received shutdown signal")
            processor.stop()

        signal.signal(signal.SIGINT, handle_signal)
        signal.signal(signal.SIGTERM, handle_signal)

        await processor.run_daemon(args.interval)

    elif args.mode == "once":
        processed = await processor.process_once()
        log.info(f"Processed {processed} events")

    elif args.mode == "reflect":
        await processor.run_reflection()

    elif args.mode == "status":
        status = await processor.get_status()
        print("\n[Spark] Status:")
        print(f"   Queue size: {status['queue_size']}")
        print(f"   Processed: {status['processed_count']}")
        print(f"   Patterns found: {status['patterns_found']}")
        print(f"   Skills tracked: {status['skills_tracked']}")
        print(f"   Agents tracked: {status['agents_tracked']}")
        print(f"   Traces captured: {status['traces_captured']}")
        print(f"   Mind available: {status['mind_available']}")
        if status['tool_weights']:
            print(f"   Tool weights: {status['tool_weights']}")
        if status['skill_stats']:
            print(f"   Skill effectiveness: {status['skill_stats']}")
        if status['skill_gaps']:
            print(f"   Skill gaps identified: {status['skill_gaps']}")
        if status['skill_improvements']:
            print(f"   Improvements proposed: {status['skill_improvements']}")
        if status['agent_stats']:
            print(f"   Agent effectiveness: {status['agent_stats']}")
        if status['parallel_patterns']:
            print(f"   Parallel patterns: {status['parallel_patterns']}")
        # M4 status
        print(f"   Prompt patterns: {status['prompt_patterns']}")
        print(f"   Pareto frontier: {status['pareto_frontier']}")
        print(f"   Meta-learnings: {status['meta_learnings']}")
        print(f"   Suggestions: {status['suggestions_loaded']}")
        # M5 status
        print(f"   Injections tracked: {status['injections_tracked']}")
        print(f"   Follow rate: {status['injection_follow_rate']:.0%}")
        print(f"   Active experiments: {status['active_experiments']}")
        print(f"   Experiments concluded: {status['experiments_concluded']}")
        # Self-improvement status
        print(f"   Daemon cycles: {status['daemon_cycles']}")
        print(f"   Introspection every: {status['introspection_interval']} cycles")
        print(f"   Last improvements: {status['last_improvement_count']}")

    # Cleanup
    await processor.mind.close()


if __name__ == "__main__":
    asyncio.run(main())
