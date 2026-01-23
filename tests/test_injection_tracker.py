"""
Unit tests for lib/injection_tracker.py

Tests the feedback loop that tracks whether injected suggestions were followed.
"""

import pytest
import time
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.injection_tracker import (
    InjectionTracker,
    TrackedInjection,
    InjectionOutcome,
    FeedbackStats
)
from lib.queue import SparkEvent, EventType


# ==================== TrackedInjection Tests ====================

class TestTrackedInjection:
    """Tests for TrackedInjection dataclass."""

    def test_creation_with_required_fields(self):
        """TrackedInjection creates with required fields."""
        injection = TrackedInjection(
            tracking_id="t1",
            learning_id="l1",
            session_id="s1",
            injection_type="tool_recommendation",
            injected_at=1000.0,
            content_summary="Use Grep for search",
            trigger_conditions={"task": "search"}
        )
        assert injection.tracking_id == "t1"
        assert injection.learning_id == "l1"
        assert injection.session_id == "s1"
        assert injection.outcome == InjectionOutcome.PENDING

    def test_age_seconds_calculation(self):
        """age_seconds calculates correctly."""
        injection = TrackedInjection(
            tracking_id="t1",
            learning_id="l1",
            session_id="s1",
            injection_type="test",
            injected_at=time.time() - 100,
            content_summary="test",
            trigger_conditions={}
        )
        assert 99 < injection.age_seconds < 102

    def test_is_stale_fresh(self):
        """Fresh injection is not stale."""
        injection = TrackedInjection(
            tracking_id="t1",
            learning_id="l1",
            session_id="s1",
            injection_type="test",
            injected_at=time.time(),
            content_summary="test",
            trigger_conditions={}
        )
        assert injection.is_stale is False

    def test_is_stale_old(self):
        """Old injection is stale (> 1 hour)."""
        injection = TrackedInjection(
            tracking_id="t1",
            learning_id="l1",
            session_id="s1",
            injection_type="test",
            injected_at=time.time() - 7200,  # 2 hours ago
            content_summary="test",
            trigger_conditions={}
        )
        assert injection.is_stale is True

    def test_default_outcome_is_pending(self):
        """Default outcome is PENDING."""
        injection = TrackedInjection(
            tracking_id="t1",
            learning_id="l1",
            session_id="s1",
            injection_type="test",
            injected_at=1000.0,
            content_summary="test",
            trigger_conditions={}
        )
        assert injection.outcome == InjectionOutcome.PENDING

    def test_default_confidence_delta_is_zero(self):
        """Default confidence_delta is 0."""
        injection = TrackedInjection(
            tracking_id="t1",
            learning_id="l1",
            session_id="s1",
            injection_type="test",
            injected_at=1000.0,
            content_summary="test",
            trigger_conditions={}
        )
        assert injection.confidence_delta == 0.0


# ==================== FeedbackStats Tests ====================

class TestFeedbackStats:
    """Tests for FeedbackStats dataclass."""

    def test_default_values(self):
        """FeedbackStats has correct defaults."""
        stats = FeedbackStats()
        assert stats.total_injections == 0
        assert stats.outcomes_determined == 0
        assert stats.followed_count == 0
        assert stats.ignored_count == 0
        assert stats.contradicted_count == 0
        assert stats.expired_count == 0
        assert stats.avg_determination_time_sec == 0.0
        assert stats.follow_rate == 0.0


# ==================== InjectionTracker Init Tests ====================

class TestInjectionTrackerInit:
    """Tests for InjectionTracker initialization."""

    def test_init_default(self):
        """InjectionTracker initializes with defaults."""
        tracker = InjectionTracker()
        assert tracker.active_injections == {}
        assert tracker.completed_injections == []
        assert tracker.stats.total_injections == 0
        assert tracker.mind is None

    def test_init_with_mind_client(self):
        """InjectionTracker accepts Mind client."""
        mock_mind = MagicMock()
        tracker = InjectionTracker(mind_client=mock_mind)
        assert tracker.mind == mock_mind


# ==================== tag_injection Tests ====================

