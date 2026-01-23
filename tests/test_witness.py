"""
Tests for the Spark Witness - Unified Self-Evolving Observer.
"""

import json
import pytest
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from lib.witness import (
    SparkWitness,
    SystemHealth,
    SystemObservation,
    WitnessSnapshot,
    witness,
)


class TestSystemHealth:
    """Test SystemHealth enum."""

    def test_healthy_value(self):
        assert SystemHealth.HEALTHY.value == "healthy"

    def test_degraded_value(self):
        assert SystemHealth.DEGRADED.value == "degraded"

    def test_unhealthy_value(self):
        assert SystemHealth.UNHEALTHY.value == "unhealthy"

    def test_unknown_value(self):
        assert SystemHealth.UNKNOWN.value == "unknown"


class TestSystemObservation:
    """Test SystemObservation dataclass."""

    def test_creation(self):
        obs = SystemObservation(
            system_name="test",
            health=SystemHealth.HEALTHY,
            metrics={"count": 5},
            message="All good"
        )
        assert obs.system_name == "test"
        assert obs.health == SystemHealth.HEALTHY
        assert obs.metrics == {"count": 5}
        assert obs.message == "All good"
        assert obs.timestamp > 0

    def test_to_dict(self):
        obs = SystemObservation(
            system_name="test",
            health=SystemHealth.HEALTHY,
            metrics={"count": 5},
            message="All good"
        )
        d = obs.to_dict()
        assert d["system"] == "test"
        assert d["health"] == "healthy"
        assert d["metrics"] == {"count": 5}
        assert d["message"] == "All good"


class TestWitnessSnapshot:
    """Test WitnessSnapshot dataclass."""

    def test_creation(self):
        obs = SystemObservation(
            system_name="test",
            health=SystemHealth.HEALTHY,
            metrics={},
            message="OK"
        )
        snapshot = WitnessSnapshot(
            timestamp=time.time(),
            overall_health=SystemHealth.HEALTHY,
            systems={"test": obs},
            active_goal=None,
            recent_events=5,
            learnings_count=10,
            anomalies=[]
        )
        assert snapshot.overall_health == SystemHealth.HEALTHY
        assert "test" in snapshot.systems
        assert snapshot.recent_events == 5

    def test_to_dict(self):
        obs = SystemObservation(
            system_name="test",
            health=SystemHealth.HEALTHY,
            metrics={},
            message="OK"
        )
        snapshot = WitnessSnapshot(
            timestamp=time.time(),
            overall_health=SystemHealth.HEALTHY,
            systems={"test": obs},
            active_goal={"goal_type": "feature"},
            recent_events=5,
            learnings_count=10,
            anomalies=["issue1"]
        )
        d = snapshot.to_dict()
        assert d["overall_health"] == "healthy"
        assert "test" in d["systems"]
        assert d["active_goal"]["goal_type"] == "feature"
        assert d["anomalies"] == ["issue1"]


class TestSparkWitness:
    """Test SparkWitness class."""

    def test_init_registers_core_systems(self):
        with patch.object(SparkWitness, '_load_state'):
            witness = SparkWitness()
            # Should have 11 core systems registered
            assert "queue" in witness.systems
            assert "mind" in witness.systems
            assert "goals" in witness.systems
            assert "hooks" in witness.systems
            assert "predictions" in witness.systems
            assert "injections" in witness.systems
            assert "daemon" in witness.systems
            assert "tool_stats" in witness.systems
            assert "learnings" in witness.systems
            assert "error_patterns" in witness.systems
            assert "processing" in witness.systems

    def test_register_system(self):
        with patch.object(SparkWitness, '_load_state'):
            witness = SparkWitness()

            def custom_observer():
                return SystemObservation(
                    system_name="custom",
                    health=SystemHealth.HEALTHY,
                    metrics={},
                    message="Custom system"
                )

            witness.register_system("custom", custom_observer)
            assert "custom" in witness.systems


