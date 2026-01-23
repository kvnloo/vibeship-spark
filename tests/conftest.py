"""
Shared pytest fixtures for Spark tests.
"""

import pytest
import asyncio
import sys
from pathlib import Path

# Add lib to path
sys.path.insert(0, str(Path(__file__).parent.parent))


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def temp_queue_dir(tmp_path):
    """Temporary directory for queue tests."""
    queue_dir = tmp_path / "spark_queue"
    queue_dir.mkdir()
    return queue_dir


@pytest.fixture
def temp_queue(temp_queue_dir):
    """Temporary queue for testing."""
    from lib.queue import SparkQueue
    return SparkQueue(queue_dir=str(temp_queue_dir))


@pytest.fixture
def sample_events():
    """Sample events for testing."""
    from lib.queue import SparkEvent, EventType

    return [
        SparkEvent(
            event_type=EventType.POST_TOOL,
            timestamp=1234567890.0 + i,
            session_id=f"test_session_{i}",
            data={"index": i},
            tool_name="Bash" if i % 2 == 0 else "Edit"
        )
        for i in range(20)
    ]


@pytest.fixture
def sample_success_events():
    """Sample successful tool events."""
    from lib.queue import SparkEvent, EventType

    return [
        SparkEvent(
            event_type=EventType.POST_TOOL,
            timestamp=1234567890.0 + i,
            session_id=f"success_{i}",
            data={},
            tool_name="Bash",
            duration_ms=50.0
        )
        for i in range(10)
    ]


@pytest.fixture
def sample_failure_events():
    """Sample failed tool events."""
    from lib.queue import SparkEvent, EventType

    return [
        SparkEvent(
            event_type=EventType.POST_TOOL_FAILURE,
            timestamp=1234567890.0 + i,
            session_id=f"failure_{i}",
            data={},
            tool_name="Bash",
            error="Command not found"
        )
        for i in range(3)
    ]


@pytest.fixture
def mock_mind_client():
    """Mock Mind client for testing without actual Mind."""
    from unittest.mock import MagicMock, AsyncMock
    from lib.mind_client import MindClient

    mock = MagicMock(spec=MindClient)
    mock.is_available = AsyncMock(return_value=True)
    mock.store = AsyncMock(return_value="mock_memory_id")
    mock.store_batch = AsyncMock(return_value=1)
    mock.retrieve = AsyncMock(return_value=[])
    mock.retrieve_all = AsyncMock(return_value=[])  # Pagination-aware retrieval
    mock.close = AsyncMock()

    return mock
