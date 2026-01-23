"""
Tests for lib/mind_client.py
"""

import pytest
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
import aiohttp

# Add lib to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.mind_client import (
    MindClient, Memory, ContentType, TemporalLevel,
    store_observation, store_learning, retrieve_learnings
)


class TestContentType:
    """Tests for ContentType enum."""

    def test_content_types_exist(self):
        """All content types are defined."""
        assert ContentType.OBSERVATION == "observation"
        assert ContentType.EVENT == "event"
        assert ContentType.DECISION == "decision"
        assert ContentType.REFLECTION == "reflection"


class TestTemporalLevel:
    """Tests for TemporalLevel enum."""

    def test_temporal_levels_exist(self):
        """All temporal levels are defined."""
        assert TemporalLevel.IMMEDIATE == 1
        assert TemporalLevel.SITUATIONAL == 2
        assert TemporalLevel.SEASONAL == 3
        assert TemporalLevel.IDENTITY == 4


class TestMemory:
    """Tests for Memory dataclass."""

    def test_to_dict_basic(self):
        """Memory converts to dict correctly."""
        memory = Memory(
            content="Test memory",
            temporal_level=TemporalLevel.SITUATIONAL,
            salience=0.8,
            content_type=ContentType.OBSERVATION
        )

        d = memory.to_dict()

        assert d["content"] == "Test memory"
        assert d["temporal_level"] == 2
        assert d["salience"] == 0.8
        assert d["content_type"] == "observation"
        assert "metadata" not in d

    def test_to_dict_with_metadata(self):
        """Memory with metadata converts correctly."""
        memory = Memory(
            content="Test memory",
            temporal_level=TemporalLevel.IDENTITY,
            salience=0.9,
            content_type=ContentType.REFLECTION,
            metadata={"tool": "Bash", "success_rate": 0.9}
        )

        d = memory.to_dict()

        assert d["metadata"]["tool"] == "Bash"
        assert d["metadata"]["success_rate"] == 0.9


class TestMindClient:
    """Tests for MindClient class."""

    def test_init_default(self):
        """Client initializes with defaults."""
        client = MindClient()
        assert client.base_url == "http://localhost:8080"
        assert client._session is None

    def test_init_custom_url(self):
        """Client accepts custom URL."""
        client = MindClient(base_url="http://custom:9000")
        assert client.base_url == "http://custom:9000"

    def test_init_strips_trailing_slash(self):
        """Client strips trailing slash from URL."""
        client = MindClient(base_url="http://localhost:8080/")
        assert client.base_url == "http://localhost:8080"


class AsyncContextManagerMock:
    """Helper for mocking async context managers."""
    def __init__(self, return_value):
        self.return_value = return_value

    async def __aenter__(self):
        return self.return_value

    async def __aexit__(self, *args):
        pass


class TestIsAvailable:
    """Tests for is_available method."""

    @pytest.mark.asyncio
    async def test_returns_true_when_healthy(self):
        """Returns True when Mind health check succeeds."""
        client = MindClient()

        mock_response = MagicMock()
        mock_response.status = 200

        with patch.object(client, '_get_session') as mock_get_session:
            mock_session = MagicMock()
            mock_session.get.return_value = AsyncContextManagerMock(mock_response)
            mock_get_session.return_value = mock_session

            result = await client.is_available()

        assert result is True

    @pytest.mark.asyncio
    async def test_returns_false_when_unhealthy(self):
        """Returns False when Mind health check fails."""
        client = MindClient()

        mock_response = MagicMock()
        mock_response.status = 500

        with patch.object(client, '_get_session') as mock_get_session:
            mock_session = MagicMock()
            mock_session.get.return_value = AsyncContextManagerMock(mock_response)
            mock_get_session.return_value = mock_session

            result = await client.is_available()

        assert result is False

    @pytest.mark.asyncio
    async def test_returns_false_on_connection_error(self):
        """Returns False when connection fails."""
        client = MindClient()

        with patch.object(client, '_get_session') as mock_get_session:
            mock_session = MagicMock()
            mock_session.get.side_effect = aiohttp.ClientError()
            mock_get_session.return_value = mock_session

            result = await client.is_available()

        assert result is False


