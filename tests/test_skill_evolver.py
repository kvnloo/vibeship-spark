"""
Tests for lib/skill_evolver.py
"""

import pytest
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

# Add lib to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.queue import SparkEvent, EventType
from lib.skill_evolver import (
    SkillEvolver, SkillUsage, SkillStats, SkillGap, SkillImprovement
)


class TestSkillUsage:
    """Tests for SkillUsage dataclass."""

    def test_creation(self):
        """SkillUsage creates with required fields."""
        usage = SkillUsage(
            skill_id="supabase-auth",
            task_context="authentication",
            outcome="success"
        )
        assert usage.skill_id == "supabase-auth"
        assert usage.task_context == "authentication"
        assert usage.outcome == "success"

    def test_creation_with_optional_fields(self):
        """SkillUsage accepts optional fields."""
        usage = SkillUsage(
            skill_id="api-design",
            task_context="api_design",
            outcome="failure",
            duration_ms=150.5,
            error="Missing endpoint",
            session_id="test-session"
        )
        assert usage.duration_ms == 150.5
        assert usage.error == "Missing endpoint"
        assert usage.session_id == "test-session"


class TestSkillStats:
    """Tests for SkillStats dataclass."""

    def test_success_rate_empty(self):
        """Success rate is 0 when no uses."""
        stats = SkillStats(skill_id="test")
        assert stats.success_rate == 0.0

    def test_success_rate_calculation(self):
        """Success rate calculates correctly."""
        stats = SkillStats(
            skill_id="test",
            total_uses=10,
            successes=8,
            failures=2
        )
        assert stats.success_rate == 0.8

    def test_avg_duration_empty(self):
        """Avg duration is 0 when no uses."""
        stats = SkillStats(skill_id="test")
        assert stats.avg_duration_ms == 0.0

    def test_avg_duration_calculation(self):
        """Avg duration calculates correctly."""
        stats = SkillStats(
            skill_id="test",
            total_uses=10,
            total_duration_ms=1000.0
        )
        assert stats.avg_duration_ms == 100.0

    def test_most_common_task_empty(self):
        """Most common task is None when no task types."""
        stats = SkillStats(skill_id="test")
        assert stats.most_common_task is None

    def test_most_common_task(self):
        """Most common task returns highest count."""
        stats = SkillStats(skill_id="test")
        stats.task_types = {
            "authentication": 5,
            "database": 3,
            "api_design": 2
        }
        assert stats.most_common_task == "authentication"


class TestSkillGap:
    """Tests for SkillGap dataclass."""

    def test_creation(self):
        """SkillGap creates correctly."""
        gap = SkillGap(
            task_type="authentication",
            frequency=10,
            current_success_rate=0.5,
            improvement_potential=0.4
        )
        assert gap.task_type == "authentication"
        assert gap.frequency == 10
        assert gap.improvement_potential == 0.4


class TestSkillImprovement:
    """Tests for SkillImprovement dataclass."""

    def test_creation(self):
        """SkillImprovement creates correctly."""
        improvement = SkillImprovement(
            skill_id="supabase-auth",
            improvement_type="error_handling",
            description="Add handling for missing_resource errors",
            evidence=["5 occurrences", "30% of failures"],
            confidence=0.8,
            priority=1
        )
        assert improvement.skill_id == "supabase-auth"
        assert improvement.improvement_type == "error_handling"
        assert improvement.priority == 1


class TestSkillEvolver:
    """Tests for SkillEvolver class."""

    def test_init_default(self):
        """SkillEvolver initializes with defaults."""
        evolver = SkillEvolver()
        assert evolver.skill_stats is not None
        assert evolver.usage_history == []
        assert evolver.gaps_identified == []

    def test_init_with_mock_client(self, mock_mind_client):
        """SkillEvolver accepts mock Mind client."""
        evolver = SkillEvolver(mind_client=mock_mind_client)
        assert evolver.mind == mock_mind_client


class TestTrackSkillUsage:
    """Tests for track_skill_usage method."""

    def test_tracks_success(self):
        """Tracks successful skill usage."""
        evolver = SkillEvolver()
        event = SparkEvent(
            event_type=EventType.POST_TOOL,
            timestamp=1234567890.0,
            session_id="test",
            data={},
            tool_name="Skill",
            tool_input={"skill": "supabase-auth"},
            duration_ms=100.0
        )

        usage = evolver.track_skill_usage(event)

        assert usage is not None
        assert usage.skill_id == "supabase-auth"
        assert usage.outcome == "success"
        assert evolver.skill_stats["supabase-auth"].successes == 1

    def test_tracks_failure(self):
        """Tracks failed skill usage."""
        evolver = SkillEvolver()
        event = SparkEvent(
            event_type=EventType.POST_TOOL_FAILURE,
            timestamp=1234567890.0,
            session_id="test",
            data={},
            tool_name="Skill",
            tool_input={"skill": "api-design"},
            error="Skill not found"
        )

        usage = evolver.track_skill_usage(event)

        assert usage.outcome == "failure"
        assert usage.error == "Skill not found"
        assert evolver.skill_stats["api-design"].failures == 1

    def test_updates_stats(self):
        """Multiple usages update stats correctly."""
        evolver = SkillEvolver()

        for i in range(5):
            event = SparkEvent(
                event_type=EventType.POST_TOOL,
                timestamp=1234567890.0 + i,
                session_id="test",
                data={},
                tool_name="Skill",
                tool_input={"skill": "test-skill"},
                duration_ms=100.0
            )
            evolver.track_skill_usage(event)

        stats = evolver.skill_stats["test-skill"]
        assert stats.total_uses == 5
        assert stats.successes == 5
        assert stats.total_duration_ms == 500.0


