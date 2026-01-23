"""
ExperimentManager: A/B testing for pattern comparison.

When Spark discovers two possible approaches (e.g., "recommend Grep" vs "recommend Glob"),
this manager runs controlled experiments to determine which actually works better.

Uses statistical significance testing to avoid false conclusions.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple
from enum import Enum
import random
import math
import time
import uuid


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
    created_at: float = field(default_factory=time.time)
    started_at: Optional[float] = None
    concluded_at: Optional[float] = None
    min_samples_per_arm: int = 30
    confidence_level: float = 0.95
    winner: Optional[str] = None  # "control", "treatment", or "tie"
    task_category: Optional[str] = None  # What type of tasks this applies to

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
    confidence_interval: Tuple[float, float]  # (lower, upper) for difference


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

    def __init__(self, mind_client=None):
        """
        Initialize experiment manager.

        Args:
            mind_client: Optional Mind client for persisting experiment data
        """
        self.mind = mind_client
        self.experiments: Dict[str, PatternExperiment] = {}
        self.session_assignments: Dict[str, Tuple[str, str]] = {}  # session_id -> (experiment_id, arm)

    def create_experiment(
        self,
        name: str,
        description: str,
        control_pattern_id: str,
        treatment_pattern_id: str,
        min_samples: int = 30,
        confidence_level: float = 0.95,
        task_category: Optional[str] = None
    ) -> PatternExperiment:
        """
        Create a new A/B experiment.

        Args:
            name: Human-readable name
            description: What we're testing
            control_pattern_id: ID of the existing/baseline pattern
            treatment_pattern_id: ID of the new pattern to test
            min_samples: Minimum samples per arm before analysis
            confidence_level: Required confidence (default 95%)
            task_category: Optional task category this applies to

        Returns:
            The created experiment
        """
        experiment_id = f"exp_{uuid.uuid4().hex[:12]}"

        control = ExperimentArm(
            arm_id="control",
            pattern_id=control_pattern_id
        )
        treatment = ExperimentArm(
            arm_id="treatment",
            pattern_id=treatment_pattern_id
        )

        experiment = PatternExperiment(
            experiment_id=experiment_id,
            name=name,
            description=description,
            control=control,
            treatment=treatment,
            min_samples_per_arm=min_samples,
            confidence_level=confidence_level,
            task_category=task_category
        )

        self.experiments[experiment_id] = experiment
        return experiment

    def start_experiment(self, experiment_id: str) -> bool:
        """
        Start an experiment (begin collecting data).

        Args:
            experiment_id: ID of the experiment to start

        Returns:
            True if started, False if not found
        """
        if experiment_id not in self.experiments:
            return False

        experiment = self.experiments[experiment_id]
        experiment.status = ExperimentStatus.RUNNING
        experiment.started_at = time.time()
        return True

    def assign_session(self, session_id: str, experiment_id: str) -> Optional[str]:
        """
        Randomly assign a session to control or treatment.

        Uses 50/50 random assignment for unbiased experiment.

        Args:
            session_id: The session to assign
            experiment_id: The experiment to assign to

        Returns:
            "control" or "treatment", or None if experiment not found/not running
        """
        if experiment_id not in self.experiments:
            return None

        experiment = self.experiments[experiment_id]
        if experiment.status != ExperimentStatus.RUNNING:
            return None

        # Check if already assigned
        if session_id in self.session_assignments:
            existing_exp_id, existing_arm = self.session_assignments[session_id]
            if existing_exp_id == experiment_id:
                return existing_arm

        # Random 50/50 assignment
        arm = random.choice(["control", "treatment"])

        if arm == "control":
            experiment.control.sessions_assigned.append(session_id)
        else:
            experiment.treatment.sessions_assigned.append(session_id)

        self.session_assignments[session_id] = (experiment_id, arm)
        return arm

    def record_outcome(
        self,
        session_id: str,
        experiment_id: str,
        was_successful: bool
    ) -> bool:
        """
        Record the outcome for a session.

        Args:
            session_id: The session
            experiment_id: The experiment
            was_successful: Whether the pattern led to success

        Returns:
            True if recorded, False if session not in experiment
        """
        if experiment_id not in self.experiments:
            return False

        if session_id not in self.session_assignments:
            return False

        assigned_exp_id, arm = self.session_assignments[session_id]
        if assigned_exp_id != experiment_id:
            return False

        experiment = self.experiments[experiment_id]

        if arm == "control":
            if was_successful:
                experiment.control.success_count += 1
            else:
                experiment.control.failure_count += 1
        else:
            if was_successful:
                experiment.treatment.success_count += 1
            else:
                experiment.treatment.failure_count += 1

        return True

    def analyze(self, experiment_id: str) -> Optional[ExperimentResult]:
        """
        Perform statistical analysis on experiment.

        Uses chi-squared approximation for proportion comparison.

        Args:
            experiment_id: The experiment to analyze

        Returns:
            ExperimentResult or None if not enough data
        """
        if experiment_id not in self.experiments:
            return None

        experiment = self.experiments[experiment_id]

        control_success = experiment.control.success_count
        control_total = experiment.control.total_trials
        treatment_success = experiment.treatment.success_count
        treatment_total = experiment.treatment.total_trials

        if control_total == 0 or treatment_total == 0:
            return None

        control_rate = control_success / control_total
        treatment_rate = treatment_success / treatment_total

        # Calculate relative improvement
        if control_rate > 0:
            relative_improvement = (treatment_rate - control_rate) / control_rate
        else:
            relative_improvement = float('inf') if treatment_rate > 0 else 0.0

        # Calculate p-value
        p_value = self._calculate_p_value(
            control_success, control_total,
            treatment_success, treatment_total
        )

        # Check significance
        is_significant = p_value < (1 - experiment.confidence_level)

        # Calculate confidence interval for difference
        diff = treatment_rate - control_rate
        se = math.sqrt(
            (control_rate * (1 - control_rate) / control_total) +
            (treatment_rate * (1 - treatment_rate) / treatment_total)
        ) if control_total > 0 and treatment_total > 0 else 0

        z = 1.96  # 95% CI
        ci_lower = diff - z * se
        ci_upper = diff + z * se

        # Determine winner
        if not is_significant:
            recommended_winner = "inconclusive"
        elif treatment_rate > control_rate:
            recommended_winner = "treatment"
        elif control_rate > treatment_rate:
            recommended_winner = "control"
        else:
            recommended_winner = "tie"

        return ExperimentResult(
            experiment_id=experiment_id,
            control_success_rate=control_rate,
            treatment_success_rate=treatment_rate,
            relative_improvement=relative_improvement,
            p_value=p_value,
            is_significant=is_significant,
            recommended_winner=recommended_winner,
            confidence_interval=(ci_lower, ci_upper)
        )

    def _calculate_p_value(
        self,
        control_success: int,
        control_total: int,
        treatment_success: int,
        treatment_total: int
    ) -> float:
        """
        Calculate p-value using two-proportion z-test.

        This tests whether the difference in proportions is statistically significant.
        """
        if control_total == 0 or treatment_total == 0:
            return 1.0

        # Pooled proportion
        pooled = (control_success + treatment_success) / (control_total + treatment_total)

        if pooled == 0 or pooled == 1:
            return 1.0

        # Standard error
        se = math.sqrt(pooled * (1 - pooled) * (1/control_total + 1/treatment_total))

        if se == 0:
            return 1.0

        # Z-score
        p1 = control_success / control_total
        p2 = treatment_success / treatment_total
        z = abs(p2 - p1) / se

        # Two-tailed p-value using normal approximation
        # Using the complementary error function approximation
        p_value = 2 * (1 - self._normal_cdf(z))

        return p_value

    def _normal_cdf(self, x: float) -> float:
        """
        Approximate normal CDF using error function approximation.

        This avoids scipy dependency.
        """
        # Approximation using tanh
        return 0.5 * (1 + math.tanh(math.sqrt(2/math.pi) * (x + 0.044715 * x**3)))

    def conclude(self, experiment_id: str, winner: str) -> bool:
        """
        Conclude experiment and declare winner.

        Args:
            experiment_id: The experiment to conclude
            winner: "control", "treatment", or "tie"

        Returns:
            True if concluded, False if not found
        """
        if experiment_id not in self.experiments:
            return False

        if winner not in ["control", "treatment", "tie"]:
            return False

        experiment = self.experiments[experiment_id]
        experiment.status = ExperimentStatus.CONCLUDED
        experiment.concluded_at = time.time()
        experiment.winner = winner

        return True

    def cancel(self, experiment_id: str) -> bool:
        """
        Cancel a running experiment.

        Args:
            experiment_id: The experiment to cancel

        Returns:
            True if cancelled, False if not found
        """
        if experiment_id not in self.experiments:
            return False

        experiment = self.experiments[experiment_id]
        experiment.status = ExperimentStatus.CANCELLED
        experiment.concluded_at = time.time()

        return True

    def get_active_experiments(self) -> List[PatternExperiment]:
        """Get all running experiments."""
        return [
            exp for exp in self.experiments.values()
            if exp.status == ExperimentStatus.RUNNING
        ]

    def get_experiment_for_task(self, task_category: str) -> Optional[PatternExperiment]:
        """
        Get active experiment applicable to task category.

        Args:
            task_category: The type of task

        Returns:
            Applicable experiment or None
        """
        for exp in self.experiments.values():
            if exp.status == ExperimentStatus.RUNNING:
                if exp.task_category is None or exp.task_category == task_category:
                    return exp
        return None

    def get_experiment(self, experiment_id: str) -> Optional[PatternExperiment]:
        """Get experiment by ID."""
        return self.experiments.get(experiment_id)

    def get_session_arm(self, session_id: str) -> Optional[Tuple[str, str]]:
        """
        Get the experiment and arm for a session.

        Returns:
            (experiment_id, arm) or None
        """
        return self.session_assignments.get(session_id)

    def auto_conclude_if_significant(self, experiment_id: str) -> Optional[ExperimentResult]:
        """
        Analyze and auto-conclude if statistically significant.

        Args:
            experiment_id: The experiment to check

        Returns:
            ExperimentResult if concluded, None otherwise
        """
        experiment = self.experiments.get(experiment_id)
        if not experiment or not experiment.is_ready_for_analysis:
            return None

        result = self.analyze(experiment_id)
        if result and result.is_significant:
            self.conclude(experiment_id, result.recommended_winner)
            return result

        return None

    async def persist_experiment(self, experiment_id: str) -> bool:
        """
        Persist experiment to Mind.

        Args:
            experiment_id: The experiment to persist

        Returns:
            True if persisted, False otherwise
        """
        if not self.mind or experiment_id not in self.experiments:
            return False

        experiment = self.experiments[experiment_id]

        from lib.mind_client import Memory, TemporalLevel, ContentType

        content = (
            f"EXPERIMENT [{experiment.status.value}]: {experiment.name}\n"
            f"Control ({experiment.control.pattern_id}): "
            f"{experiment.control.success_rate:.1%} ({experiment.control.total_trials} trials)\n"
            f"Treatment ({experiment.treatment.pattern_id}): "
            f"{experiment.treatment.success_rate:.1%} ({experiment.treatment.total_trials} trials)"
        )

        if experiment.winner:
            content += f"\nWinner: {experiment.winner}"

        memory = Memory(
            content=content,
            temporal_level=TemporalLevel.SEASONAL,
            content_type=ContentType.DECISION,
            salience=0.7,
            metadata={
                "type": "experiment",
                "experiment_id": experiment_id,
                "status": experiment.status.value,
                "winner": experiment.winner
            }
        )

        await self.mind.store(memory)
        return True

    def get_stats(self) -> Dict:
        """Get overall experiment statistics."""
        total = len(self.experiments)
        running = sum(1 for e in self.experiments.values() if e.status == ExperimentStatus.RUNNING)
        concluded = sum(1 for e in self.experiments.values() if e.status == ExperimentStatus.CONCLUDED)
        cancelled = sum(1 for e in self.experiments.values() if e.status == ExperimentStatus.CANCELLED)

        return {
            "total_experiments": total,
            "running": running,
            "concluded": concluded,
            "cancelled": cancelled,
            "sessions_in_experiments": len(self.session_assignments)
        }
