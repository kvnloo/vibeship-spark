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
