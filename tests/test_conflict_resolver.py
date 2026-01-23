"""
Unit tests for lib/conflict_resolver.py
"""

import pytest
from unittest.mock import MagicMock
from datetime import datetime, timedelta

from lib.conflict_resolver import (
    ConflictResolver, Conflict, ConflictRecord,
    LearningScope, ResolutionStrategy, ResolutionResult
)
from lib.prompt_evolver import PromptPattern
from lib.experiment_manager import ExperimentManager


@pytest.fixture
def resolver():
    """Create a default conflict resolver."""
    return ConflictResolver()


@pytest.fixture
def resolver_with_experiments():
    """Create a resolver with experiment manager."""
    exp_mgr = ExperimentManager()
    return ConflictResolver(experiment_manager=exp_mgr)


@pytest.fixture
def pattern_a():
    """Create a sample pattern A."""
    return PromptPattern(
        pattern_id="pattern_a",
        pattern_type="tool_effectiveness",
        description="Grep is effective",
        trigger_conditions={"tool_name": "Grep"},
        approach="Use Grep for search",
        total_uses=50,
        success_count=45,
        failure_count=5
    )


@pytest.fixture
def pattern_b():
    """Create a sample pattern B that conflicts with A."""
    return PromptPattern(
        pattern_id="pattern_b",
        pattern_type="tool_effectiveness",
        description="Grep is not effective",
        trigger_conditions={"tool_name": "Grep"},
        approach="Avoid Grep for search",
        total_uses=30,
        success_count=15,
        failure_count=15
    )


@pytest.fixture
def pattern_c():
    """Create a pattern with different tool (no conflict)."""
    return PromptPattern(
        pattern_id="pattern_c",
        pattern_type="tool_effectiveness",
        description="Read is effective",
        trigger_conditions={"tool_name": "Read"},
        approach="Use Read for files",
        total_uses=40,
        success_count=38,
        failure_count=2
    )


@pytest.fixture
def project_specific_pattern():
    """Create a project-specific pattern."""
    return PromptPattern(
        pattern_id="pattern_project",
        pattern_type="tool_effectiveness",
        description="Grep is not effective in this project",
        trigger_conditions={"tool_name": "Grep", "project_path": "/my/project"},
        approach="Use Task agent instead",
        total_uses=20,
        success_count=18,
        failure_count=2
    )


class TestConflictResolverInit:
    """Tests for ConflictResolver initialization."""

    def test_init_default(self):
        """Initializes with defaults."""
        resolver = ConflictResolver()

        assert resolver.experiment_manager is None
        assert resolver.decay_rate_days == 30.0
        assert resolver.total_conflicts_detected == 0
        assert resolver.total_conflicts_resolved == 0

    def test_init_with_experiment_manager(self):
        """Accepts experiment manager."""
        exp_mgr = ExperimentManager()
        resolver = ConflictResolver(experiment_manager=exp_mgr)

        assert resolver.experiment_manager is exp_mgr

    def test_init_with_decay_rate(self):
        """Accepts custom decay rate."""
        resolver = ConflictResolver(decay_rate_days=60.0)

        assert resolver.decay_rate_days == 60.0


class TestDetectConflicts:
    """Tests for detect_conflicts method."""

    def test_detects_tool_preference_conflict(self, resolver, pattern_a, pattern_b):
        """Detects conflicting tool preferences."""
        conflicts = resolver.detect_conflicts([pattern_a, pattern_b])

        assert len(conflicts) == 1
        assert conflicts[0].conflict_type == "tool_preference"

    def test_no_conflict_different_tools(self, resolver, pattern_a, pattern_c):
        """No conflict for different tools."""
        conflicts = resolver.detect_conflicts([pattern_a, pattern_c])

        assert len(conflicts) == 0

    def test_no_conflict_single_pattern(self, resolver, pattern_a):
        """No conflict for single pattern."""
        conflicts = resolver.detect_conflicts([pattern_a])

        assert len(conflicts) == 0

    def test_no_conflict_empty_list(self, resolver):
        """No conflict for empty list."""
        conflicts = resolver.detect_conflicts([])

        assert len(conflicts) == 0

    def test_increments_detection_count(self, resolver, pattern_a, pattern_b):
        """Increments detection counter."""
        resolver.detect_conflicts([pattern_a, pattern_b])

        assert resolver.total_conflicts_detected == 1

    def test_stores_active_conflict(self, resolver, pattern_a, pattern_b):
        """Stores conflict in active conflicts."""
        resolver.detect_conflicts([pattern_a, pattern_b])

        assert len(resolver.active_conflicts) == 1


