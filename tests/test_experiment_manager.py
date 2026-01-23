"""
Unit tests for lib/experiment_manager.py

Tests the A/B experimentation system for pattern comparison.
"""

import pytest
import time
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.experiment_manager import (
    ExperimentManager,
    PatternExperiment,
    ExperimentArm,
    ExperimentStatus,
    ExperimentResult
)


# ==================== ExperimentArm Tests ====================

class TestExperimentArm:
    """Tests for ExperimentArm dataclass."""

    def test_creation(self):
        """ExperimentArm creates with required fields."""
        arm = ExperimentArm(arm_id="control", pattern_id="p1")
        assert arm.arm_id == "control"
        assert arm.pattern_id == "p1"
        assert arm.sessions_assigned == []
        assert arm.success_count == 0
        assert arm.failure_count == 0

    def test_total_trials_zero(self):
        """total_trials is 0 initially."""
        arm = ExperimentArm(arm_id="a1", pattern_id="p1")
        assert arm.total_trials == 0

    def test_total_trials_sum(self):
        """total_trials sums success and failure."""
        arm = ExperimentArm(arm_id="a1", pattern_id="p1")
        arm.success_count = 7
        arm.failure_count = 3
        assert arm.total_trials == 10

    def test_success_rate_zero_trials(self):
        """success_rate is 0 with no trials."""
        arm = ExperimentArm(arm_id="a1", pattern_id="p1")
        assert arm.success_rate == 0.0

    def test_success_rate_calculation(self):
        """success_rate calculates correctly."""
        arm = ExperimentArm(arm_id="a1", pattern_id="p1")
        arm.success_count = 8
        arm.failure_count = 2
        assert arm.success_rate == 0.8

    def test_success_rate_all_success(self):
        """success_rate is 1.0 with all successes."""
        arm = ExperimentArm(arm_id="a1", pattern_id="p1")
        arm.success_count = 10
        arm.failure_count = 0
        assert arm.success_rate == 1.0

    def test_success_rate_all_failure(self):
        """success_rate is 0.0 with all failures."""
        arm = ExperimentArm(arm_id="a1", pattern_id="p1")
        arm.success_count = 0
        arm.failure_count = 10
        assert arm.success_rate == 0.0


# ==================== PatternExperiment Tests ====================

class TestPatternExperiment:
    """Tests for PatternExperiment dataclass."""

    def _create_experiment(self, control_sessions=0, treatment_sessions=0):
        """Helper to create experiment with sessions."""
        control = ExperimentArm(arm_id="control", pattern_id="p1")
        control.sessions_assigned = [f"cs{i}" for i in range(control_sessions)]
        treatment = ExperimentArm(arm_id="treatment", pattern_id="p2")
        treatment.sessions_assigned = [f"ts{i}" for i in range(treatment_sessions)]

        return PatternExperiment(
            experiment_id="exp1",
            name="Test",
            description="Test experiment",
            control=control,
            treatment=treatment
        )

    def test_creation(self):
        """PatternExperiment creates with required fields."""
        exp = self._create_experiment()
        assert exp.experiment_id == "exp1"
        assert exp.name == "Test"
        assert exp.status == ExperimentStatus.DRAFT
        assert exp.winner is None

    def test_total_sessions_zero(self):
        """total_sessions is 0 with no assignments."""
        exp = self._create_experiment()
        assert exp.total_sessions == 0

    def test_total_sessions_counts_both_arms(self):
        """total_sessions counts both arms."""
        exp = self._create_experiment(control_sessions=3, treatment_sessions=2)
        assert exp.total_sessions == 5

    def test_is_ready_for_analysis_false_no_trials(self):
        """is_ready_for_analysis is False with no trials."""
        exp = self._create_experiment()
        exp.min_samples_per_arm = 30
        assert exp.is_ready_for_analysis is False

    def test_is_ready_for_analysis_false_insufficient(self):
        """is_ready_for_analysis is False with insufficient trials."""
        control = ExperimentArm(arm_id="control", pattern_id="p1")
        control.success_count = 10
        treatment = ExperimentArm(arm_id="treatment", pattern_id="p2")
        treatment.success_count = 10

        exp = PatternExperiment(
            experiment_id="exp1",
            name="Test",
            description="Test",
            control=control,
            treatment=treatment,
            min_samples_per_arm=30
        )

        assert exp.is_ready_for_analysis is False

    def test_is_ready_for_analysis_true(self):
        """is_ready_for_analysis is True with enough trials."""
        control = ExperimentArm(arm_id="control", pattern_id="p1")
        control.success_count = 25
        control.failure_count = 10
        treatment = ExperimentArm(arm_id="treatment", pattern_id="p2")
        treatment.success_count = 28
        treatment.failure_count = 7

        exp = PatternExperiment(
            experiment_id="exp1",
            name="Test",
            description="Test",
            control=control,
            treatment=treatment,
            min_samples_per_arm=30
        )

        assert exp.is_ready_for_analysis is True