class TestTagInjection:
    """Tests for tag_injection method."""

    def test_tags_injection_returns_id(self):
        """tag_injection returns tracking ID."""
        tracker = InjectionTracker()

        tracking_id = tracker.tag_injection(
            learning_id="learn1",
            session_id="sess1",
            injection_type="tool_recommendation",
            content_summary="Use Grep",
            trigger_conditions={"task": "search"}
        )

        assert tracking_id is not None
        assert tracking_id.startswith("inj_")
        assert tracking_id in tracker.active_injections

    def test_tags_injection_updates_stats(self):
        """tag_injection updates total count."""
        tracker = InjectionTracker()

        tracker.tag_injection(
            learning_id="learn1",
            session_id="sess1",
            injection_type="tool_recommendation",
            content_summary="Use Grep",
            trigger_conditions={}
        )

        assert tracker.stats.total_injections == 1

    def test_tags_multiple_injections(self):
        """Can tag multiple injections."""
        tracker = InjectionTracker()

        ids = []
        for i in range(5):
            tid = tracker.tag_injection(
                learning_id=f"learn{i}",
                session_id="sess1",
                injection_type="tool_recommendation",
                content_summary=f"Suggestion {i}",
                trigger_conditions={}
            )
            ids.append(tid)

        assert len(set(ids)) == 5  # All unique
        assert len(tracker.active_injections) == 5
        assert tracker.stats.total_injections == 5

    def test_respects_max_active_limit(self):
        """Respects MAX_ACTIVE_INJECTIONS limit."""
        tracker = InjectionTracker()
        tracker.MAX_ACTIVE_INJECTIONS = 3

        for i in range(5):
            tracker.tag_injection(
                learning_id=f"learn{i}",
                session_id="sess1",
                injection_type="test",
                content_summary=f"Test {i}",
                trigger_conditions={}
            )

        # Should only keep most recent 3
        assert len(tracker.active_injections) <= 3
        # Oldest should have been expired
        assert tracker.stats.expired_count == 2

    def test_stores_injection_details(self):
        """tag_injection stores all injection details."""
        tracker = InjectionTracker()

        tracking_id = tracker.tag_injection(
            learning_id="learn1",
            session_id="sess1",
            injection_type="error_warning",
            content_summary="Avoid timeout errors",
            trigger_conditions={"warned_error": "timeout"}
        )

        injection = tracker.active_injections[tracking_id]
        assert injection.learning_id == "learn1"
        assert injection.session_id == "sess1"
        assert injection.injection_type == "error_warning"
        assert injection.content_summary == "Avoid timeout errors"
        assert injection.trigger_conditions == {"warned_error": "timeout"}


# ==================== observe_event Tests ====================

class TestObserveEvent:
    """Tests for observe_event method."""

    def test_returns_none_no_active_injections(self):
        """Returns None when no active injections."""
        tracker = InjectionTracker()

        event = SparkEvent(
            event_type=EventType.POST_TOOL,
            timestamp=1.0,
            session_id="sess1",
            data={},
            tool_name="Read"
        )

        result = tracker.observe_event(event)
        assert result is None

    def test_returns_none_different_session(self):
        """Returns None when event is from different session."""
        tracker = InjectionTracker()

        tracker.tag_injection(
            learning_id="learn1",
            session_id="sess1",
            injection_type="tool_recommendation",
            content_summary="Use Grep",
            trigger_conditions={"recommended_tool": "Grep"}
        )

        event = SparkEvent(
            event_type=EventType.POST_TOOL,
            timestamp=1.0,
            session_id="sess2",  # Different session
            data={},
            tool_name="Grep"
        )

        result = tracker.observe_event(event)
        assert result is None

    def test_detects_tool_recommendation_followed(self):
        """Detects when tool recommendation was followed."""
        tracker = InjectionTracker()

        tracking_id = tracker.tag_injection(
            learning_id="learn1",
            session_id="sess1",
            injection_type="tool_recommendation",
            content_summary="Use Grep for search",
            trigger_conditions={"recommended_tool": "Grep"}
        )

        event = SparkEvent(
            event_type=EventType.POST_TOOL,
            timestamp=1.0,
            session_id="sess1",
            data={},
            tool_name="Grep"
        )

        result = tracker.observe_event(event)

        assert result == tracking_id
        assert tracking_id not in tracker.active_injections
        assert len(tracker.completed_injections) == 1
        assert tracker.completed_injections[0].outcome == InjectionOutcome.FOLLOWED

    def test_detects_error_warning_ignored(self):
        """Detects when error warning was ignored (error occurred)."""
        tracker = InjectionTracker()

        tracking_id = tracker.tag_injection(
            learning_id="learn1",
            session_id="sess1",
            injection_type="error_warning",
            content_summary="Avoid timeout errors",
            trigger_conditions={"warned_error": "timeout"}
        )

        event = SparkEvent(
            event_type=EventType.POST_TOOL_FAILURE,
            timestamp=1.0,
            session_id="sess1",
            data={},
            tool_name="Bash",
            error="Command timeout after 60s"
        )

        result = tracker.observe_event(event)

        assert result == tracking_id
        assert tracker.completed_injections[0].outcome == InjectionOutcome.IGNORED

    def test_tracks_tool_sequence(self):
        """Tracks tool sequence for session."""
        tracker = InjectionTracker()

        tracker.tag_injection(
            learning_id="learn1",
            session_id="sess1",
            injection_type="tool_recommendation",
            content_summary="Use Edit",
            trigger_conditions={"recommended_tool": "Edit"}
        )

        # Observe several tools
        for tool in ["Read", "Grep", "Read"]:
            event = SparkEvent(
                event_type=EventType.POST_TOOL,
                timestamp=1.0,
                session_id="sess1",
                data={},
                tool_name=tool
            )
            tracker.observe_event(event)

        assert "sess1" in tracker._session_tool_sequence
        assert tracker._session_tool_sequence["sess1"] == ["Read", "Grep", "Read"]