class TestObserveQueue:
    """Test queue observation."""

    def test_empty_queue(self, tmp_path):
        with patch.object(SparkWitness, '_load_state'):
            witness = SparkWitness()
            # Mock queue file path
            queue_file = tmp_path / "events.jsonl"
            # Don't create the file - test missing file case

            with patch.object(Path, 'home', return_value=tmp_path):
                with patch.object(Path, 'exists', return_value=False):
                    obs = witness._observe_queue()
                    assert obs.health == SystemHealth.HEALTHY
                    assert "0" in obs.message or "Empty" in obs.message


class TestObserveHooks:
    """Test hooks observation."""

    def test_all_hooks_configured(self, tmp_path):
        settings_file = tmp_path / ".claude" / "settings.json"
        settings_file.parent.mkdir(parents=True)
        settings = {
            "hooks": {
                "SessionStart": "python...",
                "UserPromptSubmit": "python...",
                "PreToolUse": "python...",
                "PostToolUse": "python...",
                "PostToolUseFailure": "python...",
                "Stop": "python...",
                "SessionEnd": "python..."
            }
        }
        settings_file.write_text(json.dumps(settings))

        with patch.object(SparkWitness, '_load_state'):
            witness = SparkWitness()
            with patch.object(Path, 'home', return_value=tmp_path):
                obs = witness._observe_hooks()
                assert obs.health == SystemHealth.HEALTHY
                assert "7" in obs.message

    def test_missing_hooks(self, tmp_path):
        settings_file = tmp_path / ".claude" / "settings.json"
        settings_file.parent.mkdir(parents=True)
        settings = {
            "hooks": {
                "SessionStart": "python...",
                # Missing most hooks
            }
        }
        settings_file.write_text(json.dumps(settings))

        with patch.object(SparkWitness, '_load_state'):
            witness = SparkWitness()
            with patch.object(Path, 'home', return_value=tmp_path):
                obs = witness._observe_hooks()
                assert obs.health == SystemHealth.UNHEALTHY
                assert "Missing" in obs.message


class TestExplain:
    """Test explain method."""

    def test_explain_returns_string(self):
        with patch.object(SparkWitness, '_load_state'):
            with patch.object(SparkWitness, 'observe') as mock_observe:
                mock_observe.return_value = WitnessSnapshot(
                    timestamp=time.time(),
                    overall_health=SystemHealth.HEALTHY,
                    systems={},
                    active_goal=None,
                    recent_events=0,
                    learnings_count=0,
                    anomalies=[]
                )
                w = SparkWitness()
                result = w.explain()
                assert isinstance(result, str)
                assert "Spark Status" in result

    def test_explain_verbose_shows_systems(self):
        with patch.object(SparkWitness, '_load_state'):
            with patch.object(SparkWitness, 'observe') as mock_observe:
                obs = SystemObservation(
                    system_name="test",
                    health=SystemHealth.HEALTHY,
                    metrics={},
                    message="Test OK"
                )
                mock_observe.return_value = WitnessSnapshot(
                    timestamp=time.time(),
                    overall_health=SystemHealth.HEALTHY,
                    systems={"test": obs},
                    active_goal=None,
                    recent_events=0,
                    learnings_count=0,
                    anomalies=[]
                )
                w = SparkWitness()
                result = w.explain(verbose=True)
                assert "test" in result
                assert "Test OK" in result


class TestRecordAnomaly:
    """Test anomaly recording."""

    def test_records_anomaly(self):
        with patch.object(SparkWitness, '_load_state'):
            witness = SparkWitness()
            witness._record_anomaly("test:unhealthy")
            assert witness.anomaly_patterns.get("test:unhealthy") == 1

            witness._record_anomaly("test:unhealthy")
            assert witness.anomaly_patterns.get("test:unhealthy") == 2


class TestGetRecurringAnomalies:
    """Test recurring anomaly detection."""

    def test_returns_recurring_only(self):
        with patch.object(SparkWitness, '_load_state'):
            witness = SparkWitness()
            witness.anomaly_patterns = {
                "frequent": 5,
                "once": 1,
                "twice": 2
            }
            recurring = witness._get_recurring_anomalies()
            patterns = [p[0] for p in recurring]
            assert "frequent" in patterns
            assert "twice" in patterns
            assert "once" not in patterns

    def test_sorted_by_count(self):
        with patch.object(SparkWitness, '_load_state'):
            witness = SparkWitness()
            witness.anomaly_patterns = {
                "medium": 3,
                "high": 10,
                "low": 2
            }
            recurring = witness._get_recurring_anomalies()
            assert recurring[0][0] == "high"
            assert recurring[1][0] == "medium"