class TestStore:
    """Tests for store method."""

    @pytest.mark.asyncio
    async def test_store_returns_memory_id(self):
        """Returns memory_id on successful store."""
        client = MindClient()
        memory = Memory(
            content="Test",
            temporal_level=TemporalLevel.SITUATIONAL,
            salience=0.7,
            content_type=ContentType.OBSERVATION
        )

        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"memory_id": "test-123"})

        with patch.object(client, '_get_session') as mock_get_session:
            mock_session = MagicMock()
            mock_session.post.return_value = AsyncContextManagerMock(mock_response)
            mock_get_session.return_value = mock_session

            result = await client.store(memory)

        assert result == "test-123"

    @pytest.mark.asyncio
    async def test_store_returns_none_on_failure(self):
        """Returns None on failed store."""
        client = MindClient()
        memory = Memory(
            content="Test",
            temporal_level=TemporalLevel.SITUATIONAL,
            salience=0.7,
            content_type=ContentType.OBSERVATION
        )

        mock_response = MagicMock()
        mock_response.status = 500

        with patch.object(client, '_get_session') as mock_get_session:
            mock_session = MagicMock()
            mock_session.post.return_value = AsyncContextManagerMock(mock_response)
            mock_get_session.return_value = mock_session

            result = await client.store(memory)

        assert result is None

    @pytest.mark.asyncio
    async def test_store_returns_none_on_exception(self):
        """Returns None on exception (graceful degradation)."""
        client = MindClient()
        memory = Memory(
            content="Test",
            temporal_level=TemporalLevel.SITUATIONAL,
            salience=0.7,
            content_type=ContentType.OBSERVATION
        )

        with patch.object(client, '_get_session') as mock_get_session:
            mock_session = MagicMock()
            mock_session.post.side_effect = Exception("Network error")
            mock_get_session.return_value = mock_session

            result = await client.store(memory)

        assert result is None


class TestStoreBatch:
    """Tests for store_batch method."""

    @pytest.mark.asyncio
    async def test_stores_multiple_memories(self):
        """Stores multiple memories in parallel."""
        client = MindClient()
        memories = [
            Memory(
                content=f"Test {i}",
                temporal_level=TemporalLevel.SITUATIONAL,
                salience=0.7,
                content_type=ContentType.OBSERVATION
            )
            for i in range(3)
        ]

        with patch.object(client, 'store', new_callable=AsyncMock) as mock_store:
            mock_store.return_value = "test-id"

            count = await client.store_batch(memories)

        assert count == 3
        assert mock_store.call_count == 3

    @pytest.mark.asyncio
    async def test_counts_successful_stores(self):
        """Only counts successful stores."""
        client = MindClient()
        memories = [
            Memory(
                content=f"Test {i}",
                temporal_level=TemporalLevel.SITUATIONAL,
                salience=0.7,
                content_type=ContentType.OBSERVATION
            )
            for i in range(3)
        ]

        with patch.object(client, 'store', new_callable=AsyncMock) as mock_store:
            # First succeeds, second fails, third succeeds
            mock_store.side_effect = ["id-1", None, "id-3"]

            count = await client.store_batch(memories)

        assert count == 2