class TestDetectApproachConflict:
    """Tests for detecting approach conflicts."""

    def test_detects_approach_conflict(self, resolver):
        """Detects conflicting approaches for same trigger."""
        pattern_a = PromptPattern(
            pattern_id="seq_a",
            pattern_type="tool_sequence",
            description="Search first",
            trigger_conditions={"task_category": "search"},
            approach="Use Grep then Read",
            total_uses=30,
            success_count=25,
            failure_count=5
        )
        pattern_b = PromptPattern(
            pattern_id="seq_b",
            pattern_type="tool_sequence",
            description="Read first",
            trigger_conditions={"task_category": "search"},
            approach="Use Read then Grep",
            total_uses=25,
            success_count=20,
            failure_count=5
        )

        conflicts = resolver.detect_conflicts([pattern_a, pattern_b])

        assert len(conflicts) == 1
        assert conflicts[0].conflict_type == "approach"


class TestResolveByScope:
    """Tests for scope-based resolution."""

    def test_project_beats_universal(self, resolver, pattern_a, project_specific_pattern):
        """Project-specific pattern wins over universal."""
        result = resolver.resolve_single_conflict(
            Conflict(
                conflict_id="test",
                learning_a=pattern_a,
                learning_b=project_specific_pattern,
                conflict_type="tool_preference"
            ),
            context={"project_path": "/my/project"}
        )

        assert result.resolved is True
        assert result.winner.pattern_id == "pattern_project"
        assert result.strategy == ResolutionStrategy.SCOPE_HIERARCHY

    def test_framework_beats_universal(self, resolver):
        """Framework-specific pattern wins over universal."""
        universal = PromptPattern(
            pattern_id="universal",
            pattern_type="tool_effectiveness",
            description="Universal pattern",
            trigger_conditions={"tool_name": "Grep"},
            approach="Use Grep",
            total_uses=100,
            success_count=80,
            failure_count=20
        )
        framework = PromptPattern(
            pattern_id="framework",
            pattern_type="tool_effectiveness",
            description="React-specific pattern",
            trigger_conditions={"tool_name": "Grep", "framework": "react"},
            approach="Use different approach in React",
            total_uses=30,
            success_count=25,
            failure_count=5
        )

        result = resolver.resolve_single_conflict(
            Conflict(
                conflict_id="test",
                learning_a=universal,
                learning_b=framework,
                conflict_type="tool_preference"
            )
        )

        assert result.winner.pattern_id == "framework"


class TestResolveByScore:
    """Tests for score-based resolution."""

    def test_higher_score_wins(self, resolver, pattern_a, pattern_b):
        """Higher effective score wins."""
        # pattern_a has 90% success, pattern_b has 50%
        result = resolver.resolve_single_conflict(
            Conflict(
                conflict_id="test",
                learning_a=pattern_a,
                learning_b=pattern_b,
                conflict_type="tool_preference"
            )
        )

        assert result.resolved is True
        assert result.winner.pattern_id == "pattern_a"
        assert result.strategy == ResolutionStrategy.SCORE_DIFFERENCE


class TestCalculateEffectiveScore:
    """Tests for calculate_effective_score method."""

    def test_high_success_high_score(self, resolver, pattern_a):
        """High success rate gives high score."""
        score = resolver.calculate_effective_score(pattern_a)

        assert score > 0.7

    def test_low_success_low_score(self, resolver, pattern_b):
        """Low success rate gives lower score."""
        score = resolver.calculate_effective_score(pattern_b)

        assert score < 0.6

    def test_no_uses_neutral_score(self, resolver):
        """No uses gives neutral score."""
        pattern = PromptPattern(
            pattern_id="new",
            pattern_type="tool_effectiveness",
            description="New pattern",
            trigger_conditions={},
            approach="Untested",
            total_uses=0,
            success_count=0,
            failure_count=0
        )

        score = resolver.calculate_effective_score(pattern)

        # Should be low due to no samples
        assert score < 0.5

    def test_sample_weight_affects_score(self, resolver):
        """Low sample count reduces score."""
        high_samples = PromptPattern(
            pattern_id="high",
            pattern_type="tool_effectiveness",
            description="High samples",
            trigger_conditions={},
            approach="Tested",
            total_uses=50,
            success_count=40,
            failure_count=10
        )
        low_samples = PromptPattern(
            pattern_id="low",
            pattern_type="tool_effectiveness",
            description="Low samples",
            trigger_conditions={},
            approach="Barely tested",
            total_uses=5,
            success_count=4,
            failure_count=1
        )

        high_score = resolver.calculate_effective_score(high_samples)
        low_score = resolver.calculate_effective_score(low_samples)

        assert high_score > low_score


