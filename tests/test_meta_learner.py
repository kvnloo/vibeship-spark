"""
Tests for lib/meta_learner.py
"""

import pytest
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime

# Add lib to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.meta_learner import (
    MetaLearner, LearningEvent, LearningTrend, PruneCandidate, MetaInsight
)


class TestLearningEvent:
    """Tests for LearningEvent dataclass."""

    def test_creation(self):
        """LearningEvent creates with required fields."""
        event = LearningEvent(
            event_id="e1",
            timestamp=1234567890.0,
            learning_type="tool",
            source="learner",
            confidence=0.8
        )
        assert event.event_id == "e1"
        assert event.learning_type == "tool"
        assert event.confidence == 0.8

    def test_optional_fields(self):
        """LearningEvent handles optional fields."""
        event = LearningEvent(
            event_id="e1",
            timestamp=1234567890.0,
            learning_type="skill",
            source="skill_evolver",
            confidence=0.7,
            was_useful=True,
            usage_count=5
        )
        assert event.was_useful is True
        assert event.usage_count == 5


class TestLearningTrend:
    """Tests for LearningTrend dataclass."""

    def test_creation(self):
        """LearningTrend creates correctly."""
        trend = LearningTrend(
            learning_type="tool",
            sample_count=20,
            avg_confidence=0.85,
            confidence_trend=0.02,
            stability=0.9,
            velocity=2.5,
            is_saturated=True
        )
        assert trend.learning_type == "tool"
        assert trend.is_saturated is True


class TestPruneCandidate:
    """Tests for PruneCandidate dataclass."""

    def test_creation(self):
        """PruneCandidate creates correctly."""
        candidate = PruneCandidate(
            learning_id="l1",
            learning_type="error",
            reason="Old and low confidence",
            confidence=0.2,
            age_days=45.0
        )
        assert candidate.learning_id == "l1"
        assert candidate.age_days == 45.0


class TestMetaInsight:
    """Tests for MetaInsight dataclass."""

    def test_creation(self):
        """MetaInsight creates correctly."""
        insight = MetaInsight(
            insight_type="saturation",
            description="Tool learning saturated",
            confidence=0.9,
            actionable=True,
            suggested_action="Focus elsewhere"
        )
        assert insight.insight_type == "saturation"
        assert insight.actionable is True


class TestMetaLearner:
    """Tests for MetaLearner class."""

    def test_init_default(self):
        """MetaLearner initializes with defaults."""
        learner = MetaLearner()
        assert learner.learning_events == []
        assert learner.total_learnings == 0

    def test_init_with_mock_client(self, mock_mind_client):
        """MetaLearner accepts mock Mind client."""
        learner = MetaLearner(mind_client=mock_mind_client)
        assert learner.mind == mock_mind_client


class TestRecordLearning:
    """Tests for record_learning method."""

    def test_records_learning(self):
        """Records a learning event."""
        learner = MetaLearner()

        event = learner.record_learning(
            learning_type="tool",
            source="learner",
            confidence=0.8
        )

        assert event is not None
        assert event.learning_type == "tool"
        assert learner.total_learnings == 1
        assert len(learner.learning_events) == 1

    def test_records_with_custom_id(self):
        """Records learning with custom ID."""
        learner = MetaLearner()

        event = learner.record_learning(
            learning_type="skill",
            source="skill_evolver",
            confidence=0.7,
            learning_id="custom_id"
        )

        assert event.event_id == "custom_id"

    def test_updates_type_index(self):
        """Updates events_by_type index."""
        learner = MetaLearner()

        learner.record_learning("tool", "learner", 0.8)
        learner.record_learning("tool", "learner", 0.9)
        learner.record_learning("skill", "skill_evolver", 0.7)

        assert len(learner.events_by_type["tool"]) == 2
        assert len(learner.events_by_type["skill"]) == 1


