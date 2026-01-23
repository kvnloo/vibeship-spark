"""
Spark Core Library

The ambient self-evolving intelligence layer for Claude Code.
"""

from .queue import SparkQueue, SparkEvent, EventType, quick_capture, get_queue
from .mind_client import MindClient, Memory, ContentType, TemporalLevel
from .learner import SparkLearner, Pattern, ToolStats

__all__ = [
    # Queue
    "SparkQueue",
    "SparkEvent",
    "EventType",
    "quick_capture",
    "get_queue",
    # Mind
    "MindClient",
    "Memory",
    "ContentType",
    "TemporalLevel",
    # Learner
    "SparkLearner",
    "Pattern",
    "ToolStats",
]

__version__ = "0.1.0"
