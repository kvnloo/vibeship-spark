"""
Shared fixtures for integration tests.
"""

import pytest
import asyncio
import sys
import tempfile
import shutil
from pathlib import Path
from typing import List, Optional
from dataclasses import dataclass, field
from unittest.mock import AsyncMock, MagicMock

# Add lib to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from lib.queue import SparkQueue, SparkEvent, EventType
from lib.mind_client import MindClient, Memory, TemporalLevel, ContentType
from lib.learner import SparkLearner
from lib.context_injector import ContextInjector
from lib.prompt_evolver import PromptEvolver
from lib.meta_learner import MetaLearner
from lib.suggester import Suggester


@dataclass
class SessionScenario:
    """Defines a test scenario for session simulation."""
    name: str
    description: str
    events: List[SparkEvent] = field(default_factory=list)
    expected_patterns: List[str] = field(default_factory=list)
    expected_min_learnings: int = 0
    should_inject_context: bool = False


@dataclass
class SessionResult:
    """Result of a simulated session."""
    scenario_name: str
    events_processed: int
    patterns_extracted: int
    learnings_stored: int
    injection_content: Optional[str]
    errors: List[str] = field(default_factory=list)
    duration_ms: float = 0.0


class MockMindClient:
    """Mock Mind client for isolated testing."""

    def __init__(self):
        self.memories = {}
        self.available = True
        self.store_calls = []
        self.retrieve_calls = []

    async def is_available(self) -> bool:
        return self.available

    async def store(self, memory: Memory) -> Optional[str]:
        if not self.available:
            return None
        memory_id = f"mock_{len(self.memories)}"
        self.memories[memory_id] = {
            "memory_id": memory_id,
            "content": memory.content,
            "temporal_level": memory.temporal_level.value if hasattr(memory.temporal_level, 'value') else memory.temporal_level,
            "salience": memory.salience,
            "metadata": memory.metadata
        }
        self.store_calls.append(memory)
        return memory_id

    async def store_batch(self, memories: List[Memory]) -> int:
        """Store multiple memories at once."""
        if not self.available:
            return 0
        stored = 0
        for memory in memories:
            result = await self.store(memory)
            if result:
                stored += 1
        return stored

    async def retrieve(self, query: str, limit: int = 10, **kwargs) -> List[dict]:
        if not self.available:
            return []
        self.retrieve_calls.append({"query": query, "limit": limit})
        # Return memories that contain the query
        results = []
        for mem in self.memories.values():
            if query.lower() in mem["content"].lower():
                results.append(mem)
                if len(results) >= limit:
                    break
        return results

    async def retrieve_all(self, query: str, max_results: int = 1000, **kwargs) -> List[dict]:
        """Pagination-aware retrieval (same as retrieve for mock)."""
        return await self.retrieve(query, limit=max_results, **kwargs)

    async def close(self):
        pass

    def set_unavailable(self):
        self.available = False

    def set_available(self):
        self.available = True

    def clear(self):
        self.memories = {}
        self.store_calls = []
        self.retrieve_calls = []


@pytest.fixture
def mock_mind():
    """Provide a mock Mind client."""
    return MockMindClient()


@pytest.fixture
def temp_queue_dir():
    """Provide a temporary directory for queue storage."""
    temp_dir = tempfile.mkdtemp(prefix="spark_test_")
    yield temp_dir
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def isolated_queue(temp_queue_dir):
    """Provide an isolated queue instance."""
    return SparkQueue(queue_dir=temp_queue_dir)


@pytest.fixture
def sample_events():
    """Generate sample events for testing."""
    return [
        SparkEvent(
            event_type=EventType.POST_TOOL,
            timestamp=1000.0,
            session_id="test_session_1",
            data={},
            tool_name="Grep",
            tool_input={"pattern": "def test"},
            duration_ms=50.0
        ),
        SparkEvent(
            event_type=EventType.POST_TOOL,
            timestamp=1001.0,
            session_id="test_session_1",
            data={},
            tool_name="Read",
            tool_input={"file_path": "/test/file.py"},
            duration_ms=30.0
        ),
        SparkEvent(
            event_type=EventType.POST_TOOL,
            timestamp=1002.0,
            session_id="test_session_1",
            data={},
            tool_name="Edit",
            tool_input={"file_path": "/test/file.py"},
            duration_ms=40.0
        ),
    ]


