"""
InjectionTracker: Tracks injected suggestions and determines if they were helpful.

This closes the feedback loop - when Spark injects context like "use Grep for search",
we track whether the user actually followed that suggestion, ignored it, or did the opposite.

This feedback adjusts confidence scores, making good suggestions stronger and bad ones weaker.
"""

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
    outcome_evidence: List[str] = field(default_factory=list)
    confidence_delta: float = 0.0  # How much to adjust learning confidence

    @property
    def age_seconds(self) -> float:
        """How long since injection."""
        return time.time() - self.injected_at

    @property
    def is_stale(self) -> bool:
        """Whether injection is too old to track (> 1 hour)."""
        return self.age_seconds > 3600


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

    def __init__(self, mind_client=None):
        """
        Initialize tracker.

        Args:
            mind_client: Optional Mind client for persisting feedback
        """
        self.mind = mind_client
        self.active_injections: Dict[str, TrackedInjection] = {}
        self.completed_injections: List[TrackedInjection] = []
        self.stats = FeedbackStats()
        self._session_tool_sequence: Dict[str, List[str]] = {}  # session_id -> [tool_names]
        self._determination_times: List[float] = []

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
            injection_type: Type of injection (tool_recommendation, error_warning, skill_suggestion)
            content_summary: Brief description of injected content
            trigger_conditions: What triggered this injection

        Returns:
            tracking_id: Unique ID for this tracked injection
        """
        # Generate tracking ID
        tracking_id = f"inj_{uuid.uuid4().hex[:12]}"

        # Create tracked injection
        injection = TrackedInjection(
            tracking_id=tracking_id,
            learning_id=learning_id,
            session_id=session_id,
            injection_type=injection_type,
            injected_at=time.time(),
            content_summary=content_summary,
            trigger_conditions=trigger_conditions
        )

        # Enforce max limit - remove oldest if at capacity
        if len(self.active_injections) >= self.MAX_ACTIVE_INJECTIONS:
            oldest_id = min(
                self.active_injections.keys(),
                key=lambda k: self.active_injections[k].injected_at
            )
            old_injection = self.active_injections.pop(oldest_id)
            old_injection.outcome = InjectionOutcome.EXPIRED
            self.completed_injections.append(old_injection)
            self.stats.expired_count += 1

        # Store injection
        self.active_injections[tracking_id] = injection
        self.stats.total_injections += 1

        # Initialize session tool sequence if needed
        if session_id not in self._session_tool_sequence:
            self._session_tool_sequence[session_id] = []

        return tracking_id

    def observe_event(self, event) -> Optional[str]:
        """
        Observe an event and check if it relates to any active injection.

        Args:
            event: The observed SparkEvent

        Returns:
            tracking_id if event determined an outcome, None otherwise
        """
        if not hasattr(event, 'session_id') or not hasattr(event, 'tool_name'):
            return None

        session_id = event.session_id
        tool_name = event.tool_name or ""

        # Track tool sequence for this session
        if session_id not in self._session_tool_sequence:
            self._session_tool_sequence[session_id] = []
        if tool_name:
            self._session_tool_sequence[session_id].append(tool_name)

        # Check each active injection for this session
        for tracking_id, injection in list(self.active_injections.items()):
            if injection.session_id != session_id:
                continue

            outcome = None

            # Check based on injection type
            if injection.injection_type == "tool_recommendation":
                outcome = self._check_tool_recommendation(injection, event)
            elif injection.injection_type == "error_warning":
                outcome = self._check_error_warning(injection, event)
            elif injection.injection_type == "skill_suggestion":
                outcome = self._check_skill_suggestion(injection, event)

            if outcome is not None:
                self.determine_outcome(
                    tracking_id=tracking_id,
                    outcome=outcome,
                    evidence=[f"Event: {tool_name} at {event.timestamp}"]
                )
                return tracking_id

        return None

    def _check_tool_recommendation(
        self,
        injection: TrackedInjection,
        event
    ) -> Optional[InjectionOutcome]:
        """
        Check if a tool recommendation was followed.

        Logic:
        - If recommended tool is used -> FOLLOWED
        - If different tool used for same task type -> IGNORED
        """
        recommended_tool = injection.trigger_conditions.get("recommended_tool")
        if not recommended_tool:
            return None

        tool_used = event.tool_name

        if tool_used == recommended_tool:
            return InjectionOutcome.FOLLOWED

        # Check if enough events have passed to call it ignored
        session_tools = self._session_tool_sequence.get(injection.session_id, [])
        events_since_injection = len([
            t for t in session_tools
            if session_tools.index(t) > session_tools.index(tool_used) - self.MIN_EVIDENCE_EVENTS
        ]) if tool_used in session_tools else 0

        if events_since_injection >= self.MIN_EVIDENCE_EVENTS:
            # User did several things without using recommended tool
            return InjectionOutcome.IGNORED

        return None

    def _check_error_warning(
        self,
        injection: TrackedInjection,
        event
    ) -> Optional[InjectionOutcome]:
        """
        Check if an error warning was heeded.

        Logic:
        - If warned error occurred -> IGNORED (they didn't heed the warning)
        - If warned tool used successfully -> FOLLOWED (they were careful)
        """
        warned_error = injection.trigger_conditions.get("warned_error")
        warned_tool = injection.trigger_conditions.get("warned_tool")

        if not warned_error:
            return None

        # Check if the warned error occurred
        if hasattr(event, 'error') and event.error:
            error_text = str(event.error).lower()
            if warned_error.lower() in error_text:
                return InjectionOutcome.IGNORED  # Warning was not heeded

        # Check if tool was used successfully (warning heeded)
        if warned_tool and event.tool_name == warned_tool:
            if not hasattr(event, 'error') or not event.error:
                return InjectionOutcome.FOLLOWED

        return None

    def _check_skill_suggestion(
        self,
        injection: TrackedInjection,
        event
    ) -> Optional[InjectionOutcome]:
        """
        Check if a skill suggestion was followed.

        Logic:
        - If suggested skill invoked -> FOLLOWED
        - If task completed differently -> IGNORED
        """
        suggested_skill = injection.trigger_conditions.get("suggested_skill")
        if not suggested_skill:
            return None

        # Check tool input for skill invocation
        if hasattr(event, 'tool_input') and event.tool_input:
            tool_input_str = str(event.tool_input).lower()
            if suggested_skill.lower() in tool_input_str:
                return InjectionOutcome.FOLLOWED

        return None

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
        if tracking_id not in self.active_injections:
            return False

        injection = self.active_injections.pop(tracking_id)
        injection.outcome = outcome
        injection.outcome_determined_at = time.time()
        injection.outcome_evidence = evidence

        # Calculate confidence delta
        if outcome == InjectionOutcome.FOLLOWED:
            injection.confidence_delta = self.CONFIDENCE_BOOST_FOLLOWED
            self.stats.followed_count += 1
        elif outcome == InjectionOutcome.IGNORED:
            injection.confidence_delta = -self.CONFIDENCE_PENALTY_IGNORED
            self.stats.ignored_count += 1
        elif outcome == InjectionOutcome.CONTRADICTED:
            injection.confidence_delta = -self.CONFIDENCE_PENALTY_CONTRADICTED
            self.stats.contradicted_count += 1
        elif outcome == InjectionOutcome.EXPIRED:
            self.stats.expired_count += 1

        # Track determination time
        determination_time = injection.outcome_determined_at - injection.injected_at
        self._determination_times.append(determination_time)

        # Update stats
        self.stats.outcomes_determined += 1
        if self._determination_times:
            self.stats.avg_determination_time_sec = (
                sum(self._determination_times) / len(self._determination_times)
            )

        # Calculate follow rate
        actionable = (
            self.stats.followed_count +
            self.stats.ignored_count +
            self.stats.contradicted_count
        )
        if actionable > 0:
            self.stats.follow_rate = self.stats.followed_count / actionable

        # Move to completed
        self.completed_injections.append(injection)

        return True

    async def update_learning_confidence(self, tracking_id: str) -> float:
        """
        Update the source learning's confidence based on outcome.

        This is where the feedback loop closes - we adjust the original
        learning's confidence based on whether our suggestion helped.

        Args:
            tracking_id: ID of the completed tracked injection

        Returns:
            The confidence delta applied
        """
        # Find the completed injection
        injection = next(
            (i for i in self.completed_injections if i.tracking_id == tracking_id),
            None
        )
        if not injection:
            return 0.0

        if not self.mind:
            return injection.confidence_delta

        # Store feedback in Mind
        from lib.mind_client import Memory, TemporalLevel, ContentType

        feedback_content = (
            f"FEEDBACK [{injection.outcome.value}]: "
            f"Injection '{injection.content_summary}' was {injection.outcome.value}. "
            f"Confidence delta: {injection.confidence_delta:+.2f}"
        )

        memory = Memory(
            content=feedback_content,
            temporal_level=TemporalLevel.SITUATIONAL,
            content_type=ContentType.EVENT,
            salience=0.6,
            metadata={
                "type": "injection_feedback",
                "tracking_id": tracking_id,
                "learning_id": injection.learning_id,
                "outcome": injection.outcome.value,
                "confidence_delta": injection.confidence_delta
            }
        )

        await self.mind.store(memory)

        return injection.confidence_delta

    def expire_stale_injections(self) -> int:
        """
        Mark old injections as expired.

        Returns:
            Number of injections expired
        """
        expired_count = 0
        current_time = time.time()

        for tracking_id, injection in list(self.active_injections.items()):
            if injection.is_stale or (current_time - injection.injected_at) > self.OUTCOME_TIMEOUT_SEC:
                self.determine_outcome(
                    tracking_id=tracking_id,
                    outcome=InjectionOutcome.EXPIRED,
                    evidence=["Injection timed out"]
                )
                expired_count += 1

        return expired_count

    def get_stats(self) -> FeedbackStats:
        """Get current feedback statistics."""
        return self.stats

    def clear_session(self, session_id: str) -> int:
        """
        Clear all injections for a session.

        Args:
            session_id: Session to clear

        Returns:
            Number of injections cleared
        """
        cleared = 0

        for tracking_id, injection in list(self.active_injections.items()):
            if injection.session_id == session_id:
                self.determine_outcome(
                    tracking_id=tracking_id,
                    outcome=InjectionOutcome.EXPIRED,
                    evidence=["Session ended"]
                )
                cleared += 1

        # Clear tool sequence
        if session_id in self._session_tool_sequence:
            del self._session_tool_sequence[session_id]

        return cleared

    async def persist_completed(self) -> int:
        """
        Persist completed injections to Mind.

        Returns:
            Number persisted
        """
        if not self.mind:
            return 0

        persisted = 0
        for injection in self.completed_injections:
            if injection.outcome != InjectionOutcome.PENDING:
                delta = await self.update_learning_confidence(injection.tracking_id)
                if delta != 0:
                    persisted += 1

        return persisted

    def get_active_for_session(self, session_id: str) -> List[TrackedInjection]:
        """Get all active injections for a session."""
        return [
            inj for inj in self.active_injections.values()
            if inj.session_id == session_id
        ]

    def get_follow_rate_for_type(self, injection_type: str) -> float:
        """Get follow rate for a specific injection type."""
        type_injections = [
            inj for inj in self.completed_injections
            if inj.injection_type == injection_type
        ]

        followed = sum(1 for inj in type_injections if inj.outcome == InjectionOutcome.FOLLOWED)
        actionable = sum(
            1 for inj in type_injections
            if inj.outcome in [InjectionOutcome.FOLLOWED, InjectionOutcome.IGNORED, InjectionOutcome.CONTRADICTED]
        )

        return followed / actionable if actionable > 0 else 0.0