# ==================== ExperimentManager Init Tests ====================

class TestExperimentManagerInit:
    """Tests for ExperimentManager initialization."""

    def test_init_default(self):
        """ExperimentManager initializes with defaults."""
        manager = ExperimentManager()
        assert manager.experiments == {}
        assert manager.session_assignments == {}
        assert manager.mind is None

    def test_init_with_mind_client(self):
        """ExperimentManager accepts Mind client."""
        mock_mind = MagicMock()
        manager = ExperimentManager(mind_client=mock_mind)
        assert manager.mind == mock_mind


# ==================== create_experiment Tests ====================

class TestCreateExperiment:
    """Tests for ExperimentManager.create_experiment."""

    def test_creates_experiment(self):
        """create_experiment creates valid experiment."""
        manager = ExperimentManager()

        exp = manager.create_experiment(
            name="Grep vs Glob",
            description="Compare search tools",
            control_pattern_id="grep_pattern",
            treatment_pattern_id="glob_pattern"
        )

        assert exp.experiment_id is not None
        assert exp.experiment_id.startswith("exp_")
        assert exp.name == "Grep vs Glob"
        assert exp.description == "Compare search tools"
        assert exp.control.pattern_id == "grep_pattern"
        assert exp.treatment.pattern_id == "glob_pattern"
        assert exp.status == ExperimentStatus.DRAFT

    def test_stores_in_experiments_dict(self):
        """Created experiment is stored."""
        manager = ExperimentManager()

        exp = manager.create_experiment(
            name="Test",
            description="Test",
            control_pattern_id="p1",
            treatment_pattern_id="p2"
        )

        assert exp.experiment_id in manager.experiments
        assert manager.experiments[exp.experiment_id] == exp

    def test_custom_min_samples(self):
        """Respects custom min_samples."""
        manager = ExperimentManager()

        exp = manager.create_experiment(
            name="Test",
            description="Test",
            control_pattern_id="p1",
            treatment_pattern_id="p2",
            min_samples=50
        )

        assert exp.min_samples_per_arm == 50

    def test_custom_confidence_level(self):
        """Respects custom confidence_level."""
        manager = ExperimentManager()

        exp = manager.create_experiment(
            name="Test",
            description="Test",
            control_pattern_id="p1",
            treatment_pattern_id="p2",
            confidence_level=0.99
        )

        assert exp.confidence_level == 0.99

    def test_task_category(self):
        """Can set task_category."""
        manager = ExperimentManager()

        exp = manager.create_experiment(
            name="Test",
            description="Test",
            control_pattern_id="p1",
            treatment_pattern_id="p2",
            task_category="search"
        )

        assert exp.task_category == "search"


# ==================== start_experiment Tests ====================

