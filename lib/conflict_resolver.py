"""
Spark Conflict Resolver: Handle conflicting learnings intelligently.

When Spark extracts patterns that contradict each other, this module
resolves them using a layered approach:

1. Scope Hierarchy: More specific learnings override general ones
2. Effective Scoring: Confidence * Recency * Sample Weight
3. Automatic Experiments: When close, let data decide
4. Merge When Compatible: Different triggers = not a conflict
5. Resolution History: Learn from how conflicts are resolved

This system is self-healing - conflicts naturally resolve through
experimentation and data accumulation.
"""

import math
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from .prompt_evolver import PromptPattern
from .experiment_manager import ExperimentManager


class LearningScope(Enum):
    """Scope levels for learnings, from most to least specific."""
    SESSION = "session"      # Current session only
    PROJECT = "project"      # This specific project
    FRAMEWORK = "framework"  # Projects using this framework
    LANGUAGE = "language"    # Projects in this language
    UNIVERSAL = "universal"  # All projects


class ResolutionStrategy(Enum):
    """How a conflict was resolved."""
    SCOPE_HIERARCHY = "scope_hierarchy"      # More specific scope won
    SCORE_DIFFERENCE = "score_difference"    # Higher effective score won
    EXPERIMENT = "experiment"                # A/B test initiated
    MERGED = "merged"                        # Learnings combined
    RECENCY = "recency"                      # More recent won
    MANUAL = "manual"                        # User decided
    UNRESOLVED = "unresolved"                # Could not resolve


@dataclass
class Conflict:
    """Represents a detected conflict between two learnings."""
    conflict_id: str
    learning_a: PromptPattern
    learning_b: PromptPattern
    conflict_type: str  # "tool_preference", "approach", "error_avoidance"
    detected_at: datetime = field(default_factory=datetime.now)
    context: Dict[str, Any] = field(default_factory=dict)

    @property
    def age_seconds(self) -> float:
        """How old is this conflict detection."""
        return (datetime.now() - self.detected_at).total_seconds()


@dataclass
class ConflictRecord:
    """Record of how a conflict was resolved."""
    conflict_id: str
    learning_a_id: str
    learning_b_id: str
    detected_at: datetime
    resolved_at: Optional[datetime] = None
    resolution: ResolutionStrategy = ResolutionStrategy.UNRESOLVED
    resolution_reason: str = ""
    winner_id: Optional[str] = None
    experiment_id: Optional[str] = None
    outcome_verified: bool = False
    outcome_success: Optional[bool] = None

    @property
    def is_resolved(self) -> bool:
        """Check if conflict has been resolved."""
        return self.resolution != ResolutionStrategy.UNRESOLVED

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "conflict_id": self.conflict_id,
            "learning_a_id": self.learning_a_id,
            "learning_b_id": self.learning_b_id,
            "detected_at": self.detected_at.isoformat(),
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
            "resolution": self.resolution.value,
            "resolution_reason": self.resolution_reason,
            "winner_id": self.winner_id,
            "experiment_id": self.experiment_id,
            "outcome_verified": self.outcome_verified,
            "outcome_success": self.outcome_success
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ConflictRecord":
        """Create from dictionary."""
        return cls(
            conflict_id=data["conflict_id"],
            learning_a_id=data["learning_a_id"],
            learning_b_id=data["learning_b_id"],
            detected_at=datetime.fromisoformat(data["detected_at"]),
            resolved_at=datetime.fromisoformat(data["resolved_at"]) if data.get("resolved_at") else None,
            resolution=ResolutionStrategy(data.get("resolution", "unresolved")),
            resolution_reason=data.get("resolution_reason", ""),
            winner_id=data.get("winner_id"),
            experiment_id=data.get("experiment_id"),
            outcome_verified=data.get("outcome_verified", False),
            outcome_success=data.get("outcome_success")
        )


@dataclass
class ResolutionResult:
    """Result of resolving a conflict."""
    conflict_id: str
    resolved: bool
    winner: Optional[PromptPattern] = None
    strategy: ResolutionStrategy = ResolutionStrategy.UNRESOLVED
    reason: str = ""
    experiment_id: Optional[str] = None
    merged_pattern: Optional[PromptPattern] = None


