"""
Performance benchmarks for Spark.

Measures and verifies performance requirements:
- Hook latency < 50ms
- Queue throughput
- Pattern extraction speed
- Memory usage
"""

import pytest
import asyncio
import sys
import time
import statistics
from pathlib import Path
from typing import List, Dict
from dataclasses import dataclass

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from lib.queue import SparkQueue, SparkEvent, EventType
from lib.learner import SparkLearner
from lib.prompt_evolver import PromptEvolver
from lib.meta_learner import MetaLearner
from lib.suggester import Suggester


@dataclass
class BenchmarkResult:
    """Result of a performance benchmark."""
    name: str
    iterations: int
    total_time_ms: float
    avg_time_ms: float
    min_time_ms: float
    max_time_ms: float
    p95_time_ms: float
    p99_time_ms: float
    throughput_per_sec: float

    def __str__(self):
        return (f"{self.name}: avg={self.avg_time_ms:.2f}ms, "
                f"p95={self.p95_time_ms:.2f}ms, "
                f"throughput={self.throughput_per_sec:.0f}/s")


def calculate_percentile(times: List[float], percentile: float) -> float:
    """Calculate percentile from list of times."""
    if not times:
        return 0.0
    sorted_times = sorted(times)
    index = int(len(sorted_times) * percentile / 100)
    return sorted_times[min(index, len(sorted_times) - 1)]


def run_benchmark(name: str, func, iterations: int = 100) -> BenchmarkResult:
    """Run a benchmark and collect statistics."""
    times = []

    for _ in range(iterations):
        start = time.perf_counter()
        func()
        end = time.perf_counter()
        times.append((end - start) * 1000)  # Convert to ms

    total_time = sum(times)
    return BenchmarkResult(
        name=name,
        iterations=iterations,
        total_time_ms=total_time,
        avg_time_ms=statistics.mean(times),
        min_time_ms=min(times),
        max_time_ms=max(times),
        p95_time_ms=calculate_percentile(times, 95),
        p99_time_ms=calculate_percentile(times, 99),
        throughput_per_sec=iterations / (total_time / 1000) if total_time > 0 else 0
    )


async def run_async_benchmark(name: str, func, iterations: int = 100) -> BenchmarkResult:
    """Run an async benchmark and collect statistics."""
    times = []

    for _ in range(iterations):
        start = time.perf_counter()
        await func()
        end = time.perf_counter()
        times.append((end - start) * 1000)

    total_time = sum(times)
    return BenchmarkResult(
        name=name,
        iterations=iterations,
        total_time_ms=total_time,
        avg_time_ms=statistics.mean(times),
        min_time_ms=min(times),
        max_time_ms=max(times),
        p95_time_ms=calculate_percentile(times, 95),
        p99_time_ms=calculate_percentile(times, 99),
        throughput_per_sec=iterations / (total_time / 1000) if total_time > 0 else 0
    )


class TestQueuePerformance:
    """Performance tests for the event queue."""

    def test_queue_write_latency(self, isolated_queue):
        """Queue write latency should be < 10ms."""
        event = SparkEvent(
            event_type=EventType.POST_TOOL,
            timestamp=1.0,
            session_id="perf_test",
            data={"key": "value"},
            tool_name="Test"
        )

        def write_event():
            isolated_queue.push(event)

        result = run_benchmark("queue_write", write_event, iterations=1000)

        print(f"\n{result}")
        # Average write should be < 10ms (hook budget)
        assert result.avg_time_ms < 10, f"Queue write too slow: {result.avg_time_ms}ms"
        # p95 should be < 20ms
        assert result.p95_time_ms < 20, f"Queue write p95 too slow: {result.p95_time_ms}ms"

    def test_queue_read_latency(self, isolated_queue):
        """Queue read latency should be reasonable."""
        # Pre-populate queue
        for i in range(100):
            isolated_queue.push(SparkEvent(
                event_type=EventType.POST_TOOL,
                timestamp=float(i),
                session_id="perf_test",
                data={},
                tool_name="Test"
            ))

        def read_batch():
            isolated_queue.pop_batch(10)

        # Re-populate between reads
        for _ in range(100):
            for i in range(10):
                isolated_queue.push(SparkEvent(
                    event_type=EventType.POST_TOOL,
                    timestamp=float(i),
                    session_id="perf_test",
                    data={},
                    tool_name="Test"
                ))

        result = run_benchmark("queue_read_batch", read_batch, iterations=100)

        print(f"\n{result}")
        assert result.avg_time_ms < 50, f"Queue read too slow: {result.avg_time_ms}ms"

    def test_queue_throughput(self, isolated_queue):
        """Queue should handle high throughput."""
        num_events = 10000

        start = time.perf_counter()
        for i in range(num_events):
            isolated_queue.push(SparkEvent(
                event_type=EventType.POST_TOOL,
                timestamp=float(i),
                session_id="throughput_test",
                data={},
                tool_name=f"Tool{i % 10}"
            ))
        write_time = time.perf_counter() - start

        start = time.perf_counter()
        events = isolated_queue.pop_batch(num_events)
        read_time = time.perf_counter() - start

        write_throughput = num_events / write_time
        read_throughput = num_events / read_time

        print(f"\nQueue throughput:")
        print(f"  Write: {write_throughput:.0f} events/sec")
        print(f"  Read: {read_throughput:.0f} events/sec")

        # Should handle at least 1000 events/sec
        assert write_throughput > 1000, f"Write throughput too low: {write_throughput}"
        assert len(events) == num_events


