"""
Spark Mind Client: Async integration with Vibeship Mind.

All Mind operations are async and non-blocking.
Used by the background processor, NEVER by hooks directly.
"""

import asyncio
import aiohttp
import json
from typing import Any, Dict, List, Optional
from dataclasses import dataclass
from enum import Enum


class ContentType(str, Enum):
    """Memory content types."""
    OBSERVATION = "observation"
    EVENT = "event"
    DECISION = "decision"
    REFLECTION = "reflection"


class TemporalLevel(int, Enum):
    """Memory temporal levels."""
    IMMEDIATE = 1    # Current context, expires quickly
    SITUATIONAL = 2  # Current task/session
    SEASONAL = 3     # Project-level, important events
    IDENTITY = 4     # Core knowledge, permanent


@dataclass
class Memory:
    """A memory to store in Mind."""
    content: str
    temporal_level: TemporalLevel
    salience: float  # 0.0 to 1.0
    content_type: ContentType
    metadata: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        result = {
            "content": self.content,
            "temporal_level": self.temporal_level.value,
            "salience": self.salience,
            "content_type": self.content_type.value,
        }
        if self.metadata:
            result["metadata"] = self.metadata
        return result


class MindClient:
    """
    Async client for Vibeship Mind API.

    Design:
    - All operations are async
    - Connection pooling via aiohttp
    - Graceful degradation if Mind is unavailable
    - Never blocks, never crashes
    """

    def __init__(
        self,
        base_url: str = "http://localhost:8080",
        timeout: float = 5.0
    ):
        self.base_url = base_url.rstrip('/')
        self.timeout = aiohttp.ClientTimeout(total=timeout)
        self._session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create HTTP session."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(timeout=self.timeout)
        return self._session

    async def close(self):
        """Close the HTTP session."""
        if self._session and not self._session.closed:
            await self._session.close()

    async def is_available(self) -> bool:
        """Check if Mind is running."""
        try:
            session = await self._get_session()
            async with session.get(f"{self.base_url}/health") as resp:
                return resp.status == 200
        except Exception:
            return False

    async def store(self, memory: Memory) -> Optional[str]:
        """
        Store a memory in Mind.

        Returns memory_id on success, None on failure.
        Never raises exceptions - graceful degradation.
        """
        try:
            session = await self._get_session()
            async with session.post(
                f"{self.base_url}/v1/memories/",
                json=memory.to_dict()
            ) as resp:
                if resp.status in (200, 201):  # Accept both OK and Created
                    data = await resp.json()
                    return data.get("memory_id")
                return None
        except Exception:
            return None

    async def store_batch(self, memories: List[Memory]) -> int:
        """
        Store multiple memories.

        Returns count of successfully stored memories.
        """
        tasks = [self.store(m) for m in memories]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        return sum(1 for r in results if r is not None and not isinstance(r, Exception))

    async def retrieve(
        self,
        query: str,
        limit: int = 10,
        temporal_level: Optional[TemporalLevel] = None,
        content_type: Optional[ContentType] = None
    ) -> List[Dict[str, Any]]:
        """
        Retrieve memories matching a query.

        Returns list of matching memories, empty list on failure.
        """
        try:
            session = await self._get_session()
            payload = {"query": query, "limit": limit}

            async with session.post(
                f"{self.base_url}/v1/memories/retrieve",
                json=payload
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    memories = data.get("memories", [])

                    # Filter by temporal_level if specified
                    if temporal_level:
                        memories = [
                            m for m in memories
                            if m.get("temporal_level") == temporal_level.value
                        ]

                    # Filter by content_type if specified
                    if content_type:
                        memories = [
                            m for m in memories
                            if m.get("content_type") == content_type.value
                        ]

                    return memories
                return []
        except Exception:
            return []

    async def retrieve_all(
        self,
        query: str,
        max_results: int = 1000,
        batch_size: int = 100,
        temporal_level: Optional[TemporalLevel] = None,
        content_type: Optional[ContentType] = None
    ) -> List[Dict[str, Any]]:
        """
        Retrieve ALL memories matching a query using pagination.

        Mind Lite has a hard cap of 100 results per query.
        This method uses multiple queries to get all matching memories.

        Uses memory_id tracking to avoid duplicates across batches.

        Args:
            query: Search query
            max_results: Maximum total results to return
            batch_size: Results per batch (max 100 for Mind Lite)
            temporal_level: Optional filter
            content_type: Optional filter

        Returns:
            List of all matching memories up to max_results
        """
        all_results = []
        seen_ids = set()
        batch_size = min(batch_size, 100)  # Mind Lite caps at 100

        # First batch
        batch = await self.retrieve(
            query=query,
            limit=batch_size,
            temporal_level=temporal_level,
            content_type=content_type
        )

        if not batch:
            return all_results

        # Add first batch, tracking IDs
        for memory in batch:
            memory_id = memory.get("memory_id")
            if memory_id and memory_id not in seen_ids:
                seen_ids.add(memory_id)
                all_results.append(memory)

        # If we got less than batch_size, there are no more results
        if len(batch) < batch_size:
            return all_results[:max_results]

        # For additional batches, we need to use offset-based approach
        # Mind Lite supports list endpoint with offset
        offset = batch_size
        while len(all_results) < max_results:
            try:
                session = await self._get_session()
                # Use the list endpoint with offset for pagination
                async with session.get(
                    f"{self.base_url}/v1/memories/",
                    params={"limit": batch_size, "offset": offset}
                ) as resp:
                    if resp.status != 200:
                        break
                    data = await resp.json()

                    # Handle both list and dict response formats
                    if isinstance(data, list):
                        batch = data
                    else:
                        batch = data.get("memories", data.get("items", []))

                    if not batch:
                        break

                    # Filter by query content (since list endpoint doesn't filter)
                    query_lower = query.lower()
                    for memory in batch:
                        memory_id = memory.get("memory_id")
                        content = memory.get("content", "").lower()

                        # Check if matches query and not seen
                        if memory_id and memory_id not in seen_ids:
                            if query_lower in content:
                                seen_ids.add(memory_id)
                                all_results.append(memory)

                                if len(all_results) >= max_results:
                                    break

                    offset += batch_size

                    # If batch is smaller than requested, no more results
                    if len(batch) < batch_size:
                        break

            except Exception:
                break

        return all_results[:max_results]

    async def get_stats(self) -> Dict[str, Any]:
        """Get Mind statistics."""
        try:
            session = await self._get_session()
            async with session.get(f"{self.base_url}/v1/stats") as resp:
                if resp.status == 200:
                    return await resp.json()
                return {}
        except Exception:
            return {}


# Helper functions for common operations

async def store_observation(content: str, salience: float = 0.7, metadata: Optional[Dict] = None) -> Optional[str]:
    """Quick helper to store an observation."""
    client = MindClient()
    try:
        return await client.store(Memory(
            content=content,
            temporal_level=TemporalLevel.SITUATIONAL,
            salience=salience,
            content_type=ContentType.OBSERVATION,
            metadata=metadata
        ))
    finally:
        await client.close()


async def store_learning(content: str, salience: float = 0.9, metadata: Optional[Dict] = None) -> Optional[str]:
    """Quick helper to store a learning (long-term)."""
    client = MindClient()
    try:
        return await client.store(Memory(
            content=content,
            temporal_level=TemporalLevel.IDENTITY,
            salience=salience,
            content_type=ContentType.REFLECTION,
            metadata=metadata
        ))
    finally:
        await client.close()


async def retrieve_learnings(query: str, limit: int = 10) -> List[Dict[str, Any]]:
    """Quick helper to retrieve learnings."""
    client = MindClient()
    try:
        return await client.retrieve(
            query=query,
            limit=limit,
            temporal_level=TemporalLevel.IDENTITY,
            content_type=ContentType.REFLECTION
        )
    finally:
        await client.close()