class TestMarkLearningUseful:
    """Tests for mark_learning_useful method."""

    def test_marks_as_useful(self):
        """Marks a learning as useful."""
        learner = MetaLearner()
        event = learner.record_learning("tool", "learner", 0.8, "e1")

        learner.mark_learning_useful("e1", True)

        assert event.was_useful is True
        assert event.usage_count == 1
        assert learner.learning_usefulness["tool"] == [True]

    def test_marks_as_not_useful(self):
        """Marks a learning as not useful."""
        learner = MetaLearner()
        event = learner.record_learning("tool", "learner", 0.8, "e1")

        learner.mark_learning_useful("e1", False)

        assert event.was_useful is False
        assert learner.learning_usefulness["tool"] == [False]


class TestEndSession:
    """Tests for end_session method."""

    def test_tracks_session_learnings(self):
        """Tracks learnings per session."""
        learner = MetaLearner()

        learner.record_learning("tool", "learner", 0.8)
        learner.record_learning("tool", "learner", 0.9)
        learner.end_session()

        assert learner.session_learning_counts == [2]
        assert learner.current_session_learnings == 0


class TestAnalyzeLearningTrends:
    """Tests for analyze_learning_trends method."""

    def test_returns_empty_with_few_samples(self):
        """Returns empty when not enough samples."""
        learner = MetaLearner()
        learner.record_learning("tool", "learner", 0.8)
        learner.record_learning("tool", "learner", 0.9)

        trends = learner.analyze_learning_trends()

        assert "tool" not in trends  # Need >= 5 samples

    def test_analyzes_trends_with_enough_samples(self):
        """Analyzes trends with sufficient samples."""
        learner = MetaLearner()

        for i in range(10):
            learner.record_learning("tool", "learner", 0.7 + i * 0.02)

        trends = learner.analyze_learning_trends()

        assert "tool" in trends
        assert trends["tool"].sample_count == 10
        assert trends["tool"].avg_confidence > 0.7

    def test_detects_saturation(self):
        """Detects saturated learning types."""
        learner = MetaLearner()

        # Add consistent high-confidence learnings
        for _ in range(10):
            learner.record_learning("tool", "learner", 0.96)

        trends = learner.analyze_learning_trends()

        assert trends["tool"].is_saturated is True


class TestCalculateTrend:
    """Tests for _calculate_trend method."""

    def test_positive_trend(self):
        """Detects positive trend."""
        learner = MetaLearner()

        values = [0.5, 0.6, 0.7, 0.8, 0.9]
        trend = learner._calculate_trend(values)

        assert trend > 0

    def test_negative_trend(self):
        """Detects negative trend."""
        learner = MetaLearner()

        values = [0.9, 0.8, 0.7, 0.6, 0.5]
        trend = learner._calculate_trend(values)

        assert trend < 0

    def test_flat_trend(self):
        """Detects flat trend."""
        learner = MetaLearner()

        values = [0.7, 0.7, 0.7, 0.7, 0.7]
        trend = learner._calculate_trend(values)

        assert abs(trend) < 0.01

    def test_single_value(self):
        """Handles single value."""
        learner = MetaLearner()

        trend = learner._calculate_trend([0.5])

        assert trend == 0.0


class TestIdentifyPruneCandidates:
    """Tests for identify_prune_candidates method."""

    def test_identifies_old_low_confidence(self):
        """Identifies old low-confidence learnings."""
        learner = MetaLearner()

        # Add old low-confidence learning
        old_time = datetime.now().timestamp() - 40 * 24 * 3600  # 40 days ago
        event = LearningEvent(
            event_id="old1",
            timestamp=old_time,
            learning_type="tool",
            source="learner",
            confidence=0.2
        )
        learner.learning_events.append(event)

        candidates = learner.identify_prune_candidates()

        assert len(candidates) >= 1
        assert any(c.learning_id == "old1" for c in candidates)

    def test_identifies_never_used(self):
        """Identifies never-used learnings."""
        learner = MetaLearner()

        # Add old never-used learning
        old_time = datetime.now().timestamp() - 20 * 24 * 3600  # 20 days ago
        event = LearningEvent(
            event_id="unused1",
            timestamp=old_time,
            learning_type="tool",
            source="learner",
            confidence=0.8,
            usage_count=0
        )
        learner.learning_events.append(event)

        candidates = learner.identify_prune_candidates()

        assert len(candidates) >= 1
        assert any(c.learning_id == "unused1" for c in candidates)