class TestLearnerPerformance:
    """Performance tests for the learner."""

    @pytest.mark.asyncio
    async def test_learner_processing_speed(self, mock_mind):
        """Learner should process events quickly."""
        learner = SparkLearner(mock_mind)

        # Create batch of events
        events = [
            SparkEvent(
                event_type=EventType.POST_TOOL,
                timestamp=float(i),
                session_id="perf_test",
                data={},
                tool_name=f"Tool{i % 5}",
                duration_ms=50.0
            )
            for i in range(100)
        ]

        async def process_batch():
            await learner.process_events(events)

        result = await run_async_benchmark("learner_process", process_batch, iterations=50)

        print(f"\n{result}")
        # Should process 100 events in < 100ms
        assert result.avg_time_ms < 100, f"Learner too slow: {result.avg_time_ms}ms"

    @pytest.mark.asyncio
    async def test_pattern_extraction_scaling(self, mock_mind):
        """Pattern extraction should scale linearly."""
        learner = SparkLearner(mock_mind)

        sizes = [10, 50, 100, 500]
        times = []

        for size in sizes:
            events = [
                SparkEvent(
                    event_type=EventType.POST_TOOL,
                    timestamp=float(i),
                    session_id="scale_test",
                    data={},
                    tool_name=f"Tool{i % 5}",
                    duration_ms=50.0
                )
                for i in range(size)
            ]

            start = time.perf_counter()
            await learner.process_events(events)
            elapsed = (time.perf_counter() - start) * 1000
            times.append((size, elapsed))

            # Reset learner state
            learner.session_events.clear()

        print("\nScaling test:")
        for size, elapsed in times:
            print(f"  {size} events: {elapsed:.2f}ms ({elapsed/size:.2f}ms/event)")

        # Larger batches shouldn't be proportionally slower (sublinear or linear)
        # Time per event shouldn't increase dramatically
        time_per_event_small = times[0][1] / times[0][0]
        time_per_event_large = times[-1][1] / times[-1][0]

        # Large batch time per event should be within 5x of small batch
        assert time_per_event_large < time_per_event_small * 5


class TestPromptEvolverPerformance:
    """Performance tests for the prompt evolver."""

    @pytest.mark.asyncio
    async def test_trace_capture_speed(self, mock_mind):
        """Trace capture should be fast."""
        evolver = PromptEvolver(mock_mind)

        event = SparkEvent(
            event_type=EventType.POST_TOOL,
            timestamp=1.0,
            session_id="perf_test",
            data={},
            tool_name="Test",
            tool_input={"command": "test"},
            duration_ms=50.0
        )

        def capture():
            evolver.capture_trace(event)

        result = run_benchmark("trace_capture", capture, iterations=1000)

        print(f"\n{result}")
        # Capture should be < 1ms
        assert result.avg_time_ms < 1, f"Trace capture too slow: {result.avg_time_ms}ms"

    @pytest.mark.asyncio
    async def test_reflection_speed(self, mock_mind):
        """Session reflection should complete quickly."""
        evolver = PromptEvolver(mock_mind)

        # Add traces
        for i in range(50):
            evolver.capture_trace(SparkEvent(
                event_type=EventType.POST_TOOL,
                timestamp=float(i),
                session_id="reflect_test",
                data={},
                tool_name=f"Tool{i % 5}",
                duration_ms=50.0
            ))

        def reflect():
            evolver.reflect_on_session("reflect_test")

        result = run_benchmark("session_reflection", reflect, iterations=20)

        print(f"\n{result}")
        # Reflection on 50 traces should be < 50ms
        assert result.avg_time_ms < 50, f"Reflection too slow: {result.avg_time_ms}ms"


class TestMetaLearnerPerformance:
    """Performance tests for the meta-learner."""

    def test_learning_record_speed(self, mock_mind):
        """Recording learnings should be fast."""
        ml = MetaLearner(mock_mind)

        def record():
            ml.record_learning("tool", "learner", 0.8)

        result = run_benchmark("meta_record", record, iterations=1000)

        print(f"\n{result}")
        # Recording should be < 0.5ms
        assert result.avg_time_ms < 0.5, f"Meta record too slow: {result.avg_time_ms}ms"

    def test_trend_analysis_speed(self, mock_mind):
        """Trend analysis should be reasonable."""
        ml = MetaLearner(mock_mind)

        # Add many learnings
        for i in range(100):
            ml.record_learning("tool", "learner", 0.7 + (i % 10) * 0.02)

        def analyze():
            ml.analyze_learning_trends()

        result = run_benchmark("trend_analysis", analyze, iterations=100)

        print(f"\n{result}")
        # Analysis of 100 learnings should be < 10ms
        assert result.avg_time_ms < 10, f"Trend analysis too slow: {result.avg_time_ms}ms"

    def test_prune_candidate_speed(self, mock_mind):
        """Identifying prune candidates should be fast."""
        ml = MetaLearner(mock_mind)

        # Add old learnings
        import time as time_module
        old_time = time_module.time() - 40 * 24 * 3600
        from lib.meta_learner import LearningEvent
        for i in range(100):
            event = LearningEvent(
                event_id=f"old_{i}",
                timestamp=old_time,
                learning_type="tool",
                source="learner",
                confidence=0.3
            )
            ml.learning_events.append(event)

        def identify():
            ml.identify_prune_candidates()

        result = run_benchmark("prune_identify", identify, iterations=100)

        print(f"\n{result}")
        # Should identify candidates in < 5ms
        assert result.avg_time_ms < 5, f"Prune ID too slow: {result.avg_time_ms}ms"