# ==================== determine_outcome Tests ====================

class TestDetermineOutcome:
    """Tests for determine_outcome method."""

    def test_determines_followed(self):
        """Can manually determine FOLLOWED outcome."""
        tracker = InjectionTracker()

        tracking_id = tracker.tag_injection(
            learning_id="learn1",
            session_id="sess1",
            injection_type="test",
            content_summary="Test",
            trigger_conditions={}
        )

        result = tracker.determine_outcome(
            tracking_id=tracking_id,
            outcome=InjectionOutcome.FOLLOWED,
            evidence=["User used recommended tool"]
        )

        assert result is True
        assert tracking_id not in tracker.active_injections
        assert len(tracker.completed_injections) == 1
        assert tracker.completed_injections[0].outcome == InjectionOutcome.FOLLOWED
        assert tracker.stats.followed_count == 1

    def test_determines_ignored(self):
        """Can manually determine IGNORED outcome."""
        tracker = InjectionTracker()

        tracking_id = tracker.tag_injection(
            learning_id="learn1",
            session_id="sess1",
            injection_type="test",
            content_summary="Test",
            trigger_conditions={}
        )

        result = tracker.determine_outcome(
            tracking_id=tracking_id,
            outcome=InjectionOutcome.IGNORED,
            evidence=["User used different approach"]
        )

        assert result is True
        assert tracker.completed_injections[0].outcome == InjectionOutcome.IGNORED
        assert tracker.stats.ignored_count == 1

    def test_determines_contradicted(self):
        """Can manually determine CONTRADICTED outcome."""
        tracker = InjectionTracker()

        tracking_id = tracker.tag_injection(
            learning_id="learn1",
            session_id="sess1",
            injection_type="test",
            content_summary="Test",
            trigger_conditions={}
        )

        result = tracker.determine_outcome(
            tracking_id=tracking_id,
            outcome=InjectionOutcome.CONTRADICTED,
            evidence=["User did opposite"]
        )

        assert result is True
        assert tracker.completed_injections[0].outcome == InjectionOutcome.CONTRADICTED
        assert tracker.stats.contradicted_count == 1

    def test_returns_false_unknown_id(self):
        """Returns False for unknown tracking_id."""
        tracker = InjectionTracker()

        result = tracker.determine_outcome(
            tracking_id="unknown",
            outcome=InjectionOutcome.FOLLOWED,
            evidence=[]
        )

        assert result is False

    def test_sets_confidence_delta_followed(self):
        """Sets positive confidence_delta for FOLLOWED."""
        tracker = InjectionTracker()

        tracking_id = tracker.tag_injection(
            learning_id="learn1",
            session_id="sess1",
            injection_type="test",
            content_summary="Test",
            trigger_conditions={}
        )

        tracker.determine_outcome(
            tracking_id=tracking_id,
            outcome=InjectionOutcome.FOLLOWED,
            evidence=[]
        )

        injection = tracker.completed_injections[0]
        assert injection.confidence_delta == tracker.CONFIDENCE_BOOST_FOLLOWED

    def test_sets_confidence_delta_ignored(self):
        """Sets negative confidence_delta for IGNORED."""
        tracker = InjectionTracker()

        tracking_id = tracker.tag_injection(
            learning_id="learn1",
            session_id="sess1",
            injection_type="test",
            content_summary="Test",
            trigger_conditions={}
        )

        tracker.determine_outcome(
            tracking_id=tracking_id,
            outcome=InjectionOutcome.IGNORED,
            evidence=[]
        )

        injection = tracker.completed_injections[0]
        assert injection.confidence_delta == -tracker.CONFIDENCE_PENALTY_IGNORED

    def test_sets_confidence_delta_contradicted(self):
        """Sets large negative confidence_delta for CONTRADICTED."""
        tracker = InjectionTracker()

        tracking_id = tracker.tag_injection(
            learning_id="learn1",
            session_id="sess1",
            injection_type="test",
            content_summary="Test",
            trigger_conditions={}
        )

        tracker.determine_outcome(
            tracking_id=tracking_id,
            outcome=InjectionOutcome.CONTRADICTED,
            evidence=[]
        )

        injection = tracker.completed_injections[0]
        assert injection.confidence_delta == -tracker.CONFIDENCE_PENALTY_CONTRADICTED

    def test_updates_follow_rate(self):
        """Updates follow_rate stat correctly."""
        tracker = InjectionTracker()

        # 2 followed, 1 ignored = 66.67% follow rate
        for i, outcome in enumerate([InjectionOutcome.FOLLOWED, InjectionOutcome.FOLLOWED, InjectionOutcome.IGNORED]):
            tid = tracker.tag_injection(
                learning_id=f"learn{i}",
                session_id="sess1",
                injection_type="test",
                content_summary=f"Test {i}",
                trigger_conditions={}
            )
            tracker.determine_outcome(tid, outcome, [])

        assert abs(tracker.stats.follow_rate - 0.6667) < 0.01


