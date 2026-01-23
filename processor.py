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
        self.running = False
        self.processed_count = 0
        self.patterns_found = 0

    async def initialize(self):
        """Initialize processor, load existing learnings."""
        log.info("Initializing Spark processor...")

        # Check Mind availability
        if await self.mind.is_available():
            log.info("Connected to Vibeship Mind")
            await self.learner.load_existing_learnings()
            log.info(f"Loaded {len(self.learner.tool_weights)} tool weights")
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

        self.processed_count += len(events)

        # Log tool effectiveness summary
        rankings = self.learner.get_tool_ranking()
        if rankings:
            log.info("Tool effectiveness: " + ", ".join(
                f"{t}:{r:.0%}" for t, r in rankings[:5]
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

        # Store meta-learning about our learning
        meta_content = f"""META-REFLECTION [{datetime.now().isoformat()}]:
Spark has accumulated {len(learnings)} learnings across {len(by_type)} pattern types.
Pattern distribution: {', '.join(f'{k}={len(v)}' for k, v in by_type.items())}.
Total events processed: {self.processed_count}.
Patterns extracted this session: {self.patterns_found}."""

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
            "mind_available": await self.mind.is_available(),
            "tool_weights": dict(self.learner.tool_weights),
            "skill_weights": dict(self.learner.skill_weights),
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
        print(f"   Mind available: {status['mind_available']}")
        if status['tool_weights']:
            print(f"   Tool weights: {status['tool_weights']}")

    # Cleanup
    await processor.mind.close()


if __name__ == "__main__":
    asyncio.run(main())