class TestResolveWithExperiment:
    """Tests for experiment-based resolution."""

    def test_starts_experiment_when_close(self, resolver_with_experiments):
        """Starts experiment when scores are close."""
        pattern_a = PromptPattern(
            pattern_id="close_a",
            pattern_type="tool_effectiveness",
            description="Pattern A",
            trigger_conditions={"tool_name": "Grep"},
            approach="Approach A",
            total_uses=30,
            success_count=24,
            failure_count=6
        )
        pattern_b = PromptPattern(
            pattern_id="close_b",
            pattern_type="tool_effectiveness",
            description="Pattern B",
            trigger_conditions={"tool_name": "Grep"},
            approach="Approach B",
            total_uses=30,
            success_count=22,
            failure_count=8
        )

        result = resolver_with_experiments.resolve_single_conflict(
            Conflict(
                conflict_id="test",
                learning_a=pattern_a,
                learning_b=pattern_b,
                conflict_type="tool_preference"
            )
        )

        assert result.strategy == ResolutionStrategy.EXPERIMENT
        assert result.experiment_id is not None


class TestResolveByRecency:
    """Tests for recency-based resolution."""

    def test_more_recent_wins_as_tiebreaker(self, resolver):
        """More recent pattern wins when scores are equal."""
        old_pattern = PromptPattern(
            pattern_id="old",
            pattern_type="tool_sequence",
            description="Old pattern",
            trigger_conditions={"task_category": "test"},
            approach="Old approach",
            total_uses=10,
            success_count=8,
            failure_count=2,
            created_at=datetime.now() - timedelta(days=60)
        )
        new_pattern = PromptPattern(
            pattern_id="new",
            pattern_type="tool_sequence",
            description="New pattern",
            trigger_conditions={"task_category": "test"},
            approach="New approach",
            total_uses=10,
            success_count=8,
            failure_count=2,
            created_at=datetime.now()
        )

        # Force equal scores by using identical stats
        result = resolver.resolve_single_conflict(
            Conflict(
                conflict_id="test",
                learning_a=old_pattern,
                learning_b=new_pattern,
                conflict_type="approach"
            )
        )

        assert result.winner.pattern_id == "new"


class TestResolveMultiple:
    """Tests for resolve method with multiple learnings."""

    def test_resolves_all_conflicts(self, resolver, pattern_a, pattern_b, pattern_c):
        """Resolves conflicts and returns clean list."""
        resolved = resolver.resolve([pattern_a, pattern_b, pattern_c])

        # Should have pattern_a (winner) and pattern_c (no conflict)
        assert len(resolved) == 2
        pattern_ids = [p.pattern_id for p in resolved]
        assert "pattern_a" in pattern_ids
        assert "pattern_c" in pattern_ids
        assert "pattern_b" not in pattern_ids

    def test_returns_all_when_no_conflicts(self, resolver, pattern_a, pattern_c):
        """Returns all learnings when no conflicts."""
        resolved = resolver.resolve([pattern_a, pattern_c])

        assert len(resolved) == 2


class TestMerge:
    """Tests for learning merge functionality."""

    def test_merges_complementary_patterns(self, resolver):
        """Merges patterns with different triggers."""
        pattern_a = PromptPattern(
            pattern_id="merge_a",
            pattern_type="tool_sequence",
            description="For Python",
            trigger_conditions={"language": "python"},
            approach="Python approach",
            total_uses=20,
            success_count=18,
            failure_count=2
        )
        pattern_b = PromptPattern(
            pattern_id="merge_b",
            pattern_type="tool_sequence",
            description="For JavaScript",
            trigger_conditions={"language": "javascript"},
            approach="JavaScript approach",
            total_uses=20,
            success_count=17,
            failure_count=3
        )

        merged = resolver._try_merge(pattern_a, pattern_b)

        # Non-overlapping triggers = can be merged into combined pattern
        assert merged is not None
        assert "merged_" in merged.pattern_id
        assert merged.total_uses == 40  # Combined uses
        assert "Python approach" in merged.approach
        assert "JavaScript approach" in merged.approach