# ==================== expire_stale_injections Tests ====================

class TestExpireStaleInjections:
    """Tests for expire_stale_injections method."""

    def test_expires_old_injections(self):
        """Expires injections older than timeout."""
        tracker = InjectionTracker()
        tracker.OUTCOME_TIMEOUT_SEC = 1  # 1 second for testing

        tracker.tag_injection(
            learning_id="learn1",
            session_id="sess1",
            injection_type="test",
            content_summary="Test",
            trigger_conditions={}
        )

        # Artificially age the injection
        for inj in tracker.active_injections.values():
            inj.injected_at = time.time() - 10

        expired = tracker.expire_stale_injections()

        assert expired == 1
        assert len(tracker.active_injections) == 0
        assert len(tracker.completed_injections) == 1
        assert tracker.completed_injections[0].outcome == InjectionOutcome.EXPIRED

    def test_keeps_fresh_injections(self):
        """Does not expire fresh injections."""
        tracker = InjectionTracker()

        tracker.tag_injection(
            learning_id="learn1",
            session_id="sess1",
            injection_type="test",
            content_summary="Test",
            trigger_conditions={}
        )

        expired = tracker.expire_stale_injections()

        assert expired == 0
        assert len(tracker.active_injections) == 1


# ==================== clear_session Tests ====================

class TestClearSession:
    """Tests for clear_session method."""

    def test_clears_session_injections(self):
        """Clears all injections for a session."""
        tracker = InjectionTracker()

        # Add injections for two sessions
        for i in range(3):
            tracker.tag_injection(
                learning_id=f"learn{i}",
                session_id="sess1",
                injection_type="test",
                content_summary=f"Test {i}",
                trigger_conditions={}
            )
        tracker.tag_injection(
            learning_id="learn_other",
            session_id="sess2",
            injection_type="test",
            content_summary="Other",
            trigger_conditions={}
        )

        cleared = tracker.clear_session("sess1")

        assert cleared == 3
        assert len(tracker.active_injections) == 1  # sess2 injection remains
        assert tracker.stats.expired_count == 3

    def test_clears_tool_sequence(self):
        """Clears tool sequence for session."""
        tracker = InjectionTracker()

        tracker.tag_injection(
            learning_id="learn1",
            session_id="sess1",
            injection_type="test",
            content_summary="Test",
            trigger_conditions={}
        )

        # Add some tool events
        event = SparkEvent(
            event_type=EventType.POST_TOOL,
            timestamp=1.0,
            session_id="sess1",
            data={},
            tool_name="Read"
        )
        tracker.observe_event(event)

        tracker.clear_session("sess1")

        assert "sess1" not in tracker._session_tool_sequence


# ==================== get_stats Tests ====================