class TestStartExperiment:
    """Tests for ExperimentManager.start_experiment."""

    def test_starts_experiment(self):
        """start_experiment changes status to RUNNING."""
        manager = ExperimentManager()
        exp = manager.create_experiment(
            name="Test",
            description="Test",
            control_pattern_id="p1",
            treatment_pattern_id="p2"
        )

        result = manager.start_experiment(exp.experiment_id)

        assert result is True
        assert exp.status == ExperimentStatus.RUNNING
        assert exp.started_at is not None

    def test_returns_false_unknown_id(self):
        """Returns False for unknown experiment."""
        manager = ExperimentManager()

        result = manager.start_experiment("nonexistent")

        assert result is False


# ==================== assign_session Tests ====================

class TestAssignSession:
    """Tests for ExperimentManager.assign_session."""

    def test_assigns_to_arm(self):
        """assign_session returns arm name."""
        manager = ExperimentManager()
        exp = manager.create_experiment(
            name="Test",
            description="Test",
            control_pattern_id="p1",
            treatment_pattern_id="p2"
        )
        manager.start_experiment(exp.experiment_id)

        arm = manager.assign_session("sess1", exp.experiment_id)

        assert arm in ["control", "treatment"]

    def test_returns_none_not_running(self):
        """Returns None if experiment not running."""
        manager = ExperimentManager()
        exp = manager.create_experiment(
            name="Test",
            description="Test",
            control_pattern_id="p1",
            treatment_pattern_id="p2"
        )
        # Don't start the experiment

        arm = manager.assign_session("sess1", exp.experiment_id)

        assert arm is None

    def test_returns_none_unknown_experiment(self):
        """Returns None for unknown experiment."""
        manager = ExperimentManager()

        arm = manager.assign_session("sess1", "nonexistent")

        assert arm is None

    def test_consistent_assignment(self):
        """Same session gets same arm on repeated calls."""
        manager = ExperimentManager()
        exp = manager.create_experiment(
            name="Test",
            description="Test",
            control_pattern_id="p1",
            treatment_pattern_id="p2"
        )
        manager.start_experiment(exp.experiment_id)

        arm1 = manager.assign_session("sess1", exp.experiment_id)
        arm2 = manager.assign_session("sess1", exp.experiment_id)

        assert arm1 == arm2

    def test_adds_to_sessions_list(self):
        """Adds session to appropriate arm's list."""
        manager = ExperimentManager()
        exp = manager.create_experiment(
            name="Test",
            description="Test",
            control_pattern_id="p1",
            treatment_pattern_id="p2"
        )
        manager.start_experiment(exp.experiment_id)

        arm = manager.assign_session("sess1", exp.experiment_id)

        if arm == "control":
            assert "sess1" in exp.control.sessions_assigned
        else:
            assert "sess1" in exp.treatment.sessions_assigned

    def test_stores_assignment(self):
        """Stores session assignment."""
        manager = ExperimentManager()
        exp = manager.create_experiment(
            name="Test",
            description="Test",
            control_pattern_id="p1",
            treatment_pattern_id="p2"
        )
        manager.start_experiment(exp.experiment_id)

        arm = manager.assign_session("sess1", exp.experiment_id)

        assert "sess1" in manager.session_assignments
        assert manager.session_assignments["sess1"] == (exp.experiment_id, arm)


# ==================== record_outcome Tests ====================

class TestRecordOutcome:
    """Tests for ExperimentManager.record_outcome."""

    def test_records_success(self):
        """Records successful outcome."""
        manager = ExperimentManager()
        exp = manager.create_experiment(
            name="Test",
            description="Test",
            control_pattern_id="p1",
            treatment_pattern_id="p2"
        )
        manager.start_experiment(exp.experiment_id)
        arm = manager.assign_session("sess1", exp.experiment_id)

        result = manager.record_outcome("sess1", exp.experiment_id, was_successful=True)

        assert result is True
        if arm == "control":
            assert exp.control.success_count == 1
        else:
            assert exp.treatment.success_count == 1

    def test_records_failure(self):
        """Records failed outcome."""
        manager = ExperimentManager()
        exp = manager.create_experiment(
            name="Test",
            description="Test",
            control_pattern_id="p1",
            treatment_pattern_id="p2"
        )
        manager.start_experiment(exp.experiment_id)
        arm = manager.assign_session("sess1", exp.experiment_id)

        result = manager.record_outcome("sess1", exp.experiment_id, was_successful=False)

        assert result is True
        if arm == "control":
            assert exp.control.failure_count == 1
        else:
            assert exp.treatment.failure_count == 1

    def test_returns_false_unknown_session(self):
        """Returns False for unassigned session."""
        manager = ExperimentManager()
        exp = manager.create_experiment(
            name="Test",
            description="Test",
            control_pattern_id="p1",
            treatment_pattern_id="p2"
        )
        manager.start_experiment(exp.experiment_id)

        result = manager.record_outcome("unknown_session", exp.experiment_id, was_successful=True)

        assert result is False

    def test_returns_false_unknown_experiment(self):
        """Returns False for unknown experiment."""
        manager = ExperimentManager()

        result = manager.record_outcome("sess1", "nonexistent", was_successful=True)

        assert result is False


