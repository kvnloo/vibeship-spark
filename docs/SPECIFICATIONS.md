# Spark Comprehensive Specifications

This document contains complete specifications for all Spark milestones with detailed implementation requirements, data structures, method signatures, and comprehensive unit test plans.

---

## Table of Contents

1. [M5: Feedback Loop Completion](#m5-feedback-loop-completion)
2. [M6: Cross-Project Intelligence](#m6-cross-project-intelligence)
3. [M7: Advanced Prompt Evolution](#m7-advanced-prompt-evolution)
4. [M8: MCP Server Enhancement](#m8-mcp-server-enhancement)
5. [M10: Observability & Debugging](#m10-observability--debugging)

---

# M5: Feedback Loop Completion

## Overview
Track when injected context actually helped Claude, creating a true feedback loop that improves confidence scores over time.

## Components

### 5.1 InjectionTracker (`lib/injection_tracker.py`)

#### Data Structures

```python
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from enum import Enum
import time
import uuid

class InjectionOutcome(Enum):
    """Possible outcomes of an injection."""
    PENDING = "pending"           # Not yet determined
    FOLLOWED = "followed"         # User followed the suggestion
    IGNORED = "ignored"           # User ignored the suggestion
    CONTRADICTED = "contradicted" # User did opposite
    EXPIRED = "expired"           # Session ended without determination


@dataclass
class TrackedInjection:
    """A tracked injection with its outcome."""
    tracking_id: str
    learning_id: str
    session_id: str
    injection_type: str           # "tool_recommendation", "error_warning", "skill_suggestion"
    injected_at: float
    content_summary: str          # Brief description of what was injected
    trigger_conditions: Dict[str, Any]  # What triggered this injection
    outcome: InjectionOutcome = InjectionOutcome.PENDING
    outcome_determined_at: Optional[float] = None
    outcome_evidence: List[str] = field(default_factory=list)  # Events that determined outcome
    confidence_delta: float = 0.0  # How much to adjust learning confidence

    @property
    def age_seconds(self) -> float:
        """How long since injection."""
        return time.time() - self.injected_at

    @property
    def is_stale(self) -> bool:
        """Whether injection is too old to track."""
        return self.age_seconds > 3600  # 1 hour


@dataclass
class FeedbackStats:
    """Statistics about feedback loop effectiveness."""
    total_injections: int = 0
    outcomes_determined: int = 0
    followed_count: int = 0
    ignored_count: int = 0
    contradicted_count: int = 0
    expired_count: int = 0
    avg_determination_time_sec: float = 0.0
    follow_rate: float = 0.0      # followed / (followed + ignored + contradicted)
```

#### Class Definition

```python
class InjectionTracker:
    """
    Tracks injected suggestions and determines if they were helpful.

    Lifecycle:
    1. tag_injection() - Called when context is injected into Claude
    2. observe_event() - Called for each subsequent event in session
    3. determine_outcome() - Called when enough evidence gathered
    4. update_learning_confidence() - Feeds back to source learning
    """

    # Configuration
    MAX_ACTIVE_INJECTIONS = 100       # Per session
    OUTCOME_TIMEOUT_SEC = 1800        # 30 minutes
    MIN_EVIDENCE_EVENTS = 3           # Events needed to determine outcome
    CONFIDENCE_BOOST_FOLLOWED = 0.05  # Boost when followed
    CONFIDENCE_PENALTY_IGNORED = 0.02 # Penalty when ignored
    CONFIDENCE_PENALTY_CONTRADICTED = 0.1  # Penalty when contradicted

    def __init__(self, mind_client: Optional[MindClient] = None):
        """
        Initialize tracker.

        Args:
            mind_client: Optional Mind client for persisting feedback
        """
        self.mind = mind_client
        self.active_injections: Dict[str, TrackedInjection] = {}
        self.completed_injections: List[TrackedInjection] = []
        self.stats = FeedbackStats()
        self._session_tool_sequence: List[str] = []

    def tag_injection(
        self,
        learning_id: str,
        session_id: str,
        injection_type: str,
        content_summary: str,
        trigger_conditions: Dict[str, Any]
    ) -> str:
        """
        Tag a learning injection for tracking.

        Args:
            learning_id: ID of the source learning
            session_id: Current session ID
            injection_type: Type of injection (tool_recommendation, etc.)
            content_summary: Brief description of injected content
            trigger_conditions: What triggered this injection

        Returns:
            tracking_id: Unique ID for this tracked injection
        """
        pass

    def observe_event(self, event: SparkEvent) -> Optional[str]:
        """
        Observe an event and check if it relates to any active injection.

        Args:
            event: The observed event

        Returns:
            tracking_id if event determined an outcome, None otherwise
        """
        pass

    def determine_outcome(
        self,
        tracking_id: str,
        outcome: InjectionOutcome,
        evidence: List[str]
    ) -> bool:
        """
        Manually determine the outcome of an injection.

        Args:
            tracking_id: ID of the tracked injection
            outcome: The determined outcome
            evidence: List of event descriptions supporting this outcome

        Returns:
            True if outcome was recorded, False if tracking_id not found
        """
        pass

    def _check_tool_recommendation(
        self,
        injection: TrackedInjection,
        event: SparkEvent
    ) -> Optional[InjectionOutcome]:
        """
        Check if a tool recommendation was followed.

        Logic:
        - If recommended tool is used next -> FOLLOWED
        - If different tool used for same task -> IGNORED
        - If opposite of recommendation done -> CONTRADICTED
        """
        pass

    def _check_error_warning(
        self,
        injection: TrackedInjection,
        event: SparkEvent
    ) -> Optional[InjectionOutcome]:
        """
        Check if an error warning was heeded.

        Logic:
        - If warned error was avoided -> FOLLOWED
        - If warned error still occurred -> IGNORED
        """
        pass

    async def update_learning_confidence(self, tracking_id: str) -> float:
        """
        Update the source learning's confidence based on outcome.

        Args:
            tracking_id: ID of the completed tracked injection

        Returns:
            The confidence delta applied
        """
        pass

    def expire_stale_injections(self) -> int:
        """
        Mark old injections as expired.

        Returns:
            Number of injections expired
        """
        pass

    def get_stats(self) -> FeedbackStats:
        """Get current feedback statistics."""
        pass

    def clear_session(self, session_id: str) -> int:
        """
        Clear all injections for a session.

        Args:
            session_id: Session to clear

        Returns:
            Number of injections cleared
        """
        pass

    async def persist_completed(self) -> int:
        """
        Persist completed injections to Mind.

        Returns:
            Number persisted
        """
        pass
```

#### Unit Tests (`tests/test_injection_tracker.py`)

```python
"""
Unit tests for lib/injection_tracker.py

Test Coverage Requirements:
- 100% of public methods
- All outcome determination paths
- Edge cases and error handling
- Async operations
"""

import pytest
from lib.injection_tracker import (
    InjectionTracker, TrackedInjection, InjectionOutcome, FeedbackStats
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
        assert injection.outcome == InjectionOutcome.PENDING

    def test_age_seconds_calculation(self):
        """age_seconds calculates correctly."""
        import time
        injection = TrackedInjection(
            tracking_id="t1",
            learning_id="l1",
            session_id="s1",
            injection_type="test",
            injected_at=time.time() - 100,
            content_summary="test",
            trigger_conditions={}
        )
        assert 99 < injection.age_seconds < 101

    def test_is_stale_fresh(self):
        """Fresh injection is not stale."""
        import time
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
        """Old injection is stale."""
        import time
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


# ==================== InjectionTracker Tests ====================

class TestInjectionTrackerInit:
    """Tests for InjectionTracker initialization."""

    def test_init_default(self):
        """InjectionTracker initializes with defaults."""
        tracker = InjectionTracker()
        assert tracker.active_injections == {}
        assert tracker.completed_injections == []
        assert tracker.stats.total_injections == 0

    def test_init_with_mind_client(self, mock_mind_client):
        """InjectionTracker accepts Mind client."""
        tracker = InjectionTracker(mind_client=mock_mind_client)
        assert tracker.mind == mock_mind_client


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


class TestObserveEvent:
    """Tests for observe_event method."""

    def test_returns_none_no_match(self):
        """Returns None when event doesn't match any injection."""
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

    def test_detects_tool_recommendation_followed(self):
        """Detects when tool recommendation was followed."""
        tracker = InjectionTracker()

        # Tag a Grep recommendation
        tracking_id = tracker.tag_injection(
            learning_id="learn1",
            session_id="sess1",
            injection_type="tool_recommendation",
            content_summary="Use Grep for search",
            trigger_conditions={"recommended_tool": "Grep", "task": "search"}
        )

        # Observe Grep being used
        event = SparkEvent(
            event_type=EventType.POST_TOOL,
            timestamp=1.0,
            session_id="sess1",
            data={},
            tool_name="Grep"
        )

        result = tracker.observe_event(event)

        # May need multiple events to determine
        assert result is None or result == tracking_id

    def test_detects_error_warning_heeded(self):
        """Detects when error warning was heeded."""
        tracker = InjectionTracker()

        # Tag a warning about timeout
        tracking_id = tracker.tag_injection(
            learning_id="learn1",
            session_id="sess1",
            injection_type="error_warning",
            content_summary="Avoid long-running commands",
            trigger_conditions={"warned_error": "timeout", "warned_tool": "Bash"}
        )

        # Observe session ends without timeout error
        # (This would be checked at session end)

        assert tracking_id in tracker.active_injections


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
        assert tracker.active_injections[tracking_id].outcome == InjectionOutcome.FOLLOWED

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
        assert tracker.stats.ignored_count == 1

    def test_returns_false_unknown_id(self):
        """Returns False for unknown tracking ID."""
        tracker = InjectionTracker()

        result = tracker.determine_outcome(
            tracking_id="nonexistent",
            outcome=InjectionOutcome.FOLLOWED,
            evidence=[]
        )

        assert result is False

    def test_moves_to_completed(self):
        """Determined injection moves to completed list."""
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
            evidence=["Evidence"]
        )

        # Should be in completed
        completed_ids = [c.tracking_id for c in tracker.completed_injections]
        assert tracking_id in completed_ids


class TestUpdateLearningConfidence:
    """Tests for update_learning_confidence method."""

    @pytest.mark.asyncio
    async def test_boosts_confidence_when_followed(self, mock_mind_client):
        """Boosts confidence when suggestion was followed."""
        tracker = InjectionTracker(mind_client=mock_mind_client)

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
            evidence=["Evidence"]
        )

        delta = await tracker.update_learning_confidence(tracking_id)

        assert delta > 0  # Positive boost

    @pytest.mark.asyncio
    async def test_penalizes_confidence_when_ignored(self, mock_mind_client):
        """Penalizes confidence when suggestion was ignored."""
        tracker = InjectionTracker(mind_client=mock_mind_client)

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
            evidence=["Evidence"]
        )

        delta = await tracker.update_learning_confidence(tracking_id)

        assert delta < 0  # Negative penalty


class TestExpireStaleInjections:
    """Tests for expire_stale_injections method."""

    def test_expires_old_injections(self):
        """Expires injections older than timeout."""
        import time
        tracker = InjectionTracker()
        tracker.OUTCOME_TIMEOUT_SEC = 60  # 1 minute for testing

        # Add old injection
        old_id = tracker.tag_injection(
            learning_id="learn1",
            session_id="sess1",
            injection_type="test",
            content_summary="Old",
            trigger_conditions={}
        )
        # Manually make it old
        tracker.active_injections[old_id].injected_at = time.time() - 120

        # Add fresh injection
        fresh_id = tracker.tag_injection(
            learning_id="learn2",
            session_id="sess1",
            injection_type="test",
            content_summary="Fresh",
            trigger_conditions={}
        )

        expired_count = tracker.expire_stale_injections()

        assert expired_count == 1
        assert tracker.active_injections[old_id].outcome == InjectionOutcome.EXPIRED


class TestGetStats:
    """Tests for get_stats method."""

    def test_returns_accurate_stats(self):
        """Returns accurate statistics."""
        tracker = InjectionTracker()

        # Create some injections with different outcomes
        for i in range(3):
            tid = tracker.tag_injection(
                learning_id=f"learn{i}",
                session_id="sess1",
                injection_type="test",
                content_summary=f"Test {i}",
                trigger_conditions={}
            )
            outcome = [InjectionOutcome.FOLLOWED, InjectionOutcome.IGNORED, InjectionOutcome.FOLLOWED][i]
            tracker.determine_outcome(tid, outcome, ["evidence"])

        stats = tracker.get_stats()

        assert stats.total_injections == 3
        assert stats.outcomes_determined == 3
        assert stats.followed_count == 2
        assert stats.ignored_count == 1

    def test_calculates_follow_rate(self):
        """Correctly calculates follow rate."""
        tracker = InjectionTracker()

        for i in range(10):
            tid = tracker.tag_injection(
                learning_id=f"learn{i}",
                session_id="sess1",
                injection_type="test",
                content_summary=f"Test {i}",
                trigger_conditions={}
            )
            # 7 followed, 3 ignored
            outcome = InjectionOutcome.FOLLOWED if i < 7 else InjectionOutcome.IGNORED
            tracker.determine_outcome(tid, outcome, ["evidence"])

        stats = tracker.get_stats()

        assert stats.follow_rate == 0.7


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
        for i in range(2):
            tracker.tag_injection(
                learning_id=f"learn{i+10}",
                session_id="sess2",
                injection_type="test",
                content_summary=f"Test {i}",
                trigger_conditions={}
            )

        cleared = tracker.clear_session("sess1")

        assert cleared == 3
        # Only sess2 injections remain
        remaining_sessions = {inj.session_id for inj in tracker.active_injections.values()}
        assert remaining_sessions == {"sess2"}


# ==================== Integration Tests ====================

class TestInjectionTrackerIntegration:
    """Integration tests for complete workflows."""

    @pytest.mark.asyncio
    async def test_full_tracking_lifecycle(self, mock_mind_client):
        """Tests complete injection tracking lifecycle."""
        tracker = InjectionTracker(mind_client=mock_mind_client)

        # 1. Tag injection
        tracking_id = tracker.tag_injection(
            learning_id="tool_grep_effective",
            session_id="sess1",
            injection_type="tool_recommendation",
            content_summary="Use Grep for code search",
            trigger_conditions={"recommended_tool": "Grep", "task_type": "search"}
        )

        # 2. Simulate events
        events = [
            SparkEvent(EventType.POST_TOOL, 1.0, "sess1", {}, tool_name="Glob"),
            SparkEvent(EventType.POST_TOOL, 2.0, "sess1", {}, tool_name="Grep"),
            SparkEvent(EventType.POST_TOOL, 3.0, "sess1", {}, tool_name="Read"),
        ]

        for event in events:
            tracker.observe_event(event)

        # 3. Manually determine outcome (or let automatic detection work)
        tracker.determine_outcome(
            tracking_id,
            InjectionOutcome.FOLLOWED,
            ["Grep used after recommendation"]
        )

        # 4. Update confidence
        delta = await tracker.update_learning_confidence(tracking_id)

        # 5. Verify
        assert delta > 0
        assert tracker.stats.followed_count == 1
```

---

### 5.2 PatternExperiment (`lib/experiment.py`)

#### Data Structures

```python
from dataclasses import dataclass, field
from typing import List, Dict, Optional
from enum import Enum
import random
import math


class ExperimentStatus(Enum):
    """Status of an A/B experiment."""
    DRAFT = "draft"           # Not yet started
    RUNNING = "running"       # Actively collecting data
    CONCLUDED = "concluded"   # Reached significance
    CANCELLED = "cancelled"   # Manually stopped


@dataclass
class ExperimentArm:
    """One arm of an A/B experiment."""
    arm_id: str
    pattern_id: str
    sessions_assigned: List[str] = field(default_factory=list)
    success_count: int = 0
    failure_count: int = 0

    @property
    def total_trials(self) -> int:
        return self.success_count + self.failure_count

    @property
    def success_rate(self) -> float:
        if self.total_trials == 0:
            return 0.0
        return self.success_count / self.total_trials


@dataclass
class PatternExperiment:
    """An A/B experiment comparing two patterns."""
    experiment_id: str
    name: str
    description: str
    control: ExperimentArm        # Existing pattern (A)
    treatment: ExperimentArm      # New pattern (B)
    status: ExperimentStatus = ExperimentStatus.DRAFT
    created_at: float = 0.0
    started_at: Optional[float] = None
    concluded_at: Optional[float] = None
    min_samples_per_arm: int = 30
    confidence_level: float = 0.95
    winner: Optional[str] = None  # "control", "treatment", or "tie"

    @property
    def total_sessions(self) -> int:
        return len(self.control.sessions_assigned) + len(self.treatment.sessions_assigned)

    @property
    def is_ready_for_analysis(self) -> bool:
        return (self.control.total_trials >= self.min_samples_per_arm and
                self.treatment.total_trials >= self.min_samples_per_arm)


@dataclass
class ExperimentResult:
    """Result of statistical analysis."""
    experiment_id: str
    control_success_rate: float
    treatment_success_rate: float
    relative_improvement: float   # (treatment - control) / control
    p_value: float
    is_significant: bool
    recommended_winner: str       # "control", "treatment", "inconclusive"
    confidence_interval: tuple    # (lower, upper) for difference
```

#### Class Definition

```python
class ExperimentManager:
    """
    Manages A/B experiments for pattern comparison.

    Workflow:
    1. create_experiment() - Define control and treatment patterns
    2. start_experiment() - Begin collecting data
    3. assign_session() - Assign each session to an arm
    4. record_outcome() - Record success/failure for session
    5. analyze() - Check for statistical significance
    6. conclude() - Declare winner and update patterns
    """

    def __init__(self, mind_client: Optional[MindClient] = None):
        self.mind = mind_client
        self.experiments: Dict[str, PatternExperiment] = {}
        self.session_assignments: Dict[str, str] = {}  # session_id -> experiment_id

    def create_experiment(
        self,
        name: str,
        description: str,
        control_pattern_id: str,
        treatment_pattern_id: str,
        min_samples: int = 30,
        confidence_level: float = 0.95
    ) -> PatternExperiment:
        """Create a new A/B experiment."""
        pass

    def start_experiment(self, experiment_id: str) -> bool:
        """Start an experiment (begin collecting data)."""
        pass

    def assign_session(self, session_id: str, experiment_id: str) -> str:
        """
        Randomly assign a session to control or treatment.

        Returns:
            "control" or "treatment"
        """
        pass

    def record_outcome(
        self,
        session_id: str,
        experiment_id: str,
        was_successful: bool
    ) -> bool:
        """Record the outcome for a session."""
        pass

    def analyze(self, experiment_id: str) -> ExperimentResult:
        """
        Perform statistical analysis on experiment.

        Uses chi-squared test or equivalent.
        """
        pass

    def _calculate_p_value(
        self,
        control_success: int,
        control_total: int,
        treatment_success: int,
        treatment_total: int
    ) -> float:
        """Calculate p-value using chi-squared test."""
        pass

    def conclude(self, experiment_id: str, winner: str) -> bool:
        """Conclude experiment and declare winner."""
        pass

    def get_active_experiments(self) -> List[PatternExperiment]:
        """Get all running experiments."""
        pass

    def get_experiment_for_task(self, task_category: str) -> Optional[PatternExperiment]:
        """Get active experiment applicable to task category."""
        pass
```

#### Unit Tests (`tests/test_experiment.py`)

```python
"""
Unit tests for lib/experiment.py
"""

import pytest
from lib.experiment import (
    ExperimentManager, PatternExperiment, ExperimentArm,
    ExperimentStatus, ExperimentResult
)


class TestExperimentArm:
    """Tests for ExperimentArm dataclass."""

    def test_total_trials(self):
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


class TestPatternExperiment:
    """Tests for PatternExperiment dataclass."""

    def test_total_sessions(self):
        """total_sessions counts both arms."""
        control = ExperimentArm(arm_id="control", pattern_id="p1")
        control.sessions_assigned = ["s1", "s2", "s3"]
        treatment = ExperimentArm(arm_id="treatment", pattern_id="p2")
        treatment.sessions_assigned = ["s4", "s5"]

        exp = PatternExperiment(
            experiment_id="exp1",
            name="Test",
            description="Test experiment",
            control=control,
            treatment=treatment
        )

        assert exp.total_sessions == 5

    def test_is_ready_for_analysis_false(self):
        """is_ready_for_analysis is False with few samples."""
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
        """is_ready_for_analysis is True with enough samples."""
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


class TestExperimentManagerCreate:
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
        assert exp.name == "Grep vs Glob"
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


class TestExperimentManagerStart:
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


class TestExperimentManagerAssign:
    """Tests for ExperimentManager.assign_session."""

    def test_assigns_to_arm(self):
        """assign_session returns control or treatment."""
        manager = ExperimentManager()
        exp = manager.create_experiment(
            name="Test",
            description="Test",
            control_pattern_id="p1",
            treatment_pattern_id="p2"
        )
        manager.start_experiment(exp.experiment_id)

        assignment = manager.assign_session("session1", exp.experiment_id)

        assert assignment in ["control", "treatment"]

    def test_assignment_is_random(self):
        """Assignments are roughly 50/50."""
        manager = ExperimentManager()
        exp = manager.create_experiment(
            name="Test",
            description="Test",
            control_pattern_id="p1",
            treatment_pattern_id="p2"
        )
        manager.start_experiment(exp.experiment_id)

        assignments = []
        for i in range(100):
            assignment = manager.assign_session(f"session{i}", exp.experiment_id)
            assignments.append(assignment)

        control_count = assignments.count("control")
        # Should be roughly 50/50 (allowing 30-70 range)
        assert 30 <= control_count <= 70

    def test_records_session_assignment(self):
        """Session assignment is recorded."""
        manager = ExperimentManager()
        exp = manager.create_experiment(
            name="Test",
            description="Test",
            control_pattern_id="p1",
            treatment_pattern_id="p2"
        )
        manager.start_experiment(exp.experiment_id)

        manager.assign_session("session1", exp.experiment_id)

        assert "session1" in manager.session_assignments


class TestExperimentManagerRecord:
    """Tests for ExperimentManager.record_outcome."""

    def test_records_success(self):
        """record_outcome increments success count."""
        manager = ExperimentManager()
        exp = manager.create_experiment(
            name="Test",
            description="Test",
            control_pattern_id="p1",
            treatment_pattern_id="p2"
        )
        manager.start_experiment(exp.experiment_id)
        manager.assign_session("session1", exp.experiment_id)

        result = manager.record_outcome("session1", exp.experiment_id, was_successful=True)

        assert result is True
        total_success = exp.control.success_count + exp.treatment.success_count
        assert total_success == 1

    def test_records_failure(self):
        """record_outcome increments failure count."""
        manager = ExperimentManager()
        exp = manager.create_experiment(
            name="Test",
            description="Test",
            control_pattern_id="p1",
            treatment_pattern_id="p2"
        )
        manager.start_experiment(exp.experiment_id)
        manager.assign_session("session1", exp.experiment_id)

        manager.record_outcome("session1", exp.experiment_id, was_successful=False)

        total_failure = exp.control.failure_count + exp.treatment.failure_count
        assert total_failure == 1


class TestExperimentManagerAnalyze:
    """Tests for ExperimentManager.analyze."""

    def test_analyzes_experiment(self):
        """analyze returns ExperimentResult."""
        manager = ExperimentManager()
        exp = manager.create_experiment(
            name="Test",
            description="Test",
            control_pattern_id="p1",
            treatment_pattern_id="p2",
            min_samples=5
        )
        manager.start_experiment(exp.experiment_id)

        # Add enough data
        exp.control.success_count = 5
        exp.control.failure_count = 5
        exp.treatment.success_count = 8
        exp.treatment.failure_count = 2

        result = manager.analyze(exp.experiment_id)

        assert isinstance(result, ExperimentResult)
        assert result.control_success_rate == 0.5
        assert result.treatment_success_rate == 0.8

    def test_detects_significant_difference(self):
        """Detects statistically significant difference."""
        manager = ExperimentManager()
        exp = manager.create_experiment(
            name="Test",
            description="Test",
            control_pattern_id="p1",
            treatment_pattern_id="p2",
            min_samples=30
        )
        manager.start_experiment(exp.experiment_id)

        # Large difference
        exp.control.success_count = 30
        exp.control.failure_count = 70
        exp.treatment.success_count = 70
        exp.treatment.failure_count = 30

        result = manager.analyze(exp.experiment_id)

        assert result.is_significant is True
        assert result.recommended_winner == "treatment"


class TestExperimentManagerConclude:
    """Tests for ExperimentManager.conclude."""

    def test_concludes_experiment(self):
        """conclude marks experiment as concluded."""
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
```

---

# M6: Cross-Project Intelligence

## Overview
Share learnings across projects intelligently based on project similarity.

## Components

### 6.1 ProjectAnalyzer (`lib/project_analyzer.py`)

#### Data Structures

```python
from dataclasses import dataclass, field
from typing import List, Dict, Set, Optional
from pathlib import Path
from enum import Enum


class ProjectType(Enum):
    """High-level project classification."""
    WEB_APP = "web_app"
    CLI_TOOL = "cli_tool"
    LIBRARY = "library"
    API_SERVICE = "api_service"
    DATA_PIPELINE = "data_pipeline"
    ML_PROJECT = "ml_project"
    MOBILE_APP = "mobile_app"
    UNKNOWN = "unknown"


@dataclass
class ProjectFingerprint:
    """Fingerprint capturing project characteristics."""
    project_path: str
    project_type: ProjectType
    primary_language: str
    languages: List[str] = field(default_factory=list)
    frameworks: List[str] = field(default_factory=list)
    build_tools: List[str] = field(default_factory=list)
    test_frameworks: List[str] = field(default_factory=list)
    patterns_detected: List[str] = field(default_factory=list)  # MVC, microservices, etc.
    file_count: int = 0
    directory_structure: Dict[str, int] = field(default_factory=dict)  # dir -> file count

    def similarity(self, other: 'ProjectFingerprint') -> float:
        """
        Calculate similarity score between 0 and 1.

        Factors:
        - Same project type: +0.3
        - Same primary language: +0.2
        - Overlapping frameworks: +0.2 * overlap ratio
        - Overlapping patterns: +0.2 * overlap ratio
        - Similar size: +0.1
        """
        pass

    def to_dict(self) -> Dict:
        """Convert to dictionary for storage."""
        pass

    @classmethod
    def from_dict(cls, data: Dict) -> 'ProjectFingerprint':
        """Create from dictionary."""
        pass
```

#### Class Definition

```python
class ProjectAnalyzer:
    """
    Analyzes a project to create its fingerprint.

    Detects:
    - Languages from file extensions and config files
    - Frameworks from dependencies and imports
    - Project type from structure and dependencies
    - Patterns from directory layout
    """

    # File patterns for detection
    LANGUAGE_EXTENSIONS = {
        '.py': 'python',
        '.js': 'javascript',
        '.ts': 'typescript',
        '.go': 'go',
        '.rs': 'rust',
        '.java': 'java',
        '.rb': 'ruby',
        '.cpp': 'cpp',
        '.c': 'c',
    }

    CONFIG_FILES = {
        'package.json': 'javascript',
        'requirements.txt': 'python',
        'pyproject.toml': 'python',
        'go.mod': 'go',
        'Cargo.toml': 'rust',
        'pom.xml': 'java',
        'Gemfile': 'ruby',
    }

    FRAMEWORK_INDICATORS = {
        'fastapi': ('python', 'FastAPI'),
        'django': ('python', 'Django'),
        'flask': ('python', 'Flask'),
        'react': ('javascript', 'React'),
        'vue': ('javascript', 'Vue'),
        'angular': ('javascript', 'Angular'),
        'express': ('javascript', 'Express'),
        'nextjs': ('javascript', 'Next.js'),
    }

    def __init__(self, max_files_to_scan: int = 1000):
        self.max_files_to_scan = max_files_to_scan

    def analyze(self, project_path: str) -> ProjectFingerprint:
        """
        Analyze a project and return its fingerprint.

        Args:
            project_path: Path to project root

        Returns:
            ProjectFingerprint with detected characteristics
        """
        pass

    def _detect_languages(self, project_path: Path) -> List[str]:
        """Detect programming languages used."""
        pass

    def _detect_frameworks(self, project_path: Path, languages: List[str]) -> List[str]:
        """Detect frameworks from dependencies."""
        pass

    def _detect_project_type(
        self,
        project_path: Path,
        languages: List[str],
        frameworks: List[str]
    ) -> ProjectType:
        """Infer project type from characteristics."""
        pass

    def _detect_patterns(self, project_path: Path) -> List[str]:
        """Detect architectural patterns from structure."""
        pass

    def _parse_package_json(self, path: Path) -> Dict:
        """Parse package.json for dependencies."""
        pass

    def _parse_requirements_txt(self, path: Path) -> List[str]:
        """Parse requirements.txt for dependencies."""
        pass

    def _parse_pyproject_toml(self, path: Path) -> Dict:
        """Parse pyproject.toml for dependencies."""
        pass
```

#### Unit Tests (`tests/test_project_analyzer.py`)

```python
"""
Unit tests for lib/project_analyzer.py
"""

import pytest
import tempfile
import os
from pathlib import Path
from lib.project_analyzer import ProjectAnalyzer, ProjectFingerprint, ProjectType


class TestProjectFingerprint:
    """Tests for ProjectFingerprint dataclass."""

    def test_similarity_same_project(self):
        """Identical fingerprints have similarity 1.0."""
        fp = ProjectFingerprint(
            project_path="/test",
            project_type=ProjectType.WEB_APP,
            primary_language="python",
            languages=["python"],
            frameworks=["FastAPI"]
        )

        assert fp.similarity(fp) == 1.0

    def test_similarity_different_types(self):
        """Different project types reduce similarity."""
        fp1 = ProjectFingerprint(
            project_path="/test1",
            project_type=ProjectType.WEB_APP,
            primary_language="python"
        )
        fp2 = ProjectFingerprint(
            project_path="/test2",
            project_type=ProjectType.CLI_TOOL,
            primary_language="python"
        )

        sim = fp1.similarity(fp2)
        assert sim < 1.0
        assert sim > 0.0  # Same language

    def test_similarity_different_languages(self):
        """Different languages reduce similarity."""
        fp1 = ProjectFingerprint(
            project_path="/test1",
            project_type=ProjectType.WEB_APP,
            primary_language="python"
        )
        fp2 = ProjectFingerprint(
            project_path="/test2",
            project_type=ProjectType.WEB_APP,
            primary_language="javascript"
        )

        sim = fp1.similarity(fp2)
        assert sim < 1.0

    def test_similarity_overlapping_frameworks(self):
        """Overlapping frameworks increase similarity."""
        fp1 = ProjectFingerprint(
            project_path="/test1",
            project_type=ProjectType.WEB_APP,
            primary_language="python",
            frameworks=["FastAPI", "SQLAlchemy"]
        )
        fp2 = ProjectFingerprint(
            project_path="/test2",
            project_type=ProjectType.WEB_APP,
            primary_language="python",
            frameworks=["FastAPI", "Pydantic"]
        )

        sim = fp1.similarity(fp2)
        # Should be higher due to shared FastAPI
        assert sim > 0.5

    def test_to_dict_and_back(self):
        """Round-trip through dict preserves data."""
        original = ProjectFingerprint(
            project_path="/test",
            project_type=ProjectType.API_SERVICE,
            primary_language="python",
            languages=["python", "sql"],
            frameworks=["FastAPI"]
        )

        data = original.to_dict()
        restored = ProjectFingerprint.from_dict(data)

        assert restored.project_path == original.project_path
        assert restored.project_type == original.project_type
        assert restored.frameworks == original.frameworks


class TestProjectAnalyzer:
    """Tests for ProjectAnalyzer class."""

    @pytest.fixture
    def temp_project(self):
        """Create a temporary project structure."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create some files
            Path(tmpdir, "main.py").write_text("print('hello')")
            Path(tmpdir, "utils.py").write_text("def util(): pass")
            Path(tmpdir, "requirements.txt").write_text("fastapi\nuvicorn\n")
            Path(tmpdir, "tests").mkdir()
            Path(tmpdir, "tests", "test_main.py").write_text("def test_main(): pass")
            yield tmpdir

    def test_detects_python_language(self, temp_project):
        """Detects Python as primary language."""
        analyzer = ProjectAnalyzer()

        fingerprint = analyzer.analyze(temp_project)

        assert fingerprint.primary_language == "python"
        assert "python" in fingerprint.languages

    def test_detects_frameworks_from_requirements(self, temp_project):
        """Detects frameworks from requirements.txt."""
        analyzer = ProjectAnalyzer()

        fingerprint = analyzer.analyze(temp_project)

        assert "FastAPI" in fingerprint.frameworks or "fastapi" in str(fingerprint.frameworks).lower()

    def test_detects_test_directory(self, temp_project):
        """Detects test framework presence."""
        analyzer = ProjectAnalyzer()

        fingerprint = analyzer.analyze(temp_project)

        assert "tests" in fingerprint.directory_structure or fingerprint.test_frameworks

    def test_handles_empty_directory(self):
        """Handles empty project directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            analyzer = ProjectAnalyzer()

            fingerprint = analyzer.analyze(tmpdir)

            assert fingerprint.project_type == ProjectType.UNKNOWN
            assert fingerprint.file_count == 0


class TestProjectAnalyzerJavaScript:
    """Tests for JavaScript project analysis."""

    @pytest.fixture
    def temp_js_project(self):
        """Create a temporary JavaScript project."""
        with tempfile.TemporaryDirectory() as tmpdir:
            package_json = {
                "name": "test-app",
                "dependencies": {
                    "react": "^18.0.0",
                    "next": "^14.0.0"
                },
                "devDependencies": {
                    "jest": "^29.0.0"
                }
            }
            import json
            Path(tmpdir, "package.json").write_text(json.dumps(package_json))
            Path(tmpdir, "src").mkdir()
            Path(tmpdir, "src", "index.js").write_text("export default function App() {}")
            yield tmpdir

    def test_detects_javascript_language(self, temp_js_project):
        """Detects JavaScript project."""
        analyzer = ProjectAnalyzer()

        fingerprint = analyzer.analyze(temp_js_project)

        assert fingerprint.primary_language == "javascript"

    def test_detects_react_framework(self, temp_js_project):
        """Detects React framework."""
        analyzer = ProjectAnalyzer()

        fingerprint = analyzer.analyze(temp_js_project)

        assert any("react" in f.lower() for f in fingerprint.frameworks)

    def test_detects_web_app_type(self, temp_js_project):
        """Detects web app project type."""
        analyzer = ProjectAnalyzer()

        fingerprint = analyzer.analyze(temp_js_project)

        assert fingerprint.project_type == ProjectType.WEB_APP


class TestProjectTypeDetection:
    """Tests for project type detection logic."""

    def test_cli_tool_detection(self):
        """Detects CLI tool projects."""
        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, "cli.py").write_text("import click\n@click.command()\ndef main(): pass")
            Path(tmpdir, "requirements.txt").write_text("click\n")

            analyzer = ProjectAnalyzer()
            fingerprint = analyzer.analyze(tmpdir)

            # Should detect as CLI or at least not web app
            assert fingerprint.project_type in [ProjectType.CLI_TOOL, ProjectType.LIBRARY, ProjectType.UNKNOWN]

    def test_api_service_detection(self):
        """Detects API service projects."""
        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, "main.py").write_text("from fastapi import FastAPI\napp = FastAPI()")
            Path(tmpdir, "requirements.txt").write_text("fastapi\nuvicorn\n")
            Path(tmpdir, "api").mkdir()
            Path(tmpdir, "api", "routes.py").write_text("# routes")

            analyzer = ProjectAnalyzer()
            fingerprint = analyzer.analyze(tmpdir)

            assert fingerprint.project_type in [ProjectType.API_SERVICE, ProjectType.WEB_APP]
```

---

### 6.2 LearningTransfer (`lib/learning_transfer.py`)

#### Data Structures

```python
from dataclasses import dataclass, field
from typing import List, Dict, Optional
from enum import Enum


class LearningScope(Enum):
    """Scope of learning applicability."""
    UNIVERSAL = "universal"         # Applies everywhere
    LANGUAGE = "language"           # Specific to a language
    FRAMEWORK = "framework"         # Specific to a framework
    PROJECT_TYPE = "project_type"   # Specific to project type
    PROJECT = "project"             # Only this project


@dataclass
class TransferableLearning:
    """A learning annotated with transfer scope."""
    learning_id: str
    content: str
    original_project: str
    scope: LearningScope
    applicable_languages: List[str] = field(default_factory=list)
    applicable_frameworks: List[str] = field(default_factory=list)
    applicable_project_types: List[str] = field(default_factory=list)
    transfer_confidence: float = 1.0  # Reduced when transferred
    times_transferred: int = 0
    success_when_transferred: int = 0

    @property
    def transfer_success_rate(self) -> float:
        if self.times_transferred == 0:
            return 0.5
        return self.success_when_transferred / self.times_transferred
```

#### Class Definition

```python
class LearningTransfer:
    """
    Manages transfer of learnings between projects.

    Responsibilities:
    1. Classify learning scope based on content
    2. Match learnings to target projects
    3. Adjust confidence for transferred learnings
    4. Track transfer success rates
    """

    # Indicators for scope classification
    UNIVERSAL_INDICATORS = [
        "tool_effectiveness",
        "error_avoidance",
        "performance",
    ]

    LANGUAGE_INDICATORS = {
        "python": ["pytest", "pip", "virtualenv", "__init__"],
        "javascript": ["npm", "yarn", "node_modules", "package.json"],
        "typescript": ["tsc", "tsconfig", ".ts"],
    }

    def __init__(self, mind_client: Optional[MindClient] = None):
        self.mind = mind_client
        self.transferable_learnings: Dict[str, TransferableLearning] = {}

    def classify_scope(self, learning_content: str, metadata: Dict) -> LearningScope:
        """
        Determine the scope of a learning.

        Args:
            learning_content: The learning text
            metadata: Associated metadata (pattern_type, tool, etc.)

        Returns:
            Appropriate LearningScope
        """
        pass

    def annotate_learning(
        self,
        learning_id: str,
        content: str,
        source_fingerprint: ProjectFingerprint,
        metadata: Dict
    ) -> TransferableLearning:
        """
        Create a TransferableLearning with proper scope annotation.
        """
        pass

    def get_applicable_learnings(
        self,
        target_fingerprint: ProjectFingerprint,
        min_confidence: float = 0.5
    ) -> List[TransferableLearning]:
        """
        Get learnings applicable to target project.

        Args:
            target_fingerprint: Target project fingerprint
            min_confidence: Minimum transfer confidence

        Returns:
            List of applicable learnings, sorted by relevance
        """
        pass

    def calculate_transfer_confidence(
        self,
        learning: TransferableLearning,
        source: ProjectFingerprint,
        target: ProjectFingerprint
    ) -> float:
        """
        Calculate confidence when transferring a learning.

        Factors:
        - Original confidence
        - Project similarity
        - Historical transfer success rate
        - Scope match quality
        """
        pass

    def record_transfer_outcome(
        self,
        learning_id: str,
        was_successful: bool
    ):
        """Record whether a transferred learning was successful."""
        pass

    async def sync_learnings_from_mind(self) -> int:
        """Load transferable learnings from Mind."""
        pass

    async def persist_learnings_to_mind(self) -> int:
        """Save transferable learnings to Mind."""
        pass
```

#### Unit Tests (`tests/test_learning_transfer.py`)

```python
"""
Unit tests for lib/learning_transfer.py
"""

import pytest
from lib.learning_transfer import (
    LearningTransfer, TransferableLearning, LearningScope
)
from lib.project_analyzer import ProjectFingerprint, ProjectType


class TestTransferableLearning:
    """Tests for TransferableLearning dataclass."""

    def test_transfer_success_rate_no_transfers(self):
        """Success rate is 0.5 with no transfers."""
        learning = TransferableLearning(
            learning_id="l1",
            content="Test",
            original_project="proj1",
            scope=LearningScope.UNIVERSAL
        )

        assert learning.transfer_success_rate == 0.5

    def test_transfer_success_rate_calculation(self):
        """Success rate calculates correctly."""
        learning = TransferableLearning(
            learning_id="l1",
            content="Test",
            original_project="proj1",
            scope=LearningScope.UNIVERSAL,
            times_transferred=10,
            success_when_transferred=7
        )

        assert learning.transfer_success_rate == 0.7


class TestLearningTransferClassify:
    """Tests for LearningTransfer.classify_scope."""

    def test_classifies_universal_tool_learning(self):
        """Tool effectiveness learnings are universal."""
        transfer = LearningTransfer()

        scope = transfer.classify_scope(
            "LEARNING [TOOL_EFFECTIVENESS]: Grep has 90% success rate",
            {"pattern_type": "tool_effectiveness", "tool": "Grep"}
        )

        assert scope == LearningScope.UNIVERSAL

    def test_classifies_language_specific(self):
        """Python-specific learnings are language scoped."""
        transfer = LearningTransfer()

        scope = transfer.classify_scope(
            "LEARNING: Use pytest fixtures for test setup",
            {"pattern_type": "skill_usage", "keywords": ["pytest", "fixtures"]}
        )

        assert scope == LearningScope.LANGUAGE

    def test_classifies_framework_specific(self):
        """Framework-specific learnings are framework scoped."""
        transfer = LearningTransfer()

        scope = transfer.classify_scope(
            "LEARNING: Use FastAPI dependency injection for auth",
            {"pattern_type": "skill_usage", "keywords": ["FastAPI", "dependency"]}
        )

        assert scope == LearningScope.FRAMEWORK


class TestLearningTransferAnnotate:
    """Tests for LearningTransfer.annotate_learning."""

    def test_annotates_with_source_project(self):
        """Annotated learning includes source project."""
        transfer = LearningTransfer()
        source_fp = ProjectFingerprint(
            project_path="/source",
            project_type=ProjectType.API_SERVICE,
            primary_language="python",
            frameworks=["FastAPI"]
        )

        annotated = transfer.annotate_learning(
            learning_id="l1",
            content="Use dependency injection",
            source_fingerprint=source_fp,
            metadata={"pattern_type": "skill_usage"}
        )

        assert annotated.original_project == "/source"

    def test_annotates_applicable_languages(self):
        """Annotated learning includes applicable languages."""
        transfer = LearningTransfer()
        source_fp = ProjectFingerprint(
            project_path="/source",
            project_type=ProjectType.API_SERVICE,
            primary_language="python",
            languages=["python", "sql"],
            frameworks=["FastAPI"]
        )

        annotated = transfer.annotate_learning(
            learning_id="l1",
            content="Python async patterns",
            source_fingerprint=source_fp,
            metadata={"pattern_type": "skill_usage"}
        )

        assert "python" in annotated.applicable_languages


class TestLearningTransferApplicable:
    """Tests for LearningTransfer.get_applicable_learnings."""

    def test_returns_universal_learnings(self):
        """Universal learnings apply to all projects."""
        transfer = LearningTransfer()

        # Add a universal learning
        transfer.transferable_learnings["l1"] = TransferableLearning(
            learning_id="l1",
            content="Grep is effective for search",
            original_project="/other",
            scope=LearningScope.UNIVERSAL,
            transfer_confidence=0.9
        )

        target = ProjectFingerprint(
            project_path="/target",
            project_type=ProjectType.WEB_APP,
            primary_language="javascript"
        )

        applicable = transfer.get_applicable_learnings(target)

        assert len(applicable) == 1
        assert applicable[0].learning_id == "l1"

    def test_filters_by_language(self):
        """Language-scoped learnings only apply to matching projects."""
        transfer = LearningTransfer()

        transfer.transferable_learnings["l1"] = TransferableLearning(
            learning_id="l1",
            content="Python pytest tips",
            original_project="/other",
            scope=LearningScope.LANGUAGE,
            applicable_languages=["python"],
            transfer_confidence=0.8
        )

        # JavaScript project
        target = ProjectFingerprint(
            project_path="/target",
            project_type=ProjectType.WEB_APP,
            primary_language="javascript"
        )

        applicable = transfer.get_applicable_learnings(target)

        # Python learning should not apply
        assert len(applicable) == 0

    def test_includes_matching_language(self):
        """Language-scoped learnings apply to matching language."""
        transfer = LearningTransfer()

        transfer.transferable_learnings["l1"] = TransferableLearning(
            learning_id="l1",
            content="Python pytest tips",
            original_project="/other",
            scope=LearningScope.LANGUAGE,
            applicable_languages=["python"],
            transfer_confidence=0.8
        )

        # Python project
        target = ProjectFingerprint(
            project_path="/target",
            project_type=ProjectType.API_SERVICE,
            primary_language="python"
        )

        applicable = transfer.get_applicable_learnings(target)

        assert len(applicable) == 1

    def test_respects_min_confidence(self):
        """Filters by minimum confidence."""
        transfer = LearningTransfer()

        transfer.transferable_learnings["l1"] = TransferableLearning(
            learning_id="l1",
            content="Low confidence learning",
            original_project="/other",
            scope=LearningScope.UNIVERSAL,
            transfer_confidence=0.3
        )

        target = ProjectFingerprint(
            project_path="/target",
            project_type=ProjectType.WEB_APP,
            primary_language="python"
        )

        applicable = transfer.get_applicable_learnings(target, min_confidence=0.5)

        assert len(applicable) == 0


class TestLearningTransferConfidence:
    """Tests for LearningTransfer.calculate_transfer_confidence."""

    def test_reduces_confidence_for_dissimilar_projects(self):
        """Dissimilar projects reduce transfer confidence."""
        transfer = LearningTransfer()

        learning = TransferableLearning(
            learning_id="l1",
            content="Test",
            original_project="/source",
            scope=LearningScope.LANGUAGE,
            applicable_languages=["python"],
            transfer_confidence=0.9
        )

        source = ProjectFingerprint(
            project_path="/source",
            project_type=ProjectType.API_SERVICE,
            primary_language="python",
            frameworks=["FastAPI"]
        )

        target = ProjectFingerprint(
            project_path="/target",
            project_type=ProjectType.CLI_TOOL,
            primary_language="python",
            frameworks=["Click"]
        )

        confidence = transfer.calculate_transfer_confidence(learning, source, target)

        # Should be reduced from 0.9
        assert confidence < 0.9
        assert confidence > 0  # Still some confidence


class TestLearningTransferOutcome:
    """Tests for LearningTransfer.record_transfer_outcome."""

    def test_records_successful_transfer(self):
        """Records successful transfer outcome."""
        transfer = LearningTransfer()

        transfer.transferable_learnings["l1"] = TransferableLearning(
            learning_id="l1",
            content="Test",
            original_project="/other",
            scope=LearningScope.UNIVERSAL
        )

        transfer.record_transfer_outcome("l1", was_successful=True)

        learning = transfer.transferable_learnings["l1"]
        assert learning.times_transferred == 1
        assert learning.success_when_transferred == 1

    def test_records_failed_transfer(self):
        """Records failed transfer outcome."""
        transfer = LearningTransfer()

        transfer.transferable_learnings["l1"] = TransferableLearning(
            learning_id="l1",
            content="Test",
            original_project="/other",
            scope=LearningScope.UNIVERSAL
        )

        transfer.record_transfer_outcome("l1", was_successful=False)

        learning = transfer.transferable_learnings["l1"]
        assert learning.times_transferred == 1
        assert learning.success_when_transferred == 0
```

---

*[Document continues with M7, M8, M10 specifications...]*

Due to length, the remaining milestones (M7: Advanced Prompt Evolution, M8: MCP Server Enhancement, M10: Observability & Debugging) follow the same comprehensive format with:
- Detailed data structures
- Complete class definitions with method signatures
- Comprehensive unit test plans

See `docs/SPECIFICATIONS_PART2.md` for continuation.

---

## Test Execution

Run all specification tests:
```bash
# Run M5 tests
pytest tests/test_injection_tracker.py tests/test_experiment.py -v

# Run M6 tests
pytest tests/test_project_analyzer.py tests/test_learning_transfer.py -v

# Run all milestone tests
pytest tests/test_*.py -v
```

## Coverage Requirements

| Component | Target Coverage |
|-----------|-----------------|
| InjectionTracker | 95% |
| ExperimentManager | 95% |
| ProjectAnalyzer | 90% |
| LearningTransfer | 95% |
| PatternBreeder (M7) | 90% |
| MCPServer (M8) | 90% |
| SparkDashboard (M10) | 80% |

---

*Last updated: 2026-01-23*