class ConflictResolver:
    """
    Resolves conflicting learnings using a layered approach.

    Resolution order:
    1. Scope hierarchy (project beats universal)
    2. Effective score (confidence * recency * samples)
    3. Experimentation (A/B test close calls)
    4. Recency (tie-breaker)
    """

    # Scoring parameters
    RECENCY_HALF_LIFE_DAYS = 30  # Recency factor half-life
    MIN_SAMPLES_FULL_WEIGHT = 20  # Samples needed for full weight
    SCORE_WIN_THRESHOLD = 1.5  # 50% higher score to win outright

    # Experiment thresholds
    MIN_SAMPLES_FOR_EXPERIMENT = 5  # Each learning needs this many
    EXPERIMENT_MIN_SAMPLES = 10  # Experiment needs this to conclude

    def __init__(
        self,
        experiment_manager: Optional[ExperimentManager] = None,
        decay_rate_days: float = 30.0
    ):
        """
        Initialize the conflict resolver.

        Args:
            experiment_manager: Optional manager for A/B experiments
            decay_rate_days: Half-life for recency decay (configurable)
        """
        self.experiment_manager = experiment_manager
        self.decay_rate_days = decay_rate_days

        # Track conflicts and resolutions
        self.active_conflicts: Dict[str, Conflict] = {}
        self.resolution_history: List[ConflictRecord] = []

        # Statistics
        self.total_conflicts_detected = 0
        self.total_conflicts_resolved = 0
        self.resolutions_by_strategy: Dict[str, int] = {
            s.value: 0 for s in ResolutionStrategy
        }

    def detect_conflicts(
        self,
        learnings: List[PromptPattern]
    ) -> List[Conflict]:
        """
        Detect conflicts among a list of learnings.

        Args:
            learnings: List of patterns to check for conflicts

        Returns:
            List of detected conflicts
        """
        conflicts = []
        seen_pairs = set()

        for i, a in enumerate(learnings):
            for b in learnings[i + 1:]:
                # Skip if already checked
                pair_key = tuple(sorted([a.pattern_id, b.pattern_id]))
                if pair_key in seen_pairs:
                    continue
                seen_pairs.add(pair_key)

                # Check if they conflict
                conflict_type = self._check_conflict(a, b)
                if conflict_type:
                    conflict_id = f"conflict_{a.pattern_id}_{b.pattern_id}"
                    conflict = Conflict(
                        conflict_id=conflict_id,
                        learning_a=a,
                        learning_b=b,
                        conflict_type=conflict_type
                    )
                    conflicts.append(conflict)
                    self.active_conflicts[conflict_id] = conflict
                    self.total_conflicts_detected += 1

        return conflicts

    def _check_conflict(
        self,
        a: PromptPattern,
        b: PromptPattern
    ) -> Optional[str]:
        """
        Check if two learnings conflict.

        Returns conflict type or None if no conflict.
        """
        # Same pattern type - potential conflict
        if a.pattern_type != b.pattern_type:
            return None

        # Tool preference conflict
        if a.pattern_type == "tool_effectiveness":
            # Same tool, different success assessments
            a_tool = a.trigger_conditions.get("tool_name")
            b_tool = b.trigger_conditions.get("tool_name")
            if a_tool and a_tool == b_tool:
                # Check if recommendations differ significantly
                a_rate = a.success_count / max(1, a.total_uses)
                b_rate = b.success_count / max(1, b.total_uses)
                if abs(a_rate - b_rate) > 0.3:  # 30% difference
                    return "tool_preference"

        # Approach conflict
        if a.pattern_type == "tool_sequence":
            # Same trigger, different approaches
            if self._triggers_overlap(a.trigger_conditions, b.trigger_conditions):
                if a.approach != b.approach:
                    return "approach"

        # Error avoidance conflict
        if a.pattern_type == "error_avoidance":
            a_error = a.trigger_conditions.get("error_type")
            b_error = b.trigger_conditions.get("error_type")
            if a_error and a_error == b_error:
                if a.approach != b.approach:
                    return "error_avoidance"

        return None

    def _triggers_overlap(
        self,
        triggers_a: Dict[str, Any],
        triggers_b: Dict[str, Any]
    ) -> bool:
        """Check if trigger conditions overlap significantly."""
        if not triggers_a or not triggers_b:
            return False

        # Check for common keys with same values
        common_keys = set(triggers_a.keys()) & set(triggers_b.keys())
        if not common_keys:
            return False

        matches = sum(
            1 for k in common_keys
            if triggers_a[k] == triggers_b[k]
        )

        # More than half of common keys match
        return matches > len(common_keys) / 2

    def resolve(
        self,
        learnings: List[PromptPattern],
        context: Optional[Dict[str, Any]] = None
    ) -> List[PromptPattern]:
        """
        Resolve conflicts in a list of learnings and return non-conflicting set.

        Args:
            learnings: List of potentially conflicting learnings
            context: Current context for scope determination

        Returns:
            List of learnings with conflicts resolved
        """
        if not learnings:
            return []

        if len(learnings) == 1:
            return learnings

        # Detect conflicts
        conflicts = self.detect_conflicts(learnings)

        if not conflicts:
            return learnings

        # Resolve each conflict
        resolved_learnings = list(learnings)
        losers = set()

        for conflict in conflicts:
            result = self.resolve_single_conflict(conflict, context)

            if result.resolved and result.winner:
                # Mark the loser
                loser_id = (
                    conflict.learning_b.pattern_id
                    if result.winner.pattern_id == conflict.learning_a.pattern_id
                    else conflict.learning_a.pattern_id
                )
                losers.add(loser_id)
            elif result.merged_pattern:
                # Replace both with merged
                losers.add(conflict.learning_a.pattern_id)
                losers.add(conflict.learning_b.pattern_id)
                resolved_learnings.append(result.merged_pattern)

        # Filter out losers
        return [l for l in resolved_learnings if l.pattern_id not in losers]

    def resolve_single_conflict(
        self,
        conflict: Conflict,
        context: Optional[Dict[str, Any]] = None
    ) -> ResolutionResult:
        """
        Resolve a single conflict between two learnings.

        Uses layered resolution:
        1. Scope hierarchy
        2. Effective score
        3. Experimentation
        4. Recency
        """
        a = conflict.learning_a
        b = conflict.learning_b
        context = context or {}

        # Layer 1: Scope hierarchy
        scope_a = self._determine_scope(a, context)
        scope_b = self._determine_scope(b, context)

        if scope_a != scope_b:
            # More specific scope wins
            scope_order = [
                LearningScope.SESSION,
                LearningScope.PROJECT,
                LearningScope.FRAMEWORK,
                LearningScope.LANGUAGE,
                LearningScope.UNIVERSAL
            ]
            if scope_order.index(scope_a) < scope_order.index(scope_b):
                return self._record_win(
                    conflict, a, ResolutionStrategy.SCOPE_HIERARCHY,
                    f"Scope {scope_a.value} beats {scope_b.value}"
                )
            else:
                return self._record_win(
                    conflict, b, ResolutionStrategy.SCOPE_HIERARCHY,
                    f"Scope {scope_b.value} beats {scope_a.value}"
                )

        # Layer 2: Effective score
        score_a = self.calculate_effective_score(a)
        score_b = self.calculate_effective_score(b)

        if score_a > score_b * self.SCORE_WIN_THRESHOLD:
            return self._record_win(
                conflict, a, ResolutionStrategy.SCORE_DIFFERENCE,
                f"Score {score_a:.2f} vs {score_b:.2f}"
            )
        elif score_b > score_a * self.SCORE_WIN_THRESHOLD:
            return self._record_win(
                conflict, b, ResolutionStrategy.SCORE_DIFFERENCE,
                f"Score {score_b:.2f} vs {score_a:.2f}"
            )

        # Layer 3: Can they be merged?
        merged = self._try_merge(a, b)
        if merged:
            return self._record_merge(conflict, merged)

        # Layer 4: Experimentation
        if self._should_experiment(a, b):
            return self._start_experiment(conflict)

        # Layer 5: Recency (tie-breaker)
        a_time = self._get_created_time(a)
        b_time = self._get_created_time(b)

        if a_time > b_time:
            return self._record_win(
                conflict, a, ResolutionStrategy.RECENCY,
                "More recent learning"
            )
        else:
            return self._record_win(
                conflict, b, ResolutionStrategy.RECENCY,
                "More recent learning"
            )

    def _determine_scope(
        self,
        learning: PromptPattern,
        context: Dict[str, Any]
    ) -> LearningScope:
        """Determine the scope of a learning."""
        triggers = learning.trigger_conditions

        # Check for session-specific
        if triggers.get("session_id"):
            return LearningScope.SESSION

        # Check for project-specific
        if triggers.get("project_path") or triggers.get("project_name"):
            return LearningScope.PROJECT

        # Check for framework-specific
        if triggers.get("framework"):
            return LearningScope.FRAMEWORK

        # Check for language-specific
        if triggers.get("language"):
            return LearningScope.LANGUAGE

        return LearningScope.UNIVERSAL

    def calculate_effective_score(self, learning: PromptPattern) -> float:
        """
        Calculate effective score combining confidence, recency, and samples.

        Score = confidence * recency_factor * sample_weight

        Where:
        - recency_factor = 0.5 + 0.5 * exp(-age_days / decay_rate)
        - sample_weight = min(1.0, sample_count / MIN_SAMPLES)
        """
        # Base confidence from success rate
        if learning.total_uses > 0:
            confidence = learning.success_count / learning.total_uses
        else:
            confidence = 0.5  # Neutral for no data

        # Recency factor
        created_time = self._get_created_time(learning)
        age_days = (datetime.now() - created_time).days
        recency_factor = 0.5 + 0.5 * math.exp(-age_days / self.decay_rate_days)

        # Sample weight
        sample_weight = min(1.0, learning.total_uses / self.MIN_SAMPLES_FULL_WEIGHT)

        return confidence * recency_factor * sample_weight

    def _get_created_time(self, learning: PromptPattern) -> datetime:
        """Get creation time from learning, handling different formats."""
        if hasattr(learning, 'created_at') and learning.created_at:
            if isinstance(learning.created_at, datetime):
                return learning.created_at
            elif isinstance(learning.created_at, (int, float)):
                return datetime.fromtimestamp(learning.created_at)
        return datetime.now()

    def _try_merge(
        self,
        a: PromptPattern,
        b: PromptPattern
    ) -> Optional[PromptPattern]:
        """
        Try to merge two learnings into one more nuanced pattern.

        Returns merged pattern or None if not mergeable.
        """
        # Can only merge if triggers are complementary, not overlapping
        if self._triggers_overlap(a.trigger_conditions, b.trigger_conditions):
            return None

        # Different trigger conditions = both valid in their contexts
        # Create a merged pattern that includes both conditions
        merged_triggers = {
            "merged_from": [a.pattern_id, b.pattern_id],
            "condition_a": a.trigger_conditions,
            "condition_b": b.trigger_conditions
        }

        merged_approach = f"Context A: {a.approach}\nContext B: {b.approach}"

        return PromptPattern(
            pattern_id=f"merged_{a.pattern_id}_{b.pattern_id}",
            pattern_type=a.pattern_type,
            description=f"Merged: {a.description} + {b.description}",
            trigger_conditions=merged_triggers,
            approach=merged_approach,
            total_uses=a.total_uses + b.total_uses,
            success_count=a.success_count + b.success_count,
            failure_count=a.failure_count + b.failure_count
        )

    def _should_experiment(
        self,
        a: PromptPattern,
        b: PromptPattern
    ) -> bool:
        """Check if we should run an A/B experiment."""
        if not self.experiment_manager:
            return False

        # Both need minimum samples
        if a.total_uses < self.MIN_SAMPLES_FOR_EXPERIMENT:
            return False
        if b.total_uses < self.MIN_SAMPLES_FOR_EXPERIMENT:
            return False

        # Check if experiment already exists
        for exp in self.experiment_manager.get_active_experiments():
            if (exp.control_arm.pattern_id == a.pattern_id and
                exp.treatment_arm.pattern_id == b.pattern_id):
                return False
            if (exp.control_arm.pattern_id == b.pattern_id and
                exp.treatment_arm.pattern_id == a.pattern_id):
                return False

        return True

    def _start_experiment(self, conflict: Conflict) -> ResolutionResult:
        """Start an A/B experiment to resolve a conflict."""
        a = conflict.learning_a
        b = conflict.learning_b

        exp = self.experiment_manager.create_experiment(
            name=f"Conflict: {a.pattern_id} vs {b.pattern_id}",
            description=f"Resolving conflict type: {conflict.conflict_type}",
            control_pattern_id=a.pattern_id,
            treatment_pattern_id=b.pattern_id,
            min_samples=self.EXPERIMENT_MIN_SAMPLES
        )

        self.experiment_manager.start_experiment(exp.experiment_id)

        # Record the resolution
        record = ConflictRecord(
            conflict_id=conflict.conflict_id,
            learning_a_id=a.pattern_id,
            learning_b_id=b.pattern_id,
            detected_at=conflict.detected_at,
            resolution=ResolutionStrategy.EXPERIMENT,
            resolution_reason=f"A/B test initiated",
            experiment_id=exp.experiment_id
        )
        self.resolution_history.append(record)
        self.resolutions_by_strategy[ResolutionStrategy.EXPERIMENT.value] += 1

        # Return control as winner during experiment
        return ResolutionResult(
            conflict_id=conflict.conflict_id,
            resolved=True,
            winner=a,  # Use control during experiment
            strategy=ResolutionStrategy.EXPERIMENT,
            reason=f"Experiment {exp.experiment_id} started",
            experiment_id=exp.experiment_id
        )

    def _record_win(
        self,
        conflict: Conflict,
        winner: PromptPattern,
        strategy: ResolutionStrategy,
        reason: str
    ) -> ResolutionResult:
        """Record a resolution where one learning wins."""
        loser_id = (
            conflict.learning_b.pattern_id
            if winner.pattern_id == conflict.learning_a.pattern_id
            else conflict.learning_a.pattern_id
        )

        record = ConflictRecord(
            conflict_id=conflict.conflict_id,
            learning_a_id=conflict.learning_a.pattern_id,
            learning_b_id=conflict.learning_b.pattern_id,
            detected_at=conflict.detected_at,
            resolved_at=datetime.now(),
            resolution=strategy,
            resolution_reason=reason,
            winner_id=winner.pattern_id
        )
        self.resolution_history.append(record)
        self.total_conflicts_resolved += 1
        self.resolutions_by_strategy[strategy.value] += 1

        # Remove from active
        if conflict.conflict_id in self.active_conflicts:
            del self.active_conflicts[conflict.conflict_id]

        return ResolutionResult(
            conflict_id=conflict.conflict_id,
            resolved=True,
            winner=winner,
            strategy=strategy,
            reason=reason
        )

    def _record_merge(
        self,
        conflict: Conflict,
        merged: PromptPattern
    ) -> ResolutionResult:
        """Record a resolution where learnings are merged."""
        record = ConflictRecord(
            conflict_id=conflict.conflict_id,
            learning_a_id=conflict.learning_a.pattern_id,
            learning_b_id=conflict.learning_b.pattern_id,
            detected_at=conflict.detected_at,
            resolved_at=datetime.now(),
            resolution=ResolutionStrategy.MERGED,
            resolution_reason="Complementary trigger conditions",
            winner_id=merged.pattern_id
        )
        self.resolution_history.append(record)
        self.total_conflicts_resolved += 1
        self.resolutions_by_strategy[ResolutionStrategy.MERGED.value] += 1

        # Remove from active
        if conflict.conflict_id in self.active_conflicts:
            del self.active_conflicts[conflict.conflict_id]

        return ResolutionResult(
            conflict_id=conflict.conflict_id,
            resolved=True,
            strategy=ResolutionStrategy.MERGED,
            reason="Learnings merged into combined pattern",
            merged_pattern=merged
        )

    def verify_resolution_outcome(
        self,
        conflict_id: str,
        success: bool
    ) -> bool:
        """
        Verify if a resolution outcome was successful.

        Call this after observing whether the resolved learning worked.
        """
        for record in self.resolution_history:
            if record.conflict_id == conflict_id:
                record.outcome_verified = True
                record.outcome_success = success
                return True
        return False

    def get_active_conflicts(self) -> List[Conflict]:
        """Get all active (unresolved) conflicts."""
        return list(self.active_conflicts.values())

    def get_resolution_history(
        self,
        limit: int = 50
    ) -> List[ConflictRecord]:
        """Get recent resolution history."""
        return self.resolution_history[-limit:]

    def get_stats(self) -> Dict[str, Any]:
        """Get resolver statistics."""
        verified = [r for r in self.resolution_history if r.outcome_verified]
        successful = [r for r in verified if r.outcome_success]

        return {
            "total_conflicts_detected": self.total_conflicts_detected,
            "total_conflicts_resolved": self.total_conflicts_resolved,
            "active_conflicts": len(self.active_conflicts),
            "resolutions_by_strategy": self.resolutions_by_strategy.copy(),
            "resolution_success_rate": (
                len(successful) / len(verified) if verified else 0.0
            ),
            "decay_rate_days": self.decay_rate_days,
            "history_size": len(self.resolution_history)
        }

    def set_decay_rate(self, days: float) -> None:
        """
        Set the decay rate for recency scoring.

        Args:
            days: Half-life in days for recency decay
        """
        if days > 0:
            self.decay_rate_days = days

    def clear_history(self) -> int:
        """Clear resolution history. Returns count cleared."""
        count = len(self.resolution_history)
        self.resolution_history.clear()
        return count

    def export_history(self) -> List[Dict[str, Any]]:
        """Export resolution history as list of dicts."""
        return [r.to_dict() for r in self.resolution_history]

    def import_history(self, records: List[Dict[str, Any]]) -> int:
        """Import resolution history from list of dicts."""
        count = 0
        for data in records:
            try:
                record = ConflictRecord.from_dict(data)
                self.resolution_history.append(record)
                count += 1
            except (KeyError, ValueError):
                continue
        return count