class TestWitnessFunction:
    """Test the convenience witness() function."""

    def test_returns_explanation(self):
        with patch.object(SparkWitness, '_load_state'):
            with patch.object(SparkWitness, 'explain', return_value="Test output"):
                result = witness()
                assert result == "Test output"


class TestOverallHealthDetermination:
    """Test overall health calculation."""

    def test_unhealthy_if_any_unhealthy(self):
        with patch.object(SparkWitness, '_load_state'):
            w = SparkWitness()
            # Mock all observers to return different health states
            w.systems = {
                "healthy": lambda: SystemObservation("h", SystemHealth.HEALTHY, {}, "OK"),
                "unhealthy": lambda: SystemObservation("u", SystemHealth.UNHEALTHY, {}, "Bad"),
            }
            with patch.object(w, '_get_active_goal', return_value=None):
                with patch.object(w, '_count_recent_events', return_value=0):
                    with patch.object(w, '_count_learnings', return_value=0):
                        with patch.object(w, '_save_state'):
                            snapshot = w.observe()
                            assert snapshot.overall_health == SystemHealth.UNHEALTHY

    def test_degraded_if_any_degraded(self):
        with patch.object(SparkWitness, '_load_state'):
            w = SparkWitness()
            w.systems = {
                "healthy": lambda: SystemObservation("h", SystemHealth.HEALTHY, {}, "OK"),
                "degraded": lambda: SystemObservation("d", SystemHealth.DEGRADED, {}, "Slow"),
            }
            with patch.object(w, '_get_active_goal', return_value=None):
                with patch.object(w, '_count_recent_events', return_value=0):
                    with patch.object(w, '_count_learnings', return_value=0):
                        with patch.object(w, '_save_state'):
                            snapshot = w.observe()
                            assert snapshot.overall_health == SystemHealth.DEGRADED

    def test_healthy_if_all_healthy(self):
        with patch.object(SparkWitness, '_load_state'):
            w = SparkWitness()
            w.systems = {
                "healthy1": lambda: SystemObservation("h1", SystemHealth.HEALTHY, {}, "OK"),
                "healthy2": lambda: SystemObservation("h2", SystemHealth.HEALTHY, {}, "OK"),
            }
            with patch.object(w, '_get_active_goal', return_value=None):
                with patch.object(w, '_count_recent_events', return_value=0):
                    with patch.object(w, '_count_learnings', return_value=0):
                        with patch.object(w, '_save_state'):
                            snapshot = w.observe()
                            assert snapshot.overall_health == SystemHealth.HEALTHY


class TestObservationHistory:
    """Test observation history tracking."""

    def test_stores_observations(self):
        with patch.object(SparkWitness, '_load_state'):
            w = SparkWitness()
            w.systems = {
                "test": lambda: SystemObservation("t", SystemHealth.HEALTHY, {}, "OK"),
            }
            with patch.object(w, '_get_active_goal', return_value=None):
                with patch.object(w, '_count_recent_events', return_value=0):
                    with patch.object(w, '_count_learnings', return_value=0):
                        with patch.object(w, '_save_state'):
                            w.observe()
                            assert len(w.observation_history) == 1
                            w.observe()
                            assert len(w.observation_history) == 2

    def test_limits_history_to_100(self):
        with patch.object(SparkWitness, '_load_state'):
            w = SparkWitness()
            w.systems = {
                "test": lambda: SystemObservation("t", SystemHealth.HEALTHY, {}, "OK"),
            }
            # Pre-fill history
            w.observation_history = [MagicMock() for _ in range(99)]

            with patch.object(w, '_get_active_goal', return_value=None):
                with patch.object(w, '_count_recent_events', return_value=0):
                    with patch.object(w, '_count_learnings', return_value=0):
                        with patch.object(w, '_save_state'):
                            w.observe()
                            assert len(w.observation_history) == 100
                            w.observe()
                            # Should still be 100 after limit
                            assert len(w.observation_history) == 100