class TestInferTaskContext:
    """Tests for _infer_task_context method."""

    def test_infers_authentication(self):
        """Infers authentication task."""
        evolver = SkillEvolver()
        event = SparkEvent(
            event_type=EventType.POST_TOOL,
            timestamp=1234567890.0,
            session_id="test",
            data={},
            tool_name="Skill",
            tool_input={"skill": "supabase-auth"}
        )

        context = evolver._infer_task_context(event)
        assert context == "authentication"

    def test_infers_database(self):
        """Infers database task."""
        evolver = SkillEvolver()
        event = SparkEvent(
            event_type=EventType.POST_TOOL,
            timestamp=1234567890.0,
            session_id="test",
            data={},
            tool_name="Skill",
            tool_input={"skill": "postgres-setup"}
        )

        context = evolver._infer_task_context(event)
        assert context == "database"

    def test_infers_general(self):
        """Defaults to general for unknown skills."""
        evolver = SkillEvolver()
        event = SparkEvent(
            event_type=EventType.POST_TOOL,
            timestamp=1234567890.0,
            session_id="test",
            data={},
            tool_name="Skill",
            tool_input={"skill": "random-skill"}
        )

        context = evolver._infer_task_context(event)
        assert context == "general"


class TestCategorizeError:
    """Tests for _categorize_error method."""

    def test_missing_resource(self):
        """Categorizes missing resource errors."""
        evolver = SkillEvolver()
        assert evolver._categorize_error("File not found") == "missing_resource"
        assert evolver._categorize_error("Missing dependency") == "missing_resource"

    def test_permission(self):
        """Categorizes permission errors."""
        evolver = SkillEvolver()
        assert evolver._categorize_error("Permission denied") == "permission"
        assert evolver._categorize_error("Access forbidden") == "permission"

    def test_timeout(self):
        """Categorizes timeout errors."""
        evolver = SkillEvolver()
        assert evolver._categorize_error("Request timeout") == "timeout"

    def test_configuration(self):
        """Categorizes configuration errors."""
        evolver = SkillEvolver()
        assert evolver._categorize_error("Invalid config value") == "configuration"
        assert evolver._categorize_error("env variable not set") == "configuration"

    def test_other(self):
        """Categorizes unknown errors as other."""
        evolver = SkillEvolver()
        assert evolver._categorize_error("Something went wrong") == "other"


class TestProcessEvents:
    """Tests for process_events method."""

    @pytest.mark.asyncio
    async def test_processes_skill_events(self, mock_mind_client):
        """Processes Skill tool events."""
        evolver = SkillEvolver(mind_client=mock_mind_client)

        events = [
            SparkEvent(
                event_type=EventType.POST_TOOL,
                timestamp=1234567890.0,
                session_id="test",
                data={},
                tool_name="Skill",
                tool_input={"skill": "test-skill"}
            ),
            SparkEvent(
                event_type=EventType.POST_TOOL,
                timestamp=1234567891.0,
                session_id="test",
                data={},
                tool_name="Bash"  # Not a Skill event
            )
        ]

        usages = await evolver.process_events(events)

        assert len(usages) == 1  # Only Skill events
        assert usages[0].skill_id == "test-skill"


class TestIdentifyGaps:
    """Tests for identify_gaps method."""

    def test_identifies_low_success_task(self):
        """Identifies tasks with low success rate."""
        evolver = SkillEvolver()

        # Add outcomes for a task type
        evolver.task_outcomes["authentication"] = [True, False, False, False, False]  # 20% success

        gaps = evolver.identify_gaps(min_frequency=3)

        assert len(gaps) == 1
        assert gaps[0].task_type == "authentication"
        assert gaps[0].current_success_rate == 0.2
        assert gaps[0].improvement_potential == 0.7  # 0.9 - 0.2

    def test_ignores_high_success_task(self):
        """Ignores tasks with high success rate."""
        evolver = SkillEvolver()

        evolver.task_outcomes["database"] = [True, True, True, True, False]  # 80% success

        gaps = evolver.identify_gaps(min_frequency=3)

        assert len(gaps) == 0  # No gap for 80% success

    def test_ignores_low_frequency_task(self):
        """Ignores tasks with too few samples."""
        evolver = SkillEvolver()

        evolver.task_outcomes["rare_task"] = [False, False]  # Only 2 samples

        gaps = evolver.identify_gaps(min_frequency=3)

        assert len(gaps) == 0