# ==================== analyze Tests ====================

class TestAnalyze:
    """Tests for ExperimentManager.analyze."""

    def test_returns_none_no_data(self):
        """Returns None with no trial data."""
        manager = ExperimentManager()
        exp = manager.create_experiment(
            name="Test",
            description="Test",
            control_pattern_id="p1",
            treatment_pattern_id="p2"
        )

        result = manager.analyze(exp.experiment_id)

        assert result is None

    def test_returns_none_unknown_experiment(self):
        """Returns None for unknown experiment."""
        manager = ExperimentManager()

        result = manager.analyze("nonexistent")

        assert result is None

    def test_calculates_success_rates(self):
        """Calculates correct success rates."""
        manager = ExperimentManager()
        exp = manager.create_experiment(
            name="Test",
            description="Test",
            control_pattern_id="p1",
            treatment_pattern_id="p2"
        )
        exp.control.success_count = 70
        exp.control.failure_count = 30
        exp.treatment.success_count = 80
        exp.treatment.failure_count = 20

        result = manager.analyze(exp.experiment_id)

        assert result is not None
        assert result.control_success_rate == 0.7
        assert result.treatment_success_rate == 0.8

    def test_calculates_relative_improvement(self):
        """Calculates correct relative improvement."""
        manager = ExperimentManager()
        exp = manager.create_experiment(
            name="Test",
            description="Test",
            control_pattern_id="p1",
            treatment_pattern_id="p2"
        )
        exp.control.success_count = 50
        exp.control.failure_count = 50
        exp.treatment.success_count = 60
        exp.treatment.failure_count = 40

        result = manager.analyze(exp.experiment_id)

        # (0.6 - 0.5) / 0.5 = 0.2 = 20% improvement
        assert abs(result.relative_improvement - 0.2) < 0.01

    def test_detects_significant_difference(self):
        """Detects significant differences."""
        manager = ExperimentManager()
        exp = manager.create_experiment(
            name="Test",
            description="Test",
            control_pattern_id="p1",
            treatment_pattern_id="p2"
        )
        # Very clear difference
        exp.control.success_count = 30
        exp.control.failure_count = 70
        exp.treatment.success_count = 70
        exp.treatment.failure_count = 30

        result = manager.analyze(exp.experiment_id)

        assert result.is_significant is True
        assert result.recommended_winner == "treatment"

    def test_inconclusive_similar_rates(self):
        """Returns inconclusive for similar rates."""
        manager = ExperimentManager()
        exp = manager.create_experiment(
            name="Test",
            description="Test",
            control_pattern_id="p1",
            treatment_pattern_id="p2"
        )
        # Very similar rates
        exp.control.success_count = 50
        exp.control.failure_count = 50
        exp.treatment.success_count = 51
        exp.treatment.failure_count = 49

        result = manager.analyze(exp.experiment_id)

        assert result.is_significant is False
        assert result.recommended_winner == "inconclusive"


# ==================== conclude Tests ====================