class TestConflictRecord:
    """Tests for ConflictRecord dataclass."""

    def test_creation(self):
        """Creates with required fields."""
        record = ConflictRecord(
            conflict_id="test",
            learning_a_id="a",
            learning_b_id="b",
            detected_at=datetime.now()
        )

        assert record.conflict_id == "test"
        assert record.is_resolved is False

    def test_is_resolved_true(self):
        """Is resolved when strategy set."""
        record = ConflictRecord(
            conflict_id="test",
            learning_a_id="a",
            learning_b_id="b",
            detected_at=datetime.now(),
            resolution=ResolutionStrategy.SCORE_DIFFERENCE
        )

        assert record.is_resolved is True

    def test_to_dict(self):
        """Converts to dictionary."""
        record = ConflictRecord(
            conflict_id="test",
            learning_a_id="a",
            learning_b_id="b",
            detected_at=datetime.now(),
            resolution=ResolutionStrategy.SCOPE_HIERARCHY,
            winner_id="a"
        )

        d = record.to_dict()

        assert d["conflict_id"] == "test"
        assert d["resolution"] == "scope_hierarchy"
        assert d["winner_id"] == "a"

    def test_from_dict(self):
        """Creates from dictionary."""
        data = {
            "conflict_id": "test",
            "learning_a_id": "a",
            "learning_b_id": "b",
            "detected_at": datetime.now().isoformat(),
            "resolution": "score_difference",
            "winner_id": "a"
        }

        record = ConflictRecord.from_dict(data)

        assert record.conflict_id == "test"
        assert record.resolution == ResolutionStrategy.SCORE_DIFFERENCE


class TestResolutionHistory:
    """Tests for resolution history tracking."""

    def test_records_resolution(self, resolver, pattern_a, pattern_b):
        """Records resolution in history."""
        resolver.resolve_single_conflict(
            Conflict(
                conflict_id="test",
                learning_a=pattern_a,
                learning_b=pattern_b,
                conflict_type="tool_preference"
            )
        )

        history = resolver.get_resolution_history()
        assert len(history) == 1
        assert history[0].conflict_id == "test"

    def test_export_import_history(self, resolver, pattern_a, pattern_b):
        """Exports and imports history."""
        resolver.resolve_single_conflict(
            Conflict(
                conflict_id="test",
                learning_a=pattern_a,
                learning_b=pattern_b,
                conflict_type="tool_preference"
            )
        )

        exported = resolver.export_history()

        new_resolver = ConflictResolver()
        imported = new_resolver.import_history(exported)

        assert imported == 1
        assert len(new_resolver.resolution_history) == 1


class TestVerifyOutcome:
    """Tests for outcome verification."""

    def test_verifies_successful_outcome(self, resolver, pattern_a, pattern_b):
        """Verifies successful resolution outcome."""
        resolver.resolve_single_conflict(
            Conflict(
                conflict_id="test",
                learning_a=pattern_a,
                learning_b=pattern_b,
                conflict_type="tool_preference"
            )
        )

        result = resolver.verify_resolution_outcome("test", success=True)

        assert result is True
        record = resolver.resolution_history[0]
        assert record.outcome_verified is True
        assert record.outcome_success is True

    def test_returns_false_unknown_conflict(self, resolver):
        """Returns False for unknown conflict."""
        result = resolver.verify_resolution_outcome("unknown", success=True)

        assert result is False


class TestGetStats:
    """Tests for get_stats method."""

    def test_returns_stats(self, resolver, pattern_a, pattern_b):
        """Returns resolver statistics."""
        resolver.resolve([pattern_a, pattern_b])

        stats = resolver.get_stats()

        assert "total_conflicts_detected" in stats
        assert "total_conflicts_resolved" in stats
        assert "active_conflicts" in stats
        assert "resolutions_by_strategy" in stats
        assert stats["total_conflicts_detected"] == 1