class TestRetrieve:
    """Tests for retrieve method."""

    @pytest.mark.asyncio
    async def test_retrieve_returns_memories(self):
        """Returns list of memories on success."""
        client = MindClient()

        mock_memories = [
            {"memory_id": "1", "content": "Test 1", "temporal_level": 4},
            {"memory_id": "2", "content": "Test 2", "temporal_level": 4}
        ]
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"memories": mock_memories})

        with patch.object(client, '_get_session') as mock_get_session:
            mock_session = MagicMock()
            mock_session.post.return_value = AsyncContextManagerMock(mock_response)
            mock_get_session.return_value = mock_session

            result = await client.retrieve("test query")

        assert len(result) == 2
        assert result[0]["content"] == "Test 1"

    @pytest.mark.asyncio
    async def test_retrieve_filters_by_temporal_level(self):
        """Filters results by temporal_level when specified."""
        client = MindClient()

        mock_memories = [
            {"memory_id": "1", "content": "Test 1", "temporal_level": 2},
            {"memory_id": "2", "content": "Test 2", "temporal_level": 4}
        ]
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"memories": mock_memories})

        with patch.object(client, '_get_session') as mock_get_session:
            mock_session = MagicMock()
            mock_session.post.return_value = AsyncContextManagerMock(mock_response)
            mock_get_session.return_value = mock_session

            result = await client.retrieve(
                "test query",
                temporal_level=TemporalLevel.IDENTITY
            )

        assert len(result) == 1
        assert result[0]["temporal_level"] == 4

    @pytest.mark.asyncio
    async def test_retrieve_filters_by_content_type(self):
        """Filters results by content_type when specified."""
        client = MindClient()

        mock_memories = [
            {"memory_id": "1", "content": "Test 1", "content_type": "observation"},
            {"memory_id": "2", "content": "Test 2", "content_type": "reflection"}
        ]
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"memories": mock_memories})

        with patch.object(client, '_get_session') as mock_get_session:
            mock_session = MagicMock()
            mock_session.post.return_value = AsyncContextManagerMock(mock_response)
            mock_get_session.return_value = mock_session

            result = await client.retrieve(
                "test query",
                content_type=ContentType.REFLECTION
            )

        assert len(result) == 1
        assert result[0]["content_type"] == "reflection"

    @pytest.mark.asyncio
    async def test_retrieve_returns_empty_on_failure(self):
        """Returns empty list on failure (graceful degradation)."""
        client = MindClient()

        mock_response = MagicMock()
        mock_response.status = 500

        with patch.object(client, '_get_session') as mock_get_session:
            mock_session = MagicMock()
            mock_session.post.return_value = AsyncContextManagerMock(mock_response)
            mock_get_session.return_value = mock_session

            result = await client.retrieve("test query")

        assert result == []

    @pytest.mark.asyncio
    async def test_retrieve_returns_empty_on_exception(self):
        """Returns empty list on exception (graceful degradation)."""
        client = MindClient()

        with patch.object(client, '_get_session') as mock_get_session:
            mock_session = MagicMock()
            mock_session.post.side_effect = Exception("Network error")
            mock_get_session.return_value = mock_session

            result = await client.retrieve("test query")

        assert result == []


class TestGetStats:
    """Tests for get_stats method."""

    @pytest.mark.asyncio
    async def test_returns_stats_on_success(self):
        """Returns stats dict on success."""
        client = MindClient()

        mock_stats = {"total_memories": 100, "total_users": 1}
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value=mock_stats)

        with patch.object(client, '_get_session') as mock_get_session:
            mock_session = MagicMock()
            mock_session.get.return_value = AsyncContextManagerMock(mock_response)
            mock_get_session.return_value = mock_session

            result = await client.get_stats()

        assert result["total_memories"] == 100

    @pytest.mark.asyncio
    async def test_returns_empty_on_failure(self):
        """Returns empty dict on failure."""
        client = MindClient()

        with patch.object(client, '_get_session') as mock_get_session:
            mock_session = MagicMock()
            mock_session.get.side_effect = Exception("Error")
            mock_get_session.return_value = mock_session

            result = await client.get_stats()

        assert result == {}


class TestClose:
    """Tests for close method."""

    @pytest.mark.asyncio
    async def test_closes_session(self):
        """Closes the HTTP session."""
        client = MindClient()
        mock_session = AsyncMock()
        mock_session.closed = False
        client._session = mock_session

        await client.close()

        mock_session.close.assert_called_once()


class TestHelperFunctions:
    """Tests for helper functions."""

    @pytest.mark.asyncio
    async def test_store_observation(self):
        """store_observation helper works."""
        with patch('lib.mind_client.MindClient') as MockClient:
            mock_client = AsyncMock()
            mock_client.store.return_value = "test-id"
            mock_client.close = AsyncMock()
            MockClient.return_value = mock_client

            result = await store_observation("Test observation")

            assert result == "test-id"
            mock_client.close.assert_called_once()

    @pytest.mark.asyncio
    async def test_store_learning(self):
        """store_learning helper works."""
        with patch('lib.mind_client.MindClient') as MockClient:
            mock_client = AsyncMock()
            mock_client.store.return_value = "test-id"
            mock_client.close = AsyncMock()
            MockClient.return_value = mock_client

            result = await store_learning("Important insight")

            assert result == "test-id"
            # Verify it used IDENTITY temporal level
            call_args = mock_client.store.call_args
            memory = call_args[0][0]
            assert memory.temporal_level == TemporalLevel.IDENTITY

    @pytest.mark.asyncio
    async def test_retrieve_learnings(self):
        """retrieve_learnings helper works."""
        with patch('lib.mind_client.MindClient') as MockClient:
            mock_client = AsyncMock()
            mock_client.retrieve.return_value = [{"content": "Learning 1"}]
            mock_client.close = AsyncMock()
            MockClient.return_value = mock_client

            result = await retrieve_learnings("test query")

            assert len(result) == 1
            mock_client.close.assert_called_once()