class TestConclude:
    """Tests for ExperimentManager.conclude."""

    def test_concludes_experiment(self):
        """conclude sets status and winner."""
        manager = ExperimentManager()
        exp = manager.create_experiment(
            name="Test",
            description="Test",
            control_pattern_id="p1",
            treatment_pattern_id="p2"
        )
        manager.start_experiment(exp.experiment_id)

        result = manager.conclude(exp.experiment_id, "treatment")

        assert result is True
        assert exp.status == ExperimentStatus.CONCLUDED
        assert exp.winner == "treatment"
        assert exp.concluded_at is not None

    def test_returns_false_unknown(self):
        """Returns False for unknown experiment."""
        manager = ExperimentManager()

        result = manager.conclude("nonexistent", "treatment")

        assert result is False

    def test_returns_false_invalid_winner(self):
        """Returns False for invalid winner."""
        manager = ExperimentManager()
        exp = manager.create_experiment(
            name="Test",
            description="Test",
            control_pattern_id="p1",
            treatment_pattern_id="p2"
        )

        result = manager.conclude(exp.experiment_id, "invalid")

        assert result is False


# ==================== cancel Tests ====================

class TestCancel:
    """Tests for ExperimentManager.cancel."""

    def test_cancels_experiment(self):
        """cancel sets status to CANCELLED."""
        manager = ExperimentManager()
        exp = manager.create_experiment(
            name="Test",
            description="Test",
            control_pattern_id="p1",
            treatment_pattern_id="p2"
        )
        manager.start_experiment(exp.experiment_id)

        result = manager.cancel(exp.experiment_id)

        assert result is True
        assert exp.status == ExperimentStatus.CANCELLED
        assert exp.concluded_at is not None

    def test_returns_false_unknown(self):
        """Returns False for unknown experiment."""
        manager = ExperimentManager()

        result = manager.cancel("nonexistent")

        assert result is False


# ==================== get_active_experiments Tests ====================

class TestGetActiveExperiments:
    """Tests for ExperimentManager.get_active_experiments."""

    def test_returns_running_experiments(self):
        """Returns only running experiments."""
        manager = ExperimentManager()

        exp1 = manager.create_experiment(
            name="Test1",
            description="Test",
            control_pattern_id="p1",
            treatment_pattern_id="p2"
        )
        manager.start_experiment(exp1.experiment_id)

        exp2 = manager.create_experiment(
            name="Test2",
            description="Test",
            control_pattern_id="p3",
            treatment_pattern_id="p4"
        )
        # Don't start exp2

        active = manager.get_active_experiments()

        assert len(active) == 1
        assert active[0].experiment_id == exp1.experiment_id

    def test_returns_empty_none_active(self):
        """Returns empty list when none active."""
        manager = ExperimentManager()

        exp = manager.create_experiment(
            name="Test",
            description="Test",
            control_pattern_id="p1",
            treatment_pattern_id="p2"
        )

        active = manager.get_active_experiments()

        assert len(active) == 0


# ==================== get_experiment_for_task Tests ====================

class TestGetExperimentForTask:
    """Tests for ExperimentManager.get_experiment_for_task."""

    def test_returns_matching_experiment(self):
        """Returns experiment matching task category."""
        manager = ExperimentManager()
        exp = manager.create_experiment(
            name="Search Test",
            description="Test",
            control_pattern_id="p1",
            treatment_pattern_id="p2",
            task_category="search"
        )
        manager.start_experiment(exp.experiment_id)

        result = manager.get_experiment_for_task("search")

        assert result is not None
        assert result.experiment_id == exp.experiment_id

    def test_returns_none_no_match(self):
        """Returns None when no matching experiment."""
        manager = ExperimentManager()
        exp = manager.create_experiment(
            name="Search Test",
            description="Test",
            control_pattern_id="p1",
            treatment_pattern_id="p2",
            task_category="search"
        )
        manager.start_experiment(exp.experiment_id)

        result = manager.get_experiment_for_task("edit")

        assert result is None

    def test_returns_generic_experiment(self):
        """Returns experiment with no task_category for any task."""
        manager = ExperimentManager()
        exp = manager.create_experiment(
            name="Generic Test",
            description="Test",
            control_pattern_id="p1",
            treatment_pattern_id="p2"
            # No task_category - applies to all
        )
        manager.start_experiment(exp.experiment_id)

        result = manager.get_experiment_for_task("any_task")

        assert result is not None


