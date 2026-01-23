"""
Spark Goal Tracker: Understand what users want to achieve.

The missing piece: tool success != goal success.
"Edit worked" doesn't mean "the bug is fixed."

This tracker:
1. Captures goals from user prompts
2. Classifies goal types (debug, feature, refactor, explore)
3. Tracks progress toward goals
4. Detects completion signals
5. Learns which approaches work for which goals
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime
from enum import Enum
import re
import hashlib


class GoalType(Enum):
    """Types of goals users pursue."""
    DEBUG = "debug"           # Fix a bug, resolve an error
    FEATURE = "feature"       # Add new functionality
    REFACTOR = "refactor"     # Improve existing code
    EXPLORE = "explore"       # Understand codebase, find something
    TEST = "test"             # Write or run tests
    DEPLOY = "deploy"         # Build, deploy, release
    DOCS = "docs"             # Documentation, comments
    CONFIG = "config"         # Configuration, setup
    UNKNOWN = "unknown"


class GoalStatus(Enum):
    """Status of a goal."""
    ACTIVE = "active"         # Currently working on
    COMPLETED = "completed"   # Successfully finished
    ABANDONED = "abandoned"   # User moved on without completing
    BLOCKED = "blocked"       # Stuck, needs help


@dataclass
class Goal:
    """A user goal being tracked."""
    goal_id: str
    session_id: str
    created_at: float

    # What the user wants
    raw_prompt: str           # Original user prompt
    goal_type: GoalType
    description: str          # Normalized description
    keywords: List[str]       # Key terms from the goal

    # Progress tracking
    status: GoalStatus = GoalStatus.ACTIVE
    actions: List[Dict[str, Any]] = field(default_factory=list)  # Tools used
    progress_signals: List[str] = field(default_factory=list)    # Positive signals
    blocker_signals: List[str] = field(default_factory=list)     # Negative signals

    # Outcome
    completed_at: Optional[float] = None
    success_score: float = 0.0  # 0.0 to 1.0
    approach_summary: Optional[str] = None  # What worked

    @property
    def duration_seconds(self) -> float:
        end = self.completed_at or datetime.now().timestamp()
        return end - self.created_at

    @property
    def tool_sequence(self) -> List[str]:
        return [a.get("tool", "?") for a in self.actions]


@dataclass
class GoalStrategy:
    """A learned strategy for achieving a goal type."""
    goal_type: GoalType
    description: str
    tool_sequence: List[str]   # Effective tool sequence
    success_rate: float
    sample_size: int
    avg_duration_sec: float
    tips: List[str] = field(default_factory=list)


class GoalTracker:
    """
    Track user goals and learn what works.

    This is the strategic layer - learning at the task level,
    not just the tool level.
    """

    # Keywords for goal classification
    DEBUG_KEYWORDS = ["fix", "bug", "error", "broken", "fail", "crash", "issue", "wrong", "debug", "not working"]
    FEATURE_KEYWORDS = ["add", "create", "implement", "build", "new", "feature", "make", "develop"]
    REFACTOR_KEYWORDS = ["refactor", "improve", "clean", "optimize", "reorganize", "simplify", "rename"]
    EXPLORE_KEYWORDS = ["find", "search", "where", "what", "how", "understand", "look", "show", "explain", "analyze", "check", "review", "examine", "inspect"]
    TEST_KEYWORDS = ["test", "spec", "coverage", "assert", "verify", "check"]
    DEPLOY_KEYWORDS = ["deploy", "build", "release", "publish", "ship", "push", "merge"]
    DOCS_KEYWORDS = ["document", "readme", "comment", "describe", "explain"]
    CONFIG_KEYWORDS = ["config", "setup", "install", "configure", "setting", "environment"]

    # Completion signals
    POSITIVE_SIGNALS = ["thanks", "perfect", "great", "works", "done", "fixed", "solved", "awesome", "nice"]
    NEGATIVE_SIGNALS = ["no", "wrong", "not what", "try again", "still", "doesn't work", "failed"]

    def __init__(self):
        self.active_goals: Dict[str, Goal] = {}  # goal_id -> Goal
        self.completed_goals: List[Goal] = []
        self.strategies: Dict[GoalType, List[GoalStrategy]] = {}

    def capture_goal(self, session_id: str, user_prompt: str) -> Goal:
        """
        Capture a goal from a user prompt.

        Call this when user submits a prompt.
        """
        goal_id = self._generate_id(session_id, user_prompt)

        # Classify the goal
        goal_type = self._classify_goal(user_prompt)
        description = self._extract_description(user_prompt, goal_type)
        keywords = self._extract_keywords(user_prompt)

        goal = Goal(
            goal_id=goal_id,
            session_id=session_id,
            created_at=datetime.now().timestamp(),
            raw_prompt=user_prompt[:500],  # Truncate long prompts
            goal_type=goal_type,
            description=description,
            keywords=keywords
        )

        # Replace any existing active goal for this session
        # (assumes one main goal at a time)
        old_goal = self._get_active_goal(session_id)
        if old_goal:
            old_goal.status = GoalStatus.ABANDONED
            self.completed_goals.append(old_goal)
            del self.active_goals[old_goal.goal_id]

        self.active_goals[goal_id] = goal
        return goal

    def track_action(self, session_id: str, tool_name: str, success: bool,
                     error: Optional[str] = None) -> Optional[str]:
        """
        Track an action toward the current goal.

        Returns progress signal if significant.
        """
        goal = self._get_active_goal(session_id)
        if not goal:
            return None

        action = {
            "tool": tool_name,
            "success": success,
            "timestamp": datetime.now().timestamp(),
            "error": error[:100] if error else None
        }
        goal.actions.append(action)

        # Detect progress signals
        signal = None
        if success:
            # Positive progress
            if tool_name == "Bash" and not error:
                signal = "command_succeeded"
            elif tool_name == "Edit":
                signal = "code_modified"
            elif tool_name == "Write":
                signal = "file_created"
        else:
            # Blocker
            if error:
                goal.blocker_signals.append(error[:50])
                signal = f"blocked:{error[:30]}"

        if signal:
            goal.progress_signals.append(signal)

        return signal

    def check_completion(self, session_id: str, user_message: str) -> Optional[Dict]:
        """
        Check if user message signals goal completion.

        Returns completion info if goal completed.
        """
        goal = self._get_active_goal(session_id)
        if not goal:
            return None

        message_lower = user_message.lower()

        # Check for positive completion signals
        if any(signal in message_lower for signal in self.POSITIVE_SIGNALS):
            return self._complete_goal(goal, success=True, reason="positive_signal")

        # Check for negative signals (goal failed/abandoned)
        if any(signal in message_lower for signal in self.NEGATIVE_SIGNALS):
            goal.blocker_signals.append(f"user:{message_lower[:30]}")
            # Don't complete yet - user might retry
            return None

        # Check for new goal (implicit completion of old)
        new_goal_type = self._classify_goal(user_message)
        if new_goal_type != GoalType.UNKNOWN and new_goal_type != goal.goal_type:
            # User moved to different type of task
            return self._complete_goal(goal, success=True, reason="new_goal_started")

        return None

    def complete_current_goal(self, session_id: str, success: bool = True,
                              reason: str = "explicit") -> Optional[Dict]:
        """Explicitly complete the current goal."""
        goal = self._get_active_goal(session_id)
        if goal:
            return self._complete_goal(goal, success, reason)
        return None

    def _complete_goal(self, goal: Goal, success: bool, reason: str) -> Dict:
        """Complete a goal and extract learnings."""
        goal.completed_at = datetime.now().timestamp()
        goal.status = GoalStatus.COMPLETED if success else GoalStatus.ABANDONED

        # Calculate success score
        if success:
            # Base score
            score = 0.7
            # Bonus for no blockers
            if not goal.blocker_signals:
                score += 0.2
            # Bonus for quick completion
            if goal.duration_seconds < 300:  # < 5 minutes
                score += 0.1
            goal.success_score = min(score, 1.0)
        else:
            goal.success_score = 0.3

        # Summarize approach
        goal.approach_summary = self._summarize_approach(goal)

        # Move to completed
        if goal.goal_id in self.active_goals:
            del self.active_goals[goal.goal_id]
        self.completed_goals.append(goal)

        # Update strategy learning
        self._update_strategy(goal)

        return {
            "goal_id": goal.goal_id,
            "goal_type": goal.goal_type.value,
            "success": success,
            "success_score": goal.success_score,
            "duration_sec": goal.duration_seconds,
            "actions_count": len(goal.actions),
            "approach": goal.approach_summary,
            "reason": reason
        }

    def _classify_goal(self, prompt: str) -> GoalType:
        """Classify goal type from prompt."""
        prompt_lower = prompt.lower()

        # Score each type
        scores = {
            GoalType.DEBUG: sum(1 for k in self.DEBUG_KEYWORDS if k in prompt_lower),
            GoalType.FEATURE: sum(1 for k in self.FEATURE_KEYWORDS if k in prompt_lower),
            GoalType.REFACTOR: sum(1 for k in self.REFACTOR_KEYWORDS if k in prompt_lower),
            GoalType.EXPLORE: sum(1 for k in self.EXPLORE_KEYWORDS if k in prompt_lower),
            GoalType.TEST: sum(1 for k in self.TEST_KEYWORDS if k in prompt_lower),
            GoalType.DEPLOY: sum(1 for k in self.DEPLOY_KEYWORDS if k in prompt_lower),
            GoalType.DOCS: sum(1 for k in self.DOCS_KEYWORDS if k in prompt_lower),
            GoalType.CONFIG: sum(1 for k in self.CONFIG_KEYWORDS if k in prompt_lower),
        }

        # Get highest scoring type
        best_type = max(scores, key=scores.get)
        if scores[best_type] > 0:
            return best_type
        return GoalType.UNKNOWN

    def _extract_description(self, prompt: str, goal_type: GoalType) -> str:
        """Extract a normalized description."""
        # Take first sentence or first 100 chars
        first_sentence = prompt.split('.')[0].split('?')[0].split('!')[0]
        if len(first_sentence) > 100:
            first_sentence = first_sentence[:97] + "..."
        return first_sentence.strip()

    def _extract_keywords(self, prompt: str) -> List[str]:
        """Extract key terms from prompt."""
        # Simple keyword extraction - words > 4 chars, not common
        common = {"the", "and", "for", "that", "this", "with", "from", "have", "been", "would", "could", "should"}
        words = re.findall(r'\b\w+\b', prompt.lower())
        keywords = [w for w in words if len(w) > 4 and w not in common]
        return list(set(keywords))[:10]

    def _summarize_approach(self, goal: Goal) -> str:
        """Summarize what approach was used."""
        if not goal.actions:
            return "no actions taken"

        # Get tool sequence
        tools = goal.tool_sequence
        unique_tools = list(dict.fromkeys(tools))  # Preserve order, remove dups

        if len(unique_tools) <= 3:
            return " -> ".join(unique_tools)
        else:
            return f"{unique_tools[0]} -> ... -> {unique_tools[-1]} ({len(tools)} actions)"

    def _update_strategy(self, goal: Goal):
        """Update learned strategies from completed goal."""
        if goal.goal_type == GoalType.UNKNOWN:
            return

        if goal.goal_type not in self.strategies:
            self.strategies[goal.goal_type] = []

        # Find or create strategy for this tool sequence
        sequence = goal.tool_sequence
        existing = None
        for s in self.strategies[goal.goal_type]:
            if s.tool_sequence == sequence:
                existing = s
                break

        if existing:
            # Update existing strategy
            n = existing.sample_size
            existing.success_rate = (existing.success_rate * n + goal.success_score) / (n + 1)
            existing.avg_duration_sec = (existing.avg_duration_sec * n + goal.duration_seconds) / (n + 1)
            existing.sample_size += 1
        else:
            # Create new strategy
            strategy = GoalStrategy(
                goal_type=goal.goal_type,
                description=goal.description,
                tool_sequence=sequence,
                success_rate=goal.success_score,
                sample_size=1,
                avg_duration_sec=goal.duration_seconds
            )
            self.strategies[goal.goal_type].append(strategy)

    def get_strategy_recommendation(self, goal_type: GoalType) -> Optional[str]:
        """Get a recommendation for how to approach a goal type."""
        if goal_type not in self.strategies:
            return None

        strategies = self.strategies[goal_type]
        if not strategies:
            return None

        # Find best strategy (highest success rate with enough samples)
        best = None
        for s in strategies:
            if s.sample_size >= 2 and s.success_rate >= 0.7:
                if best is None or s.success_rate > best.success_rate:
                    best = s

        if best:
            seq = " -> ".join(best.tool_sequence[:5])
            return f"For {goal_type.value}: try {seq} ({best.success_rate:.0%} success)"
        return None

    def _get_active_goal(self, session_id: str) -> Optional[Goal]:
        """Get active goal for session."""
        for goal in self.active_goals.values():
            if goal.session_id == session_id:
                return goal
        return None

    def _generate_id(self, session_id: str, prompt: str) -> str:
        """Generate unique goal ID."""
        data = f"{session_id}:{prompt[:50]}:{datetime.now().timestamp()}"
        return f"goal_{hashlib.md5(data.encode()).hexdigest()[:12]}"

    def get_stats(self) -> Dict[str, Any]:
        """Get tracking statistics."""
        if not self.completed_goals:
            return {"total_goals": 0}

        # Goal type distribution
        type_counts = {}
        type_success = {}
        for goal in self.completed_goals:
            t = goal.goal_type.value
            type_counts[t] = type_counts.get(t, 0) + 1
            if t not in type_success:
                type_success[t] = []
            type_success[t].append(goal.success_score)

        # Average success by type
        avg_success = {}
        for t, scores in type_success.items():
            avg_success[t] = sum(scores) / len(scores)

        return {
            "total_goals": len(self.completed_goals),
            "active_goals": len(self.active_goals),
            "goal_types": type_counts,
            "avg_success_by_type": avg_success,
            "strategies_learned": sum(len(s) for s in self.strategies.values())
        }

    def get_current_goal_info(self, session_id: str) -> Optional[Dict]:
        """Get info about current goal for display."""
        goal = self._get_active_goal(session_id)
        if not goal:
            return None

        return {
            "type": goal.goal_type.value,
            "description": goal.description,
            "actions_so_far": len(goal.actions),
            "duration_sec": goal.duration_seconds,
            "blockers": len(goal.blocker_signals),
            "tool_sequence": goal.tool_sequence[-5:]  # Last 5
        }
