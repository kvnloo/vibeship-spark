"""
Spark Goal Classifier: Shared classification logic.

This module provides the single source of truth for goal classification.
Used by both:
- hooks/observe.py (fast, synchronous)
- lib/goal_tracker.py (full tracking)

IMPORTANT: This must be FAST (<5ms) for hook usage.
"""

from enum import Enum
from typing import Tuple


class GoalType(Enum):
    """Types of goals users pursue."""
    # Work goals
    DEBUG = "debug"           # Fix a bug, resolve an error
    FEATURE = "feature"       # Add new functionality
    REFACTOR = "refactor"     # Improve existing code
    EXPLORE = "explore"       # Understand codebase, find something
    TEST = "test"             # Write or run tests
    DEPLOY = "deploy"         # Build, deploy, release
    DOCS = "docs"             # Documentation, comments
    CONFIG = "config"         # Configuration, setup

    # Non-work (conversational)
    CONVERSATION = "conversation"  # Thanks, yes, no, casual
    AFFIRMATION = "affirmation"    # Approval of proposed action
    CLARIFICATION = "clarification"  # Questions about what was said
    META = "meta"                    # Questions about Spark/Claude itself

    UNKNOWN = "unknown"


# Keyword sets for classification
KEYWORDS = {
    GoalType.DEBUG: [
        "fix", "bug", "error", "broken", "fail", "crash", "issue", "wrong",
        "debug", "not working", "doesn't work", "won't work", "can't",
        "exception", "traceback", "undefined", "null", "missing"
    ],
    GoalType.FEATURE: [
        "add", "create", "implement", "build", "new", "feature", "make",
        "develop", "write", "generate", "introduce", "enable"
    ],
    GoalType.REFACTOR: [
        "refactor", "improve", "clean", "optimize", "reorganize", "simplify",
        "rename", "restructure", "extract", "consolidate", "deduplicate"
    ],
    GoalType.EXPLORE: [
        "find", "search", "where", "what is", "how does", "understand",
        "look at", "show me", "explain", "analyze", "check", "review",
        "examine", "inspect", "explore", "investigate"
    ],
    GoalType.TEST: [
        "test", "spec", "coverage", "assert", "verify", "validate",
        "unit test", "integration test", "pytest", "jest"
    ],
    GoalType.DEPLOY: [
        "deploy", "build", "release", "publish", "ship", "push", "merge",
        "production", "staging", "ci/cd", "pipeline"
    ],
    GoalType.DOCS: [
        "document", "readme", "comment", "describe", "docstring",
        "documentation", "wiki", "changelog"
    ],
    GoalType.CONFIG: [
        "config", "setup", "install", "configure", "setting", "environment",
        "env", "dotenv", "yaml", "toml", "ini"
    ],
    # Conversational types
    GoalType.CONVERSATION: [
        "thanks", "thank you", "bye", "goodbye", "see ya", "later",
        "hi", "hello", "hey", "good morning", "good night",
        "cool", "nice", "awesome", "great job"
    ],
    GoalType.AFFIRMATION: [
        "yes", "yep", "yeah", "sure", "ok", "okay", "go ahead",
        "do it", "let's do it", "sounds good", "perfect", "exactly",
        "that's right", "correct", "proceed", "continue"
    ],
    GoalType.CLARIFICATION: [
        "what do you mean", "can you explain", "i don't understand",
        "could you clarify", "not sure what", "confused about",
        "what exactly", "which one", "how so"
    ],
    GoalType.META: [
        "what can you do", "help me understand", "how do i use",
        "what are your capabilities", "tell me about yourself",
        "what is spark", "how does this work"
    ],
}


def classify_goal(prompt: str) -> Tuple[GoalType, float]:
    """
    Classify a user prompt into a goal type.

    Returns (GoalType, confidence) where confidence is 0.0-1.0.

    This function is optimized for speed (<5ms).
    """
    prompt_lower = prompt.lower().strip()

    # Quick checks for very short prompts (likely conversational)
    if len(prompt_lower) < 10:
        # Single word or very short
        for keyword in KEYWORDS[GoalType.AFFIRMATION]:
            if prompt_lower == keyword or prompt_lower.rstrip("!.") == keyword:
                return GoalType.AFFIRMATION, 0.95
        for keyword in KEYWORDS[GoalType.CONVERSATION]:
            if keyword in prompt_lower:
                return GoalType.CONVERSATION, 0.9
        # Very short but not conversational - likely affirmation
        if len(prompt_lower) < 5:
            return GoalType.AFFIRMATION, 0.7

    # Check for conversational types first (they're often misclassified)
    for goal_type in [GoalType.AFFIRMATION, GoalType.CONVERSATION,
                      GoalType.CLARIFICATION, GoalType.META]:
        keywords = KEYWORDS[goal_type]
        for keyword in keywords:
            if keyword in prompt_lower:
                return goal_type, 0.85

    # Score each work type
    scores = {}
    for goal_type in [GoalType.DEBUG, GoalType.FEATURE, GoalType.REFACTOR,
                      GoalType.EXPLORE, GoalType.TEST, GoalType.DEPLOY,
                      GoalType.DOCS, GoalType.CONFIG]:
        keywords = KEYWORDS[goal_type]
        score = 0
        for keyword in keywords:
            if keyword in prompt_lower:
                # Boost score for keyword at start of prompt
                if prompt_lower.startswith(keyword):
                    score += 2
                else:
                    score += 1
        scores[goal_type] = score

    # Get best match
    if scores:
        best_type = max(scores, key=scores.get)
        best_score = scores[best_type]
        if best_score > 0:
            # Calculate confidence based on score and uniqueness
            total_score = sum(scores.values())
            confidence = min(0.95, 0.5 + (best_score / max(total_score, 1)) * 0.4)
            return best_type, confidence

    return GoalType.UNKNOWN, 0.3


def is_conversational(goal_type: GoalType) -> bool:
    """Check if a goal type is conversational (non-work)."""
    return goal_type in (
        GoalType.CONVERSATION,
        GoalType.AFFIRMATION,
        GoalType.CLARIFICATION,
        GoalType.META
    )


def should_track_as_goal(goal_type: GoalType) -> bool:
    """
    Determine if this goal type should be tracked as an active goal.

    Conversational prompts shouldn't count toward goal success/failure.
    """
    return not is_conversational(goal_type)


# Quick test
if __name__ == "__main__":
    test_prompts = [
        "Fix the bug in authentication",
        "Add a new login feature",
        "Yes",
        "Thanks!",
        "What do you want to do next?",
        "Let's do it",
        "Can you explain that?",
        "help me understand spark",
        "find where errors are handled",
        "refactor the database code",
    ]

    print("Goal Classification Test:")
    print("-" * 60)
    for prompt in test_prompts:
        goal_type, confidence = classify_goal(prompt)
        track = "TRACK" if should_track_as_goal(goal_type) else "SKIP"
        print(f"[{track}] {goal_type.value:15} ({confidence:.0%}) | {prompt[:40]}")