# ==================== get_stats Tests ====================

class TestGetStats:
    """Tests for ExperimentManager.get_stats."""

    def test_returns_stats(self):
        """Returns correct statistics."""
        manager = ExperimentManager()

        exp1 = manager.create_experiment(
            name="Test1",
            description="Test",
            control_pattern_id="p1",
            treatment_pattern_id="p2"
        )
        manager.start_experiment(exp1.experiment_id)

        exp2 = manager.create_experiment(
            name="Test2",
            description="Test",
            control_pattern_id="p3",
            treatment_pattern_id="p4"
        )
        manager.start_experiment(exp2.experiment_id)
        manager.conclude(exp2.experiment_id, "treatment")

        stats = manager.get_stats()

        assert stats["total_experiments"] == 2
        assert stats["running"] == 1
        assert stats["concluded"] == 1
        assert stats["cancelled"] == 0


# ==================== persist_experiment Tests ====================

class TestPersistExperiment:
    """Tests for ExperimentManager.persist_experiment."""

    @pytest.mark.asyncio
    async def test_persists_to_mind(self):
        """Persists experiment to Mind."""
        mock_mind = AsyncMock()
        mock_mind.store = AsyncMock(return_value="mem_123")
        manager = ExperimentManager(mind_client=mock_mind)

        exp = manager.create_experiment(
            name="Test",
            description="Test",
            control_pattern_id="p1",
            treatment_pattern_id="p2"
        )
        exp.control.success_count = 30
        exp.treatment.success_count = 35

        result = await manager.persist_experiment(exp.experiment_id)

        assert result is True
        mock_mind.store.assert_called_once()

    @pytest.mark.asyncio
    async def test_returns_false_no_mind(self):
        """Returns False without Mind client."""
        manager = ExperimentManager()

        exp = manager.create_experiment(
            name="Test",
            description="Test",
            control_pattern_id="p1",
            treatment_pattern_id="p2"
        )

        result = await manager.persist_experiment(exp.experiment_id)

        assert result is False

    @pytest.mark.asyncio
    async def test_returns_false_unknown(self):
        """Returns False for unknown experiment."""
        mock_mind = AsyncMock()
        manager = ExperimentManager(mind_client=mock_mind)

        result = await manager.persist_experiment("nonexistent")

        assert result is False


# ==================== auto_conclude_if_significant Tests ====================

class TestAutoConcludeIfSignificant:
    """Tests for ExperimentManager.auto_conclude_if_significant."""

    def test_concludes_when_significant(self):
        """Auto-concludes when statistically significant."""
        manager = ExperimentManager()
        exp = manager.create_experiment(
            name="Test",
            description="Test",
            control_pattern_id="p1",
            treatment_pattern_id="p2",
            min_samples=30
        )
        manager.start_experiment(exp.experiment_id)

        # Clear difference
        exp.control.success_count = 20
        exp.control.failure_count = 30
        exp.treatment.success_count = 40
        exp.treatment.failure_count = 10

        result = manager.auto_conclude_if_significant(exp.experiment_id)

        assert result is not None
        assert exp.status == ExperimentStatus.CONCLUDED
        assert exp.winner == "treatment"

    def test_returns_none_not_ready(self):
        """Returns None when not enough samples."""
        manager = ExperimentManager()
        exp = manager.create_experiment(
            name="Test",
            description="Test",
            control_pattern_id="p1",
            treatment_pattern_id="p2",
            min_samples=30
        )
        manager.start_experiment(exp.experiment_id)

        # Not enough samples
        exp.control.success_count = 5
        exp.treatment.success_count = 5

        result = manager.auto_conclude_if_significant(exp.experiment_id)

        assert result is None
        assert exp.status == ExperimentStatus.RUNNING