class TestGenerateMetaInsights:
    """Tests for generate_meta_insights method."""

    def test_generates_saturation_insight(self):
        """Generates saturation insights."""
        learner = MetaLearner()

        # Add saturated learnings
        for _ in range(10):
            learner.record_learning("tool", "learner", 0.96)

        insights = learner.generate_meta_insights()

        saturation_insights = [i for i in insights if i.insight_type == "saturation"]
        assert len(saturation_insights) >= 1

    def test_generates_maintenance_insight(self):
        """Generates maintenance insight for prune candidates."""
        learner = MetaLearner()

        # Add many old low-confidence learnings
        old_time = datetime.now().timestamp() - 40 * 24 * 3600
        for i in range(15):
            event = LearningEvent(
                event_id=f"old{i}",
                timestamp=old_time,
                learning_type="tool",
                source="learner",
                confidence=0.2
            )
            learner.learning_events.append(event)

        insights = learner.generate_meta_insights()

        maintenance_insights = [i for i in insights if i.insight_type == "maintenance"]
        assert len(maintenance_insights) >= 1


class TestGetLearningEffectiveness:
    """Tests for get_learning_effectiveness method."""

    def test_returns_default_without_data(self):
        """Returns default when no data."""
        learner = MetaLearner()

        effectiveness = learner.get_learning_effectiveness("unknown")

        assert effectiveness == 0.5

    def test_calculates_effectiveness(self):
        """Calculates effectiveness from usefulness data."""
        learner = MetaLearner()
        learner.learning_usefulness["tool"] = [True, True, False, True]

        effectiveness = learner.get_learning_effectiveness("tool")

        assert effectiveness == 0.75


class TestShouldLearn:
    """Tests for should_learn method."""

    def test_accepts_high_confidence(self):
        """Accepts high confidence learnings."""
        learner = MetaLearner()

        result = learner.should_learn("tool", 0.9)

        assert result is True

    def test_rejects_low_confidence(self):
        """Rejects low confidence learnings."""
        learner = MetaLearner()

        result = learner.should_learn("tool", 0.3)

        assert result is False


class TestCalibrateConfidence:
    """Tests for calibrate_confidence method."""

    def test_calibrates_based_on_effectiveness(self):
        """Calibrates confidence based on historical effectiveness."""
        learner = MetaLearner()
        learner.learning_usefulness["tool"] = [True, False]  # 50% effective

        calibrated = learner.calibrate_confidence("tool", 0.8)

        assert calibrated < 0.8  # Should be discounted


class TestPruneLearnings:
    """Tests for prune_learnings method."""

    def test_prunes_candidates(self):
        """Prunes identified candidates."""
        learner = MetaLearner()

        # Add learnings
        for i in range(5):
            learner.record_learning("tool", "learner", 0.8, f"e{i}")

        # Create prune candidates
        candidates = [
            PruneCandidate(learning_id="e0", learning_type="tool", reason="test", confidence=0.2, age_days=40),
            PruneCandidate(learning_id="e1", learning_type="tool", reason="test", confidence=0.2, age_days=40)
        ]

        pruned = learner.prune_learnings(candidates)

        assert pruned == 2
        assert learner.pruned_count == 2
        assert len(learner.learning_events) == 3


class TestGetMetaStats:
    """Tests for get_meta_stats method."""

    def test_returns_stats(self):
        """Returns meta statistics."""
        learner = MetaLearner()
        learner.record_learning("tool", "learner", 0.8)
        learner.record_learning("skill", "skill_evolver", 0.7)

        stats = learner.get_meta_stats()

        assert stats["total_learnings"] == 2
        assert stats["active_learnings"] == 2
        assert stats["learning_types"] == 2