@pytest.fixture
def search_scenario():
    """Scenario: User searching for code."""
    events = []
    for i in range(15):  # Need enough for confidence threshold
        events.append(SparkEvent(
            event_type=EventType.POST_TOOL,
            timestamp=1000.0 + i,
            session_id="search_session",
            data={},
            tool_name="Grep",
            tool_input={"pattern": f"search_{i}"},
            duration_ms=50.0 + i
        ))
    return SessionScenario(
        name="search_code",
        description="User searching through codebase",
        events=events,
        expected_patterns=["tool_effectiveness"],
        expected_min_learnings=0  # May not reach confidence threshold
    )


@pytest.fixture
def edit_scenario():
    """Scenario: User editing files."""
    events = []
    for i in range(15):
        events.append(SparkEvent(
            event_type=EventType.POST_TOOL,
            timestamp=2000.0 + i,
            session_id="edit_session",
            data={},
            tool_name="Edit",
            tool_input={"file_path": f"/test/file_{i}.py"},
            duration_ms=40.0
        ))
    return SessionScenario(
        name="edit_files",
        description="User editing multiple files",
        events=events,
        expected_patterns=["tool_effectiveness"],
        expected_min_learnings=0
    )


@pytest.fixture
def error_scenario():
    """Scenario: User encountering errors."""
    events = []
    for i in range(10):
        events.append(SparkEvent(
            event_type=EventType.POST_TOOL_FAILURE,
            timestamp=3000.0 + i,
            session_id="error_session",
            data={},
            tool_name="Bash",
            tool_input={"command": f"failing_command_{i}"},
            error="Command not found"
        ))
    return SessionScenario(
        name="error_recovery",
        description="User encountering repeated errors",
        events=events,
        expected_patterns=["error_avoidance"],
        expected_min_learnings=0
    )


@pytest.fixture
def mixed_scenario(search_scenario, edit_scenario):
    """Scenario: Mixed tool usage."""
    events = search_scenario.events[:5] + edit_scenario.events[:5]
    return SessionScenario(
        name="mixed_usage",
        description="Mixed search and edit operations",
        events=events,
        expected_patterns=["tool_effectiveness"],
        expected_min_learnings=0
    )


class SessionSimulator:
    """Simulates a full Spark session for testing."""

    def __init__(self, mind_client: MockMindClient, queue: SparkQueue):
        self.mind = mind_client
        self.queue = queue
        self.learner = SparkLearner(mind_client)
        self.evolver = PromptEvolver(mind_client)
        self.meta_learner = MetaLearner(mind_client)
        self.suggester = Suggester(mind_client)
        self.injector = ContextInjector(mind_client)

    async def simulate_session(self, scenario: SessionScenario) -> SessionResult:
        """Run a complete session simulation."""
        import time
        start_time = time.time()
        errors = []

        # 1. Push events to queue
        for event in scenario.events:
            self.queue.push(event)

        # 2. Process events through learner
        events = self.queue.pop_batch(len(scenario.events))
        patterns = await self.learner.process_events(events)

        # 3. Store patterns if confident enough
        stored = 0
        if patterns and await self.mind.is_available():
            stored = await self.learner.store_patterns_in_mind(patterns)

        # 4. Process through prompt evolver
        traces = await self.evolver.process_events(scenario.events)

        # 5. Feed to meta-learner
        for pattern in patterns or []:
            self.meta_learner.record_learning(
                learning_type=pattern.pattern_type,
                source="learner",
                confidence=pattern.confidence
            )

        # 6. Get injection content
        injection = None
        if scenario.should_inject_context:
            injection = await self.injector.get_injection_string("test_project")

        duration = (time.time() - start_time) * 1000

        return SessionResult(
            scenario_name=scenario.name,
            events_processed=len(events),
            patterns_extracted=len(patterns) if patterns else 0,
            learnings_stored=stored,
            injection_content=injection,
            errors=errors,
            duration_ms=duration
        )

    async def close(self):
        await self.injector.close()


@pytest.fixture
def simulator(mock_mind, isolated_queue):
    """Provide a session simulator."""
    sim = SessionSimulator(mock_mind, isolated_queue)
    yield sim
    asyncio.get_event_loop().run_until_complete(sim.close())