class TestProposeImprovements:
    """Tests for propose_improvements method."""

    def test_proposes_error_handling(self):
        """Proposes error handling improvements."""
        evolver = SkillEvolver()

        # Add stats with recurring errors
        evolver.skill_stats["test-skill"] = SkillStats(
            skill_id="test-skill",
            total_uses=10,
            successes=5,
            failures=5
        )
        evolver.skill_stats["test-skill"].error_types["missing_resource"] = 4

        improvements = evolver.propose_improvements(min_samples=5)

        error_improvements = [i for i in improvements if i.improvement_type == "error_handling"]
        assert len(error_improvements) >= 1
        assert "missing_resource" in error_improvements[0].description

    def test_proposes_clarity_for_low_success(self):
        """Proposes clarity improvement for low success rate."""
        evolver = SkillEvolver()

        evolver.skill_stats["confusing-skill"] = SkillStats(
            skill_id="confusing-skill",
            total_uses=15,
            successes=5,
            failures=10
        )
        evolver.skill_stats["confusing-skill"].task_types["general"] = 15

        improvements = evolver.propose_improvements(min_samples=5)

        clarity_improvements = [i for i in improvements if i.improvement_type == "clarity"]
        assert len(clarity_improvements) >= 1

    def test_skips_low_sample_skills(self):
        """Skips skills with too few samples."""
        evolver = SkillEvolver()

        evolver.skill_stats["new-skill"] = SkillStats(
            skill_id="new-skill",
            total_uses=3,
            successes=1,
            failures=2
        )

        improvements = evolver.propose_improvements(min_samples=5)

        assert all(i.skill_id != "new-skill" for i in improvements)


class TestGetSkillRanking:
    """Tests for get_skill_ranking method."""

    def test_ranks_by_success_rate(self):
        """Ranks skills by success rate."""
        evolver = SkillEvolver()

        evolver.skill_stats["skill-a"] = SkillStats(
            skill_id="skill-a", total_uses=10, successes=9, failures=1
        )
        evolver.skill_stats["skill-b"] = SkillStats(
            skill_id="skill-b", total_uses=10, successes=7, failures=3
        )
        evolver.skill_stats["skill-c"] = SkillStats(
            skill_id="skill-c", total_uses=10, successes=5, failures=5
        )

        rankings = evolver.get_skill_ranking()

        assert rankings[0][0] == "skill-a"
        assert rankings[1][0] == "skill-b"
        assert rankings[2][0] == "skill-c"

    def test_excludes_low_sample_skills(self):
        """Excludes skills with < 3 uses."""
        evolver = SkillEvolver()

        evolver.skill_stats["good-skill"] = SkillStats(
            skill_id="good-skill", total_uses=10, successes=10, failures=0
        )
        evolver.skill_stats["new-skill"] = SkillStats(
            skill_id="new-skill", total_uses=2, successes=2, failures=0
        )

        rankings = evolver.get_skill_ranking()

        assert len(rankings) == 1
        assert rankings[0][0] == "good-skill"


class TestGetRecommendationsForTask:
    """Tests for get_recommendations_for_task method."""

    def test_returns_relevant_skills(self):
        """Returns skills that work for the task type."""
        evolver = SkillEvolver()

        evolver.skill_stats["auth-skill"] = SkillStats(
            skill_id="auth-skill",
            total_uses=10,
            successes=9,
            failures=1
        )
        evolver.skill_stats["auth-skill"].task_types["authentication"] = 8

        recommendations = evolver.get_recommendations_for_task("authentication")

        assert len(recommendations) >= 1
        assert "auth-skill" in recommendations[0]

    def test_excludes_low_success_skills(self):
        """Excludes skills with low success rate."""
        evolver = SkillEvolver()

        evolver.skill_stats["bad-skill"] = SkillStats(
            skill_id="bad-skill",
            total_uses=10,
            successes=3,
            failures=7
        )
        evolver.skill_stats["bad-skill"].task_types["authentication"] = 5

        recommendations = evolver.get_recommendations_for_task("authentication")

        assert len(recommendations) == 0


class TestClearSessionData:
    """Tests for clear_session_data method."""

    def test_clears_usage_history(self):
        """Clears usage history but keeps stats."""
        evolver = SkillEvolver()
        evolver.usage_history = [MagicMock()] * 10
        evolver.skill_stats["test"] = SkillStats(skill_id="test", total_uses=5)

        evolver.clear_session_data()

        assert evolver.usage_history == []
        # Stats should be preserved
        assert "test" in evolver.skill_stats
