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
        self.running = False
        self.processed_count = 0
        self.patterns_found = 0
        self.skills_tracked = 0
        self.agents_tracked = 0

    async def initialize(self):
        """Initialize processor, load existing learnings."""
        log.info("Initializing Spark processor...")

        # Check Mind availability
        if await self.mind.is_available():
            log.info("Connected to Vibeship Mind")
            await self.learner.load_existing_learnings()
            await self.skill_evolver.load_existing_data()
            await self.orchestrator.load_existing_data()
            log.info(f"Loaded {len(self.learner.tool_weights)} tool weights, "
                     f"{len(self.skill_evolver.skill_stats)} skill stats, "
                     f"{len(self.orchestrator.agent_stats)} agent stats")
        else:
            log.warning("Mind not available - will retry on next cycle")

    async def process_once(self) -> int:
        """
        Process the current queue once.

        Returns number of events processed.
        """
        # Pop batch from queue
        events = self.queue.pop_batch(max_events=100)

        if not events:
            return 0

        log.info(f"Processing {len(events)} events...")

        # Process events and extract patterns
        patterns = await self.learner.process_events(events)

        if patterns:
            log.info(f"Extracted {len(patterns)} patterns")

            # Store patterns in Mind
            if await self.mind.is_available():
                stored = await self.learner.store_patterns_in_mind(patterns)
                log.info(f"Stored {stored} learnings in Mind")
                self.patterns_found += stored

        # Process skill events
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

        return len(events)

    async def run_daemon(self, interval_seconds: float = 5.0):
        """
        Run as a daemon, processing queue periodically.

        Args:
            interval_seconds: How often to check the queue
        """
        self.running = True
        log.info(f"Daemon started (interval: {interval_seconds}s)")

        while self.running:
            try:
                await self.process_once()
            except Exception as e:
                log.error(f"Processing error: {e}")

            # Wait for next cycle
            await asyncio.sleep(interval_seconds)

        log.info(f"Daemon stopped. Processed {self.processed_count} events, found {self.patterns_found} patterns")

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

        # Store meta-learning about our learning
        skill_summary = f"Skills tracked: {self.skills_tracked}. Gaps: {len(skill_gaps)}. Improvements: {len(skill_improvements)}."
        meta_content = f"""META-REFLECTION [{datetime.now().isoformat()}]:
Spark has accumulated {len(learnings)} learnings across {len(by_type)} pattern types.
Pattern distribution: {', '.join(f'{k}={len(v)}' for k, v in by_type.items())}.
Total events processed: {self.processed_count}.
Patterns extracted this session: {self.patterns_found}.
{skill_summary}"""

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
            "mind_available": await self.mind.is_available(),
            "tool_weights": dict(self.learner.tool_weights),
            "skill_weights": dict(self.learner.skill_weights),
            "skill_stats": {k: v.success_rate for k, v in self.skill_evolver.skill_stats.items()},
            "skill_gaps": len(self.skill_evolver.gaps_identified),
            "skill_improvements": len(self.skill_evolver.improvements_proposed),
            "agent_stats": {k: v.success_rate for k, v in self.orchestrator.agent_stats.items()},
            "parallel_patterns": len(self.orchestrator.parallel_patterns),
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
    args = parser.parse_args()

    processor = SparkProcessor()
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
        print("\n🔥 Spark Status:")
        print(f"   Queue size: {status['queue_size']}")
        print(f"   Processed: {status['processed_count']}")
        print(f"   Patterns found: {status['patterns_found']}")
        print(f"   Skills tracked: {status['skills_tracked']}")
        print(f"   Agents tracked: {status['agents_tracked']}")
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

    # Cleanup
    await processor.mind.close()


if __name__ == "__main__":
    asyncio.run(main())