class TestGetStats:
    """Tests for get_stats method."""

    def test_returns_stats(self):
        """Returns current stats."""
        tracker = InjectionTracker()

        tid = tracker.tag_injection(
            learning_id="learn1",
            session_id="sess1",
            injection_type="test",
            content_summary="Test",
            trigger_conditions={}
        )
        tracker.determine_outcome(tid, InjectionOutcome.FOLLOWED, [])

        stats = tracker.get_stats()

        assert stats.total_injections == 1
        assert stats.outcomes_determined == 1
        assert stats.followed_count == 1
        assert stats.follow_rate == 1.0


# ==================== update_learning_confidence Tests ====================

class TestUpdateLearningConfidence:
    """Tests for update_learning_confidence method."""

    @pytest.mark.asyncio
    async def test_returns_delta_without_mind(self):
        """Returns confidence delta even without Mind client."""
        tracker = InjectionTracker()

        tid = tracker.tag_injection(
            learning_id="learn1",
            session_id="sess1",
            injection_type="test",
            content_summary="Test",
            trigger_conditions={}
        )
        tracker.determine_outcome(tid, InjectionOutcome.FOLLOWED, [])

        delta = await tracker.update_learning_confidence(tid)

        assert delta == tracker.CONFIDENCE_BOOST_FOLLOWED

    @pytest.mark.asyncio
    async def test_stores_feedback_in_mind(self):
        """Stores feedback in Mind when available."""
        mock_mind = AsyncMock()
        mock_mind.store = AsyncMock(return_value="mem_123")
        tracker = InjectionTracker(mind_client=mock_mind)

        tid = tracker.tag_injection(
            learning_id="learn1",
            session_id="sess1",
            injection_type="test",
            content_summary="Test suggestion",
            trigger_conditions={}
        )
        tracker.determine_outcome(tid, InjectionOutcome.FOLLOWED, [])

        delta = await tracker.update_learning_confidence(tid)

        assert delta == tracker.CONFIDENCE_BOOST_FOLLOWED
        mock_mind.store.assert_called_once()

    @pytest.mark.asyncio
    async def test_returns_zero_unknown_id(self):
        """Returns 0 for unknown tracking_id."""
        tracker = InjectionTracker()

        delta = await tracker.update_learning_confidence("unknown")

        assert delta == 0.0


# ==================== get_active_for_session Tests ====================

class TestGetActiveForSession:
    """Tests for get_active_for_session method."""

    def test_returns_session_injections(self):
        """Returns only injections for specified session."""
        tracker = InjectionTracker()

        tracker.tag_injection(
            learning_id="learn1",
            session_id="sess1",
            injection_type="test",
            content_summary="Test 1",
            trigger_conditions={}
        )
        tracker.tag_injection(
            learning_id="learn2",
            session_id="sess1",
            injection_type="test",
            content_summary="Test 2",
            trigger_conditions={}
        )
        tracker.tag_injection(
            learning_id="learn3",
            session_id="sess2",
            injection_type="test",
            content_summary="Test 3",
            trigger_conditions={}
        )

        active = tracker.get_active_for_session("sess1")

        assert len(active) == 2
        assert all(inj.session_id == "sess1" for inj in active)


# ==================== get_follow_rate_for_type Tests ====================

class TestGetFollowRateForType:
    """Tests for get_follow_rate_for_type method."""

    def test_returns_rate_for_type(self):
        """Returns follow rate for specific injection type."""
        tracker = InjectionTracker()

        # 2 tool recommendations: 1 followed, 1 ignored
        tid1 = tracker.tag_injection(
            learning_id="learn1",
            session_id="sess1",
            injection_type="tool_recommendation",
            content_summary="Test 1",
            trigger_conditions={}
        )
        tracker.determine_outcome(tid1, InjectionOutcome.FOLLOWED, [])

        tid2 = tracker.tag_injection(
            learning_id="learn2",
            session_id="sess1",
            injection_type="tool_recommendation",
            content_summary="Test 2",
            trigger_conditions={}
        )
        tracker.determine_outcome(tid2, InjectionOutcome.IGNORED, [])

        # 1 error warning: followed (should not affect tool_recommendation rate)
        tid3 = tracker.tag_injection(
            learning_id="learn3",
            session_id="sess1",
            injection_type="error_warning",
            content_summary="Test 3",
            trigger_conditions={}
        )
        tracker.determine_outcome(tid3, InjectionOutcome.FOLLOWED, [])

        rate = tracker.get_follow_rate_for_type("tool_recommendation")

        assert rate == 0.5  # 1 followed out of 2

    def test_returns_zero_no_data(self):
        """Returns 0 when no data for type."""
        tracker = InjectionTracker()

        rate = tracker.get_follow_rate_for_type("nonexistent_type")

        assert rate == 0.0