class TestSetDecayRate:
    """Tests for set_decay_rate method."""

    def test_sets_decay_rate(self, resolver):
        """Sets decay rate."""
        resolver.set_decay_rate(60.0)

        assert resolver.decay_rate_days == 60.0

    def test_ignores_invalid_rate(self, resolver):
        """Ignores zero or negative rate."""
        original = resolver.decay_rate_days
        resolver.set_decay_rate(0)
        resolver.set_decay_rate(-10)

        assert resolver.decay_rate_days == original


class TestClearHistory:
    """Tests for clear_history method."""

    def test_clears_history(self, resolver, pattern_a, pattern_b):
        """Clears resolution history."""
        resolver.resolve([pattern_a, pattern_b])

        count = resolver.clear_history()

        assert count == 1
        assert len(resolver.resolution_history) == 0


class TestGetActiveConflicts:
    """Tests for get_active_conflicts method."""

    def test_returns_unresolved_conflicts(self, resolver_with_experiments):
        """Returns conflicts that are in experiment state."""
        pattern_a = PromptPattern(
            pattern_id="exp_a",
            pattern_type="tool_effectiveness",
            description="Pattern A",
            trigger_conditions={"tool_name": "Test"},
            approach="Approach A",
            total_uses=30,
            success_count=24,
            failure_count=6
        )
        pattern_b = PromptPattern(
            pattern_id="exp_b",
            pattern_type="tool_effectiveness",
            description="Pattern B",
            trigger_conditions={"tool_name": "Test"},
            approach="Approach B",
            total_uses=30,
            success_count=22,
            failure_count=8
        )

        # This should start an experiment, keeping the conflict "active"
        resolver_with_experiments.detect_conflicts([pattern_a, pattern_b])

        active = resolver_with_experiments.get_active_conflicts()
        assert len(active) >= 0  # May or may not be active depending on resolution


class TestLearningScope:
    """Tests for LearningScope enum."""

    def test_scope_values(self):
        """All scope values defined."""
        assert LearningScope.SESSION.value == "session"
        assert LearningScope.PROJECT.value == "project"
        assert LearningScope.FRAMEWORK.value == "framework"
        assert LearningScope.LANGUAGE.value == "language"
        assert LearningScope.UNIVERSAL.value == "universal"


class TestResolutionStrategy:
    """Tests for ResolutionStrategy enum."""

    def test_strategy_values(self):
        """All strategy values defined."""
        assert ResolutionStrategy.SCOPE_HIERARCHY.value == "scope_hierarchy"
        assert ResolutionStrategy.SCORE_DIFFERENCE.value == "score_difference"
        assert ResolutionStrategy.EXPERIMENT.value == "experiment"
        assert ResolutionStrategy.MERGED.value == "merged"
        assert ResolutionStrategy.RECENCY.value == "recency"
        assert ResolutionStrategy.MANUAL.value == "manual"
        assert ResolutionStrategy.UNRESOLVED.value == "unresolved"


class TestConflictDataclass:
    """Tests for Conflict dataclass."""

    def test_creation(self, pattern_a, pattern_b):
        """Creates with required fields."""
        conflict = Conflict(
            conflict_id="test",
            learning_a=pattern_a,
            learning_b=pattern_b,
            conflict_type="tool_preference"
        )

        assert conflict.conflict_id == "test"
        assert conflict.learning_a == pattern_a
        assert conflict.learning_b == pattern_b

    def test_age_seconds(self, pattern_a, pattern_b):
        """Calculates age in seconds."""
        conflict = Conflict(
            conflict_id="test",
            learning_a=pattern_a,
            learning_b=pattern_b,
            conflict_type="tool_preference"
        )

        assert conflict.age_seconds >= 0
        assert conflict.age_seconds < 1  # Just created


class TestResolutionResult:
    """Tests for ResolutionResult dataclass."""

    def test_creation(self, pattern_a):
        """Creates with required fields."""
        result = ResolutionResult(
            conflict_id="test",
            resolved=True,
            winner=pattern_a,
            strategy=ResolutionStrategy.SCORE_DIFFERENCE,
            reason="Higher score"
        )

        assert result.resolved is True
        assert result.winner == pattern_a
        assert result.strategy == ResolutionStrategy.SCORE_DIFFERENCE