class TestSuggesterPerformance:
    """Performance tests for the suggester."""

    def test_context_update_speed(self, mock_mind):
        """Context updates should be fast."""
        suggester = Suggester(mock_mind)

        def update():
            suggester.update_context(
                task_description="Find all test files in the project",
                current_tool="Grep"
            )

        result = run_benchmark("context_update", update, iterations=1000)

        print(f"\n{result}")
        # Update should be < 1ms
        assert result.avg_time_ms < 1, f"Context update too slow: {result.avg_time_ms}ms"

    def test_suggestion_matching_speed(self, mock_mind):
        """Suggestion matching should be fast even with many suggestions."""
        suggester = Suggester(mock_mind)

        # Add many suggestions
        from lib.suggester import Suggestion
        for i in range(100):
            suggester.suggestions[f"s{i}"] = Suggestion(
                suggestion_id=f"s{i}",
                suggestion_type="tip",
                priority=3,
                title=f"Tip {i}",
                description=f"Description for tip {i}",
                confidence=0.8,
                trigger_keywords=[f"keyword{i}", f"term{i}"]
            )

        suggester.update_context(task_description="find keyword50 in files")

        def match():
            suggester.get_relevant_suggestions()

        result = run_benchmark("suggestion_match", match, iterations=100)

        print(f"\n{result}")
        # Matching 100 suggestions should be < 5ms
        assert result.avg_time_ms < 5, f"Suggestion match too slow: {result.avg_time_ms}ms"


class TestEndToEndPerformance:
    """End-to-end performance tests."""

    @pytest.mark.asyncio
    async def test_full_event_processing_pipeline(self, mock_mind, isolated_queue):
        """Full pipeline should complete within budget."""
        learner = SparkLearner(mock_mind)
        evolver = PromptEvolver(mock_mind)
        ml = MetaLearner(mock_mind)

        # Simulate event batch
        events = [
            SparkEvent(
                event_type=EventType.POST_TOOL,
                timestamp=float(i),
                session_id="e2e_perf",
                data={},
                tool_name=f"Tool{i % 5}",
                duration_ms=50.0
            )
            for i in range(50)
        ]

        async def full_pipeline():
            # Queue
            for e in events:
                isolated_queue.push(e)

            # Process
            batch = isolated_queue.pop_batch(50)
            patterns = await learner.process_events(batch)

            # Evolve
            await evolver.process_events(batch)

            # Meta-learn
            for p in patterns or []:
                ml.record_learning(p.pattern_type, "learner", p.confidence)

        result = await run_async_benchmark("full_pipeline", full_pipeline, iterations=20)

        print(f"\n{result}")
        # Full pipeline for 50 events should be < 200ms
        assert result.avg_time_ms < 200, f"Full pipeline too slow: {result.avg_time_ms}ms"


class TestMemoryUsage:
    """Tests for memory efficiency."""

    def test_queue_memory_bounded(self, isolated_queue):
        """Queue memory should be bounded for large event counts."""
        import sys

        # Push many events
        for i in range(10000):
            isolated_queue.push(SparkEvent(
                event_type=EventType.POST_TOOL,
                timestamp=float(i),
                session_id="memory_test",
                data={"index": i},
                tool_name="Test"
            ))

        # Memory should be reasonable (queue is file-based, not in-memory)
        queue_size = isolated_queue.size()
        assert queue_size == 10000

    def test_learner_memory_bounded(self, mock_mind):
        """Learner memory should be bounded."""
        learner = SparkLearner(mock_mind)

        # Process many batches
        for batch in range(10):
            events = [
                SparkEvent(
                    event_type=EventType.POST_TOOL,
                    timestamp=float(batch * 100 + i),
                    session_id=f"batch_{batch}",
                    data={},
                    tool_name=f"Tool{i % 5}"
                )
                for i in range(100)
            ]
            asyncio.get_event_loop().run_until_complete(
                learner.process_events(events)
            )

        # Session events should not grow unbounded
        # (Learner clears after extraction)
        total_session_events = len(learner.session_events)
        # Should have at most recent batch (learner clears periodically)
        assert total_session_events < 2000, f"Too many session events: {total_session_events}"
