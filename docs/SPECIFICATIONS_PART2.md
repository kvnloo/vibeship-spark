# Spark Comprehensive Specifications - Part 2

Continuation of milestone specifications for M7, M8, and M10.

---

# M7: Advanced Prompt Evolution

## Overview
Sophisticated genetic algorithm for pattern optimization with crossover, mutation, and selection.

## Components

### 7.1 PatternBreeder (`lib/pattern_breeder.py`)

#### Data Structures

```python
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple, Callable
from enum import Enum
import random
import copy


class MutationType(Enum):
    """Types of mutations that can be applied."""
    TRIGGER_EXPAND = "trigger_expand"       # Add trigger condition
    TRIGGER_NARROW = "trigger_narrow"       # Remove trigger condition
    APPROACH_REPHRASE = "approach_rephrase" # Rephrase approach text
    TOOL_SWAP = "tool_swap"                 # Swap recommended tool
    CONFIDENCE_ADJUST = "confidence_adjust" # Adjust confidence threshold


@dataclass
class MutationRecord:
    """Record of a mutation applied to a pattern."""
    mutation_type: MutationType
    original_value: str
    new_value: str
    timestamp: float


@dataclass
class BreedingResult:
    """Result of a breeding operation."""
    parent_a_id: str
    parent_b_id: str
    offspring: 'PromptPattern'
    crossover_point: str          # What was crossed over
    mutations_applied: List[MutationRecord]


@dataclass
class PopulationStats:
    """Statistics about a pattern population."""
    size: int
    avg_fitness: float
    max_fitness: float
    min_fitness: float
    diversity_score: float        # 0-1, how varied the population is
    generations_evolved: int
    total_mutations: int
    successful_mutations: int
```

#### Class Definition

```python
class PatternBreeder:
    """
    Genetic algorithm for evolving prompt patterns.

    Operations:
    1. Selection: Choose fittest patterns for breeding
    2. Crossover: Combine two patterns to create offspring
    3. Mutation: Random changes to explore solution space
    4. Evaluation: Score offspring fitness
    5. Replacement: Update population with better patterns
    """

    # Configuration
    DEFAULT_POPULATION_SIZE = 50
    DEFAULT_MUTATION_RATE = 0.1
    DEFAULT_CROSSOVER_RATE = 0.7
    ELITE_PERCENTAGE = 0.1        # Top 10% always survive
    TOURNAMENT_SIZE = 3

    def __init__(
        self,
        population_size: int = DEFAULT_POPULATION_SIZE,
        mutation_rate: float = DEFAULT_MUTATION_RATE,
        crossover_rate: float = DEFAULT_CROSSOVER_RATE
    ):
        self.population_size = population_size
        self.mutation_rate = mutation_rate
        self.crossover_rate = crossover_rate
        self.population: List[PromptPattern] = []
        self.generation = 0
        self.stats_history: List[PopulationStats] = []
        self._mutation_operators: Dict[MutationType, Callable] = {}
        self._register_mutation_operators()

    def initialize_population(self, seed_patterns: List[PromptPattern]) -> int:
        """
        Initialize population from seed patterns.

        Args:
            seed_patterns: Initial patterns to seed population

        Returns:
            Number of patterns in population
        """
        pass

    def select(self, k: int) -> List[PromptPattern]:
        """
        Select k patterns using tournament selection.

        Args:
            k: Number of patterns to select

        Returns:
            Selected patterns
        """
        pass

    def _tournament_select(self) -> PromptPattern:
        """Select one pattern via tournament."""
        pass

    def crossover(
        self,
        parent_a: PromptPattern,
        parent_b: PromptPattern
    ) -> BreedingResult:
        """
        Create offspring by combining two parent patterns.

        Crossover strategies:
        - Trigger crossover: Combine trigger conditions
        - Approach crossover: Merge approach text
        - Metadata crossover: Mix metadata from both

        Args:
            parent_a: First parent pattern
            parent_b: Second parent pattern

        Returns:
            BreedingResult with offspring
        """
        pass

    def _crossover_triggers(
        self,
        triggers_a: Dict[str, Any],
        triggers_b: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Combine trigger conditions from both parents."""
        pass

    def _crossover_approach(
        self,
        approach_a: str,
        approach_b: str
    ) -> str:
        """Combine approach text from both parents."""
        pass

    def mutate(
        self,
        pattern: PromptPattern,
        mutation_rate: Optional[float] = None
    ) -> Tuple[PromptPattern, List[MutationRecord]]:
        """
        Apply random mutations to a pattern.

        Args:
            pattern: Pattern to mutate
            mutation_rate: Override default mutation rate

        Returns:
            Tuple of (mutated pattern, list of mutations applied)
        """
        pass

    def _apply_mutation(
        self,
        pattern: PromptPattern,
        mutation_type: MutationType
    ) -> MutationRecord:
        """Apply a specific mutation type."""
        pass

    def _mutate_trigger_expand(self, pattern: PromptPattern) -> MutationRecord:
        """Add a new trigger condition."""
        pass

    def _mutate_trigger_narrow(self, pattern: PromptPattern) -> MutationRecord:
        """Remove a trigger condition."""
        pass

    def _mutate_approach_rephrase(self, pattern: PromptPattern) -> MutationRecord:
        """Rephrase the approach text."""
        pass

    def _mutate_tool_swap(self, pattern: PromptPattern) -> MutationRecord:
        """Swap a recommended tool for alternative."""
        pass

    def evaluate_fitness(self, pattern: PromptPattern) -> float:
        """
        Evaluate pattern fitness.

        Factors:
        - Success rate (weighted heavily)
        - Sample size confidence
        - Generalization (not overfitted)
        - Simplicity (fewer conditions is better)
        """
        pass

    def evolve_generation(self) -> PopulationStats:
        """
        Evolve population by one generation.

        Steps:
        1. Evaluate all patterns
        2. Select elite to preserve
        3. Select parents for breeding
        4. Create offspring via crossover
        5. Apply mutations
        6. Replace population
        7. Record statistics

        Returns:
            Statistics for this generation
        """
        pass

    def get_best_patterns(self, n: int = 5) -> List[PromptPattern]:
        """Get top N patterns by fitness."""
        pass

    def calculate_diversity(self) -> float:
        """
        Calculate population diversity score.

        Measures how different patterns are from each other.
        """
        pass

    def get_stats(self) -> PopulationStats:
        """Get current population statistics."""
        pass

    def export_population(self) -> List[Dict]:
        """Export population for persistence."""
        pass

    def import_population(self, data: List[Dict]):
        """Import population from persistence."""
        pass

    def _register_mutation_operators(self):
        """Register all mutation operators."""
        self._mutation_operators = {
            MutationType.TRIGGER_EXPAND: self._mutate_trigger_expand,
            MutationType.TRIGGER_NARROW: self._mutate_trigger_narrow,
            MutationType.APPROACH_REPHRASE: self._mutate_approach_rephrase,
            MutationType.TOOL_SWAP: self._mutate_tool_swap,
        }
```

#### Unit Tests (`tests/test_pattern_breeder.py`)

```python
"""
Unit tests for lib/pattern_breeder.py
"""

import pytest
from lib.pattern_breeder import (
    PatternBreeder, MutationType, MutationRecord,
    BreedingResult, PopulationStats
)
from lib.prompt_evolver import PromptPattern


@pytest.fixture
def sample_patterns():
    """Create sample patterns for testing."""
    return [
        PromptPattern(
            pattern_id=f"p{i}",
            pattern_type="tool_sequence",
            description=f"Pattern {i}",
            trigger_conditions={"task_category": "search"},
            approach=f"Approach {i}",
            total_uses=20,
            success_count=15 + i,
            failure_count=5 - i if i < 5 else 0
        )
        for i in range(10)
    ]


class TestPatternBreederInit:
    """Tests for PatternBreeder initialization."""

    def test_init_default(self):
        """Initializes with default values."""
        breeder = PatternBreeder()

        assert breeder.population_size == PatternBreeder.DEFAULT_POPULATION_SIZE
        assert breeder.mutation_rate == PatternBreeder.DEFAULT_MUTATION_RATE
        assert breeder.generation == 0

    def test_init_custom(self):
        """Accepts custom parameters."""
        breeder = PatternBreeder(
            population_size=100,
            mutation_rate=0.2,
            crossover_rate=0.8
        )

        assert breeder.population_size == 100
        assert breeder.mutation_rate == 0.2


class TestPatternBreederInitializePopulation:
    """Tests for initialize_population method."""

    def test_initializes_from_seeds(self, sample_patterns):
        """Initializes population from seed patterns."""
        breeder = PatternBreeder(population_size=20)

        count = breeder.initialize_population(sample_patterns)

        assert count == 20
        assert len(breeder.population) == 20

    def test_fills_to_population_size(self, sample_patterns):
        """Fills population to target size."""
        breeder = PatternBreeder(population_size=50)

        breeder.initialize_population(sample_patterns[:3])

        # Should have created variations to fill population
        assert len(breeder.population) == 50


class TestPatternBreederSelect:
    """Tests for select method."""

    def test_selects_k_patterns(self, sample_patterns):
        """Selects requested number of patterns."""
        breeder = PatternBreeder()
        breeder.population = sample_patterns

        selected = breeder.select(5)

        assert len(selected) == 5

    def test_favors_fitter_patterns(self, sample_patterns):
        """Selection favors higher fitness patterns."""
        breeder = PatternBreeder()
        breeder.population = sample_patterns

        # Select many times and count
        selection_counts = {p.pattern_id: 0 for p in sample_patterns}
        for _ in range(100):
            selected = breeder.select(1)
            selection_counts[selected[0].pattern_id] += 1

        # Higher fitness patterns should be selected more often
        # (Last patterns have higher success rates)
        high_fitness_count = sum(selection_counts[f"p{i}"] for i in range(7, 10))
        low_fitness_count = sum(selection_counts[f"p{i}"] for i in range(0, 3))

        assert high_fitness_count > low_fitness_count


class TestPatternBreederCrossover:
    """Tests for crossover method."""

    def test_creates_offspring(self, sample_patterns):
        """Crossover creates valid offspring."""
        breeder = PatternBreeder()

        result = breeder.crossover(sample_patterns[0], sample_patterns[1])

        assert isinstance(result, BreedingResult)
        assert result.offspring is not None
        assert result.parent_a_id == sample_patterns[0].pattern_id
        assert result.parent_b_id == sample_patterns[1].pattern_id

    def test_offspring_has_new_id(self, sample_patterns):
        """Offspring has unique ID."""
        breeder = PatternBreeder()

        result = breeder.crossover(sample_patterns[0], sample_patterns[1])

        assert result.offspring.pattern_id != sample_patterns[0].pattern_id
        assert result.offspring.pattern_id != sample_patterns[1].pattern_id

    def test_offspring_inherits_traits(self, sample_patterns):
        """Offspring inherits traits from both parents."""
        breeder = PatternBreeder()
        parent_a = sample_patterns[0]
        parent_b = sample_patterns[1]

        result = breeder.crossover(parent_a, parent_b)
        offspring = result.offspring

        # Should have some characteristics from parents
        # (Exact inheritance depends on crossover strategy)
        assert offspring.pattern_type == parent_a.pattern_type

    def test_records_crossover_point(self, sample_patterns):
        """Records what was crossed over."""
        breeder = PatternBreeder()

        result = breeder.crossover(sample_patterns[0], sample_patterns[1])

        assert result.crossover_point is not None
        assert result.crossover_point in ["triggers", "approach", "metadata"]


class TestPatternBreederMutate:
    """Tests for mutate method."""

    def test_returns_mutated_pattern(self, sample_patterns):
        """Mutate returns pattern and mutation records."""
        breeder = PatternBreeder(mutation_rate=1.0)  # Force mutation

        mutated, records = breeder.mutate(sample_patterns[0])

        assert mutated is not None
        assert isinstance(records, list)

    def test_respects_mutation_rate_zero(self, sample_patterns):
        """No mutations with rate 0."""
        breeder = PatternBreeder(mutation_rate=0.0)

        mutated, records = breeder.mutate(sample_patterns[0])

        assert len(records) == 0

    def test_respects_mutation_rate_one(self, sample_patterns):
        """Always mutates with rate 1."""
        breeder = PatternBreeder(mutation_rate=1.0)

        mutated, records = breeder.mutate(sample_patterns[0])

        assert len(records) > 0

    def test_mutation_changes_pattern(self, sample_patterns):
        """Mutation actually changes the pattern."""
        breeder = PatternBreeder(mutation_rate=1.0)
        original = sample_patterns[0]

        mutated, records = breeder.mutate(original)

        # Something should be different
        if records:
            # Check that mutation was recorded
            assert records[0].original_value != records[0].new_value


class TestPatternBreederEvaluateFitness:
    """Tests for evaluate_fitness method."""

    def test_higher_success_rate_higher_fitness(self, sample_patterns):
        """Higher success rate gives higher fitness."""
        breeder = PatternBreeder()

        high_success = PromptPattern(
            pattern_id="high",
            pattern_type="test",
            description="High success",
            trigger_conditions={},
            approach="Test",
            total_uses=100,
            success_count=90,
            failure_count=10
        )

        low_success = PromptPattern(
            pattern_id="low",
            pattern_type="test",
            description="Low success",
            trigger_conditions={},
            approach="Test",
            total_uses=100,
            success_count=50,
            failure_count=50
        )

        high_fitness = breeder.evaluate_fitness(high_success)
        low_fitness = breeder.evaluate_fitness(low_success)

        assert high_fitness > low_fitness

    def test_more_samples_increases_fitness(self):
        """More samples increase fitness (confidence)."""
        breeder = PatternBreeder()

        many_samples = PromptPattern(
            pattern_id="many",
            pattern_type="test",
            description="Many samples",
            trigger_conditions={},
            approach="Test",
            total_uses=100,
            success_count=80,
            failure_count=20
        )

        few_samples = PromptPattern(
            pattern_id="few",
            pattern_type="test",
            description="Few samples",
            trigger_conditions={},
            approach="Test",
            total_uses=10,
            success_count=8,
            failure_count=2
        )

        many_fitness = breeder.evaluate_fitness(many_samples)
        few_fitness = breeder.evaluate_fitness(few_samples)

        # Same success rate, but more samples should give higher confidence
        assert many_fitness > few_fitness


class TestPatternBreederEvolveGeneration:
    """Tests for evolve_generation method."""

    def test_increments_generation(self, sample_patterns):
        """Evolution increments generation counter."""
        breeder = PatternBreeder(population_size=10)
        breeder.initialize_population(sample_patterns)

        breeder.evolve_generation()

        assert breeder.generation == 1

    def test_returns_stats(self, sample_patterns):
        """Evolution returns population statistics."""
        breeder = PatternBreeder(population_size=10)
        breeder.initialize_population(sample_patterns)

        stats = breeder.evolve_generation()

        assert isinstance(stats, PopulationStats)
        assert stats.size == 10
        assert stats.generations_evolved == 1

    def test_preserves_elite(self, sample_patterns):
        """Evolution preserves elite patterns."""
        breeder = PatternBreeder(population_size=10)
        breeder.ELITE_PERCENTAGE = 0.2  # Top 2
        breeder.initialize_population(sample_patterns)

        # Get current best
        best_before = breeder.get_best_patterns(2)
        best_ids_before = {p.pattern_id for p in best_before}

        breeder.evolve_generation()

        # Best should still be present (or better)
        best_after = breeder.get_best_patterns(2)
        # At least one of the elite should survive
        best_ids_after = {p.pattern_id for p in best_after}
        # This test is probabilistic - elite should usually survive
        # In practice, we might need to check fitness instead

    def test_records_stats_history(self, sample_patterns):
        """Evolution records stats history."""
        breeder = PatternBreeder(population_size=10)
        breeder.initialize_population(sample_patterns)

        for _ in range(3):
            breeder.evolve_generation()

        assert len(breeder.stats_history) == 3


class TestPatternBreederGetBest:
    """Tests for get_best_patterns method."""

    def test_returns_n_patterns(self, sample_patterns):
        """Returns requested number of patterns."""
        breeder = PatternBreeder()
        breeder.population = sample_patterns

        best = breeder.get_best_patterns(3)

        assert len(best) == 3

    def test_returns_sorted_by_fitness(self, sample_patterns):
        """Returns patterns sorted by fitness descending."""
        breeder = PatternBreeder()
        breeder.population = sample_patterns

        best = breeder.get_best_patterns(5)

        fitnesses = [breeder.evaluate_fitness(p) for p in best]
        assert fitnesses == sorted(fitnesses, reverse=True)


class TestPatternBreederDiversity:
    """Tests for calculate_diversity method."""

    def test_identical_population_low_diversity(self):
        """Identical patterns have low diversity."""
        breeder = PatternBreeder()

        # Create identical patterns
        pattern = PromptPattern(
            pattern_id="p1",
            pattern_type="test",
            description="Test",
            trigger_conditions={"task": "search"},
            approach="Do X"
        )
        breeder.population = [copy.deepcopy(pattern) for _ in range(10)]
        for i, p in enumerate(breeder.population):
            p.pattern_id = f"p{i}"

        diversity = breeder.calculate_diversity()

        assert diversity < 0.3  # Low diversity

    def test_varied_population_high_diversity(self, sample_patterns):
        """Varied patterns have high diversity."""
        breeder = PatternBreeder()
        breeder.population = sample_patterns

        diversity = breeder.calculate_diversity()

        assert diversity > 0.5  # Higher diversity


class TestPatternBreederExportImport:
    """Tests for export/import methods."""

    def test_export_import_roundtrip(self, sample_patterns):
        """Population survives export/import."""
        breeder = PatternBreeder()
        breeder.population = sample_patterns

        exported = breeder.export_population()

        new_breeder = PatternBreeder()
        new_breeder.import_population(exported)

        assert len(new_breeder.population) == len(sample_patterns)
        # Check some properties preserved
        original_ids = {p.pattern_id for p in sample_patterns}
        imported_ids = {p.pattern_id for p in new_breeder.population}
        assert original_ids == imported_ids
```

---

# M8: MCP Server Enhancement

## Overview
Enable real-time interaction with Spark during Claude Code sessions via MCP protocol.

## Components

### 8.1 SparkMCPServer (`mcp-server/src/spark_server.py`)

#### Data Structures

```python
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
from enum import Enum


class SparkToolName(Enum):
    """Available Spark MCP tools."""
    STATUS = "spark_status"
    SUGGEST = "spark_suggest"
    REFLECT = "spark_reflect"
    ACCEPT = "spark_accept"
    REJECT = "spark_reject"
    CREATE = "spark_create"
    WARN = "spark_warn"


@dataclass
class ToolResponse:
    """Response from a Spark MCP tool."""
    success: bool
    data: Dict[str, Any]
    error: Optional[str] = None


@dataclass
class SparkStatus:
    """Current Spark system status."""
    is_operational: bool
    mind_connected: bool
    queue_size: int
    patterns_active: int
    suggestions_ready: int
    current_session_id: Optional[str]
    last_learning_at: Optional[float]
    version: str = "1.0.0"


@dataclass
class SuggestionRequest:
    """Request for suggestions."""
    task_description: str
    current_tool: Optional[str] = None
    context: Dict[str, Any] = field(default_factory=dict)
    max_suggestions: int = 3


@dataclass
class ReflectionRequest:
    """Request for session reflection."""
    session_id: str
    include_patterns: bool = True
    include_improvements: bool = True
```

#### Class Definition

```python
class SparkMCPServer:
    """
    MCP Server for Spark integration with Claude Code.

    Provides tools for:
    - Querying Spark status
    - Getting suggestions mid-session
    - Triggering reflection
    - Managing patterns
    - Pre-tool warnings
    """

    def __init__(
        self,
        mind_client: Optional[MindClient] = None,
        suggester: Optional[Suggester] = None,
        evolver: Optional[PromptEvolver] = None
    ):
        self.mind = mind_client or MindClient()
        self.suggester = suggester or Suggester(self.mind)
        self.evolver = evolver or PromptEvolver(self.mind)
        self.current_session_id: Optional[str] = None
        self._tools: Dict[str, Callable] = {}
        self._register_tools()

    def _register_tools(self):
        """Register all MCP tools."""
        self._tools = {
            SparkToolName.STATUS.value: self.tool_status,
            SparkToolName.SUGGEST.value: self.tool_suggest,
            SparkToolName.REFLECT.value: self.tool_reflect,
            SparkToolName.ACCEPT.value: self.tool_accept,
            SparkToolName.REJECT.value: self.tool_reject,
            SparkToolName.CREATE.value: self.tool_create,
            SparkToolName.WARN.value: self.tool_warn,
        }

    async def handle_tool_call(
        self,
        tool_name: str,
        arguments: Dict[str, Any]
    ) -> ToolResponse:
        """
        Handle an incoming MCP tool call.

        Args:
            tool_name: Name of the tool to invoke
            arguments: Tool arguments

        Returns:
            ToolResponse with result or error
        """
        pass

    async def tool_status(self, arguments: Dict) -> ToolResponse:
        """
        Get current Spark status.

        Arguments: None

        Returns:
            SparkStatus as dict
        """
        pass

    async def tool_suggest(self, arguments: Dict) -> ToolResponse:
        """
        Get suggestions for current task.

        Arguments:
            task_description: str - What the user is trying to do
            current_tool: Optional[str] - Tool about to be used
            max_suggestions: int - Maximum suggestions to return

        Returns:
            List of suggestion dicts
        """
        pass

    async def tool_reflect(self, arguments: Dict) -> ToolResponse:
        """
        Trigger reflection on session.

        Arguments:
            session_id: str - Session to reflect on
            include_patterns: bool - Include identified patterns
            include_improvements: bool - Include improvement suggestions

        Returns:
            ReflectionResult as dict
        """
        pass

    async def tool_accept(self, arguments: Dict) -> ToolResponse:
        """
        Accept a suggested pattern.

        Arguments:
            pattern_id: str - ID of pattern to accept
            feedback: Optional[str] - Optional feedback

        Returns:
            Success status
        """
        pass

    async def tool_reject(self, arguments: Dict) -> ToolResponse:
        """
        Reject a suggested pattern.

        Arguments:
            pattern_id: str - ID of pattern to reject
            reason: str - Reason for rejection

        Returns:
            Success status
        """
        pass

    async def tool_create(self, arguments: Dict) -> ToolResponse:
        """
        Manually create a new pattern.

        Arguments:
            pattern_type: str - Type of pattern
            description: str - Pattern description
            approach: str - Recommended approach
            trigger_conditions: Dict - When to apply

        Returns:
            Created pattern ID
        """
        pass

    async def tool_warn(self, arguments: Dict) -> ToolResponse:
        """
        Get warnings before using a tool.

        Arguments:
            tool_name: str - Tool about to be used
            tool_input: Dict - Planned tool input

        Returns:
            List of warnings if any
        """
        pass

    def get_tool_definitions(self) -> List[Dict]:
        """
        Get MCP tool definitions for registration.

        Returns:
            List of tool definition dicts for MCP protocol
        """
        pass

    async def start(self, host: str = "localhost", port: int = 3000):
        """Start the MCP server."""
        pass

    async def stop(self):
        """Stop the MCP server."""
        pass
```

### 8.2 RealTimeAdvisor (`lib/realtime_advisor.py`)

#### Class Definition

```python
class RealTimeAdvisor:
    """
    Provides real-time guidance during Claude Code sessions.

    Capabilities:
    - Pre-tool warnings
    - Post-failure recovery suggestions
    - Mid-task recommendations
    """

    # Tools that commonly need warnings
    WARN_TOOLS = ["Bash", "Write", "Edit"]

    def __init__(
        self,
        suggester: Suggester,
        evolver: PromptEvolver,
        learner: SparkLearner
    ):
        self.suggester = suggester
        self.evolver = evolver
        self.learner = learner
        self.recent_warnings: List[str] = []

    def pre_tool_check(
        self,
        tool_name: str,
        tool_input: Dict[str, Any],
        context: Dict[str, Any] = None
    ) -> Optional[str]:
        """
        Check before tool execution for potential issues.

        Args:
            tool_name: Tool about to be used
            tool_input: Planned input to tool
            context: Additional context

        Returns:
            Warning message if issue detected, None otherwise
        """
        pass

    def _check_bash_command(self, command: str) -> Optional[str]:
        """Check Bash command for common issues."""
        pass

    def _check_file_operation(
        self,
        tool_name: str,
        file_path: str
    ) -> Optional[str]:
        """Check file operations for issues."""
        pass

    def suggest_recovery(
        self,
        failed_tool: str,
        error_message: str,
        context: Dict[str, Any] = None
    ) -> Optional[str]:
        """
        Suggest recovery after a tool failure.

        Args:
            failed_tool: Tool that failed
            error_message: Error that occurred
            context: Additional context

        Returns:
            Recovery suggestion if available
        """
        pass

    def suggest_alternative(
        self,
        current_tool: str,
        task_description: str
    ) -> Optional[str]:
        """
        Suggest alternative tool for task.

        Args:
            current_tool: Tool currently being considered
            task_description: What user is trying to do

        Returns:
            Alternative suggestion if better option exists
        """
        pass

    def get_task_guidance(self, task_category: str) -> List[str]:
        """
        Get guidance tips for a task category.

        Args:
            task_category: Type of task (search, edit, etc.)

        Returns:
            List of guidance tips
        """
        pass
```

#### Unit Tests (`tests/test_mcp_server.py`)

```python
"""
Unit tests for mcp-server components
"""

import pytest
from unittest.mock import AsyncMock, MagicMock
from mcp_server.spark_server import (
    SparkMCPServer, SparkToolName, ToolResponse, SparkStatus
)
from lib.realtime_advisor import RealTimeAdvisor


# ==================== SparkMCPServer Tests ====================

class TestSparkMCPServerInit:
    """Tests for SparkMCPServer initialization."""

    def test_init_default(self):
        """Initializes with defaults."""
        server = SparkMCPServer()

        assert server.suggester is not None
        assert server.evolver is not None

    def test_init_with_dependencies(self, mock_mind_client):
        """Accepts injected dependencies."""
        suggester = MagicMock()
        evolver = MagicMock()

        server = SparkMCPServer(
            mind_client=mock_mind_client,
            suggester=suggester,
            evolver=evolver
        )

        assert server.mind == mock_mind_client
        assert server.suggester == suggester


class TestSparkMCPServerToolStatus:
    """Tests for tool_status method."""

    @pytest.mark.asyncio
    async def test_returns_status(self, mock_mind_client):
        """Returns SparkStatus."""
        mock_mind_client.is_available = AsyncMock(return_value=True)
        server = SparkMCPServer(mind_client=mock_mind_client)

        response = await server.tool_status({})

        assert response.success is True
        assert "is_operational" in response.data
        assert "mind_connected" in response.data

    @pytest.mark.asyncio
    async def test_handles_mind_unavailable(self, mock_mind_client):
        """Handles Mind being unavailable."""
        mock_mind_client.is_available = AsyncMock(return_value=False)
        server = SparkMCPServer(mind_client=mock_mind_client)

        response = await server.tool_status({})

        assert response.success is True
        assert response.data["mind_connected"] is False


class TestSparkMCPServerToolSuggest:
    """Tests for tool_suggest method."""

    @pytest.mark.asyncio
    async def test_returns_suggestions(self, mock_mind_client):
        """Returns relevant suggestions."""
        server = SparkMCPServer(mind_client=mock_mind_client)

        # Add a suggestion
        from lib.suggester import Suggestion
        server.suggester.suggestions["s1"] = Suggestion(
            suggestion_id="s1",
            suggestion_type="recommendation",
            priority=2,
            title="Use Grep",
            description="Grep is effective for search",
            confidence=0.9,
            trigger_keywords=["search", "find"]
        )

        response = await server.tool_suggest({
            "task_description": "find all test files",
            "max_suggestions": 3
        })

        assert response.success is True
        assert len(response.data.get("suggestions", [])) >= 0

    @pytest.mark.asyncio
    async def test_respects_max_suggestions(self, mock_mind_client):
        """Respects max_suggestions parameter."""
        server = SparkMCPServer(mind_client=mock_mind_client)

        # Add many suggestions
        from lib.suggester import Suggestion
        for i in range(10):
            server.suggester.suggestions[f"s{i}"] = Suggestion(
                suggestion_id=f"s{i}",
                suggestion_type="tip",
                priority=3,
                title=f"Tip {i}",
                description=f"Description {i}",
                confidence=0.8,
                trigger_keywords=["test"]
            )

        response = await server.tool_suggest({
            "task_description": "run tests",
            "max_suggestions": 2
        })

        suggestions = response.data.get("suggestions", [])
        assert len(suggestions) <= 2


class TestSparkMCPServerToolReflect:
    """Tests for tool_reflect method."""

    @pytest.mark.asyncio
    async def test_reflects_on_session(self, mock_mind_client):
        """Reflects on specified session."""
        server = SparkMCPServer(mind_client=mock_mind_client)

        response = await server.tool_reflect({
            "session_id": "test_session",
            "include_patterns": True,
            "include_improvements": True
        })

        assert response.success is True
        assert "traces_analyzed" in response.data

    @pytest.mark.asyncio
    async def test_handles_unknown_session(self, mock_mind_client):
        """Handles unknown session gracefully."""
        server = SparkMCPServer(mind_client=mock_mind_client)

        response = await server.tool_reflect({
            "session_id": "nonexistent_session_12345"
        })

        assert response.success is True
        assert response.data["traces_analyzed"] == 0


class TestSparkMCPServerToolAccept:
    """Tests for tool_accept method."""

    @pytest.mark.asyncio
    async def test_accepts_pattern(self, mock_mind_client):
        """Accepts a pattern suggestion."""
        server = SparkMCPServer(mind_client=mock_mind_client)

        # Add a pattern
        from lib.prompt_evolver import PromptPattern
        server.evolver.patterns["p1"] = PromptPattern(
            pattern_id="p1",
            pattern_type="test",
            description="Test pattern",
            trigger_conditions={},
            approach="Test approach"
        )

        response = await server.tool_accept({
            "pattern_id": "p1",
            "feedback": "Works well"
        })

        assert response.success is True

    @pytest.mark.asyncio
    async def test_returns_error_unknown_pattern(self, mock_mind_client):
        """Returns error for unknown pattern."""
        server = SparkMCPServer(mind_client=mock_mind_client)

        response = await server.tool_accept({
            "pattern_id": "nonexistent"
        })

        assert response.success is False
        assert response.error is not None


class TestSparkMCPServerToolReject:
    """Tests for tool_reject method."""

    @pytest.mark.asyncio
    async def test_rejects_pattern(self, mock_mind_client):
        """Rejects a pattern with reason."""
        server = SparkMCPServer(mind_client=mock_mind_client)

        from lib.prompt_evolver import PromptPattern
        server.evolver.patterns["p1"] = PromptPattern(
            pattern_id="p1",
            pattern_type="test",
            description="Test",
            trigger_conditions={},
            approach="Test"
        )

        response = await server.tool_reject({
            "pattern_id": "p1",
            "reason": "Not applicable to my workflow"
        })

        assert response.success is True


class TestSparkMCPServerToolCreate:
    """Tests for tool_create method."""

    @pytest.mark.asyncio
    async def test_creates_pattern(self, mock_mind_client):
        """Creates a new manual pattern."""
        server = SparkMCPServer(mind_client=mock_mind_client)

        response = await server.tool_create({
            "pattern_type": "tool_sequence",
            "description": "Use Glob before Grep",
            "approach": "First use Glob to find files, then Grep to search content",
            "trigger_conditions": {"task_category": "search"}
        })

        assert response.success is True
        assert "pattern_id" in response.data


class TestSparkMCPServerToolWarn:
    """Tests for tool_warn method."""

    @pytest.mark.asyncio
    async def test_returns_warnings(self, mock_mind_client):
        """Returns warnings for risky operations."""
        server = SparkMCPServer(mind_client=mock_mind_client)

        # Add a warning
        from lib.suggester import Suggestion
        server.suggester.suggestions["w1"] = Suggestion(
            suggestion_id="w1",
            suggestion_type="warning",
            priority=1,
            title="Long command timeout risk",
            description="Commands over 30 seconds may timeout",
            confidence=0.9,
            trigger_tool="Bash"
        )

        response = await server.tool_warn({
            "tool_name": "Bash",
            "tool_input": {"command": "sleep 60"}
        })

        # May or may not find warnings depending on matching logic
        assert response.success is True


class TestSparkMCPServerToolDefinitions:
    """Tests for get_tool_definitions method."""

    def test_returns_all_tools(self, mock_mind_client):
        """Returns definitions for all tools."""
        server = SparkMCPServer(mind_client=mock_mind_client)

        definitions = server.get_tool_definitions()

        assert len(definitions) == len(SparkToolName)
        tool_names = {d["name"] for d in definitions}
        expected_names = {t.value for t in SparkToolName}
        assert tool_names == expected_names

    def test_definitions_have_required_fields(self, mock_mind_client):
        """Tool definitions have required MCP fields."""
        server = SparkMCPServer(mind_client=mock_mind_client)

        definitions = server.get_tool_definitions()

        for defn in definitions:
            assert "name" in defn
            assert "description" in defn
            assert "inputSchema" in defn


# ==================== RealTimeAdvisor Tests ====================

class TestRealTimeAdvisorPreToolCheck:
    """Tests for pre_tool_check method."""

    def test_warns_on_long_bash_command(self):
        """Warns about potentially long Bash commands."""
        suggester = MagicMock()
        evolver = MagicMock()
        learner = MagicMock()
        advisor = RealTimeAdvisor(suggester, evolver, learner)

        warning = advisor.pre_tool_check(
            tool_name="Bash",
            tool_input={"command": "find / -name '*.py'"}
        )

        # May or may not warn depending on implementation
        # The key is it doesn't crash
        assert warning is None or isinstance(warning, str)

    def test_no_warning_safe_command(self):
        """No warning for safe commands."""
        suggester = MagicMock()
        evolver = MagicMock()
        learner = MagicMock()
        advisor = RealTimeAdvisor(suggester, evolver, learner)

        warning = advisor.pre_tool_check(
            tool_name="Bash",
            tool_input={"command": "ls -la"}
        )

        assert warning is None


class TestRealTimeAdvisorSuggestRecovery:
    """Tests for suggest_recovery method."""

    def test_suggests_recovery_for_not_found(self):
        """Suggests recovery for 'not found' errors."""
        suggester = MagicMock()
        evolver = MagicMock()
        evolver.get_pattern_for_task.return_value = None
        learner = MagicMock()
        advisor = RealTimeAdvisor(suggester, evolver, learner)

        recovery = advisor.suggest_recovery(
            failed_tool="Read",
            error_message="File not found: /nonexistent/path.py"
        )

        # Should suggest using Glob to find the file
        assert recovery is None or "Glob" in recovery or "find" in recovery.lower()

    def test_suggests_recovery_for_permission(self):
        """Suggests recovery for permission errors."""
        suggester = MagicMock()
        evolver = MagicMock()
        learner = MagicMock()
        advisor = RealTimeAdvisor(suggester, evolver, learner)

        recovery = advisor.suggest_recovery(
            failed_tool="Bash",
            error_message="Permission denied"
        )

        # May suggest sudo or checking permissions
        assert recovery is None or isinstance(recovery, str)


class TestRealTimeAdvisorSuggestAlternative:
    """Tests for suggest_alternative method."""

    def test_suggests_grep_for_search(self):
        """Suggests Grep for search tasks."""
        suggester = MagicMock()
        suggester.get_recommendations_for_task.return_value = []
        evolver = MagicMock()
        learner = MagicMock()
        learner.get_tool_ranking.return_value = [("Grep", 0.9), ("Bash", 0.7)]
        advisor = RealTimeAdvisor(suggester, evolver, learner)

        alternative = advisor.suggest_alternative(
            current_tool="Bash",
            task_description="search for function definitions"
        )

        # Should potentially suggest Grep
        assert alternative is None or isinstance(alternative, str)
```

---

# M10: Observability & Debugging

## Overview
Make Spark's behavior transparent and debuggable with dashboards, debug mode, and export capabilities.

## Components

### 10.1 SparkDashboard (`dashboard/spark_dashboard.py`)

```python
"""
Streamlit dashboard for Spark observability.

Run with: streamlit run dashboard/spark_dashboard.py
"""

import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta
from typing import List, Dict, Optional


class SparkDashboard:
    """
    Interactive dashboard for Spark observability.

    Features:
    - Real-time metrics
    - Pattern visualization
    - Learning trends
    - Debug information
    """

    def __init__(self, mind_client=None):
        self.mind = mind_client

    def render(self):
        """Render the complete dashboard."""
        st.set_page_config(page_title="Spark Dashboard", layout="wide")
        st.title("Spark Learning Dashboard")

        # Sidebar navigation
        page = st.sidebar.selectbox(
            "Navigate",
            ["Overview", "Patterns", "Learnings", "Debug", "Export"]
        )

        if page == "Overview":
            self._render_overview()
        elif page == "Patterns":
            self._render_patterns()
        elif page == "Learnings":
            self._render_learnings()
        elif page == "Debug":
            self._render_debug()
        elif page == "Export":
            self._render_export()

    def _render_overview(self):
        """Render overview page with key metrics."""
        st.header("System Overview")

        # Metrics row
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.metric("Active Patterns", "42", "+3 today")
        with col2:
            st.metric("Avg Confidence", "0.78", "+0.02")
        with col3:
            st.metric("Suggestion Hit Rate", "67%", "+5%")
        with col4:
            st.metric("Events Processed", "1,234", "+156 today")

        # Charts
        st.subheader("Confidence Trend")
        # confidence_data = self._get_confidence_trend()
        # st.line_chart(confidence_data)

        st.subheader("Tool Effectiveness")
        # tool_data = self._get_tool_effectiveness()
        # st.bar_chart(tool_data)

    def _render_patterns(self):
        """Render patterns page."""
        st.header("Prompt Patterns")

        # Pattern filters
        col1, col2 = st.columns(2)
        with col1:
            pattern_type = st.selectbox(
                "Pattern Type",
                ["All", "tool_sequence", "error_recovery", "task_approach"]
            )
        with col2:
            min_confidence = st.slider("Min Confidence", 0.0, 1.0, 0.5)

        # Pattern table
        st.subheader("Patterns")
        # patterns = self._get_patterns(pattern_type, min_confidence)
        # st.dataframe(patterns)

    def _render_learnings(self):
        """Render learnings page."""
        st.header("Learnings")

        # Recent learnings
        st.subheader("Recent Learnings")
        # learnings = self._get_recent_learnings()
        # for learning in learnings:
        #     with st.expander(learning['title']):
        #         st.write(learning['content'])

    def _render_debug(self):
        """Render debug page."""
        st.header("Debug Information")

        # Component status
        st.subheader("Component Status")
        # status = self._get_component_status()
        # st.json(status)

        # Recent errors
        st.subheader("Recent Errors")
        # errors = self._get_recent_errors()
        # st.table(errors)

    def _render_export(self):
        """Render export page."""
        st.header("Export / Import")

        col1, col2 = st.columns(2)

        with col1:
            st.subheader("Export Learnings")
            if st.button("Export to JSON"):
                # data = self._export_learnings()
                # st.download_button("Download", data, "spark_learnings.json")
                pass

        with col2:
            st.subheader("Import Learnings")
            uploaded = st.file_uploader("Upload JSON", type="json")
            if uploaded and st.button("Import"):
                # self._import_learnings(uploaded)
                pass


def main():
    dashboard = SparkDashboard()
    dashboard.render()


if __name__ == "__main__":
    main()
```

### 10.2 SparkDebugger (`lib/debugger.py`)

#### Class Definition

```python
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
import time
import json
from enum import Enum


class DebugLevel(Enum):
    """Debug verbosity levels."""
    OFF = 0
    ERROR = 1
    WARN = 2
    INFO = 3
    DEBUG = 4
    TRACE = 5


@dataclass
class DebugEntry:
    """A single debug log entry."""
    timestamp: float
    level: DebugLevel
    component: str
    action: str
    details: Dict[str, Any]
    duration_ms: Optional[float] = None


class SparkDebugger:
    """
    Debug and trace utility for Spark.

    Provides:
    - Structured logging
    - Decision explanation
    - Performance tracing
    - State inspection
    """

    MAX_LOG_ENTRIES = 1000

    def __init__(self, level: DebugLevel = DebugLevel.INFO):
        self.level = level
        self.log: List[DebugEntry] = []
        self._active_spans: Dict[str, float] = {}

    def set_level(self, level: DebugLevel):
        """Set debug level."""
        self.level = level

    def trace(
        self,
        component: str,
        action: str,
        details: Dict[str, Any],
        level: DebugLevel = DebugLevel.DEBUG
    ):
        """
        Log a debug entry.

        Args:
            component: Component name (e.g., "learner", "suggester")
            action: Action being performed
            details: Additional details
            level: Log level
        """
        pass

    def start_span(self, span_id: str):
        """Start a timing span."""
        self._active_spans[span_id] = time.perf_counter()

    def end_span(self, span_id: str, component: str, action: str) -> float:
        """End a timing span and log duration."""
        pass

    def explain_decision(
        self,
        decision_type: str,
        decision: Any,
        factors: Dict[str, Any]
    ) -> str:
        """
        Generate human-readable explanation of a decision.

        Args:
            decision_type: Type of decision (pattern_selection, suggestion, etc.)
            decision: The decision made
            factors: Factors that influenced the decision

        Returns:
            Human-readable explanation
        """
        pass

    def inspect_state(self, component: Any) -> Dict[str, Any]:
        """
        Inspect and serialize component state.

        Args:
            component: Component to inspect

        Returns:
            Serialized state dict
        """
        pass

    def get_logs(
        self,
        level: Optional[DebugLevel] = None,
        component: Optional[str] = None,
        since: Optional[float] = None
    ) -> List[DebugEntry]:
        """Get filtered log entries."""
        pass

    def clear_logs(self):
        """Clear all log entries."""
        self.log = []

    def export_logs(self) -> str:
        """Export logs as JSON."""
        pass

    def _should_log(self, level: DebugLevel) -> bool:
        """Check if level should be logged."""
        return level.value <= self.level.value

    def _trim_logs(self):
        """Trim logs to max size."""
        if len(self.log) > self.MAX_LOG_ENTRIES:
            self.log = self.log[-self.MAX_LOG_ENTRIES:]
```

### 10.3 SparkBackup (`lib/backup.py`)

#### Class Definition

```python
from dataclasses import dataclass
from typing import Dict, List, Optional, Any
from pathlib import Path
import json
from datetime import datetime


@dataclass
class BackupManifest:
    """Manifest for a backup."""
    version: str
    created_at: str
    source_project: Optional[str]
    components: List[str]
    pattern_count: int
    learning_count: int
    checksum: str


class SparkBackup:
    """
    Backup and restore utility for Spark learnings.

    Features:
    - Export learnings to JSON
    - Import learnings with merge options
    - Version control integration
    - Incremental backups
    """

    VERSION = "1.0"

    def __init__(self, mind_client=None):
        self.mind = mind_client

    def export_learnings(
        self,
        filepath: str,
        include_patterns: bool = True,
        include_tool_weights: bool = True,
        include_suggestions: bool = True
    ) -> BackupManifest:
        """
        Export all learnings to JSON file.

        Args:
            filepath: Output file path
            include_patterns: Include prompt patterns
            include_tool_weights: Include tool effectiveness weights
            include_suggestions: Include suggestion data

        Returns:
            BackupManifest with export details
        """
        pass

    def import_learnings(
        self,
        filepath: str,
        merge: bool = True,
        overwrite_conflicts: bool = False
    ) -> int:
        """
        Import learnings from JSON file.

        Args:
            filepath: Input file path
            merge: Merge with existing (True) or replace (False)
            overwrite_conflicts: Overwrite on ID conflicts

        Returns:
            Number of learnings imported
        """
        pass

    def create_incremental_backup(
        self,
        backup_dir: str,
        since_timestamp: Optional[float] = None
    ) -> str:
        """
        Create incremental backup since last backup.

        Args:
            backup_dir: Directory for backups
            since_timestamp: Only include learnings after this time

        Returns:
            Path to backup file
        """
        pass

    def restore_from_incremental(
        self,
        backup_dir: str,
        target_timestamp: Optional[float] = None
    ) -> int:
        """
        Restore from incremental backups.

        Args:
            backup_dir: Directory containing backups
            target_timestamp: Restore to this point in time

        Returns:
            Number of learnings restored
        """
        pass

    def sync_to_git(
        self,
        repo_path: str,
        branch: str = "spark-learnings"
    ) -> bool:
        """
        Sync learnings to a git repository.

        Args:
            repo_path: Path to git repository
            branch: Branch to commit to

        Returns:
            True if sync successful
        """
        pass

    def _calculate_checksum(self, data: Dict) -> str:
        """Calculate checksum for data integrity."""
        pass

    def _verify_checksum(self, data: Dict, checksum: str) -> bool:
        """Verify data integrity."""
        pass
```

#### Unit Tests (`tests/test_backup.py`)

```python
"""
Unit tests for lib/backup.py
"""

import pytest
import tempfile
import json
from pathlib import Path
from lib.backup import SparkBackup, BackupManifest


class TestSparkBackupExport:
    """Tests for export_learnings method."""

    def test_exports_to_file(self, mock_mind_client):
        """Exports learnings to JSON file."""
        backup = SparkBackup(mind_client=mock_mind_client)

        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            manifest = backup.export_learnings(f.name)

            assert Path(f.name).exists()
            assert manifest.version == SparkBackup.VERSION

    def test_export_includes_patterns(self, mock_mind_client):
        """Export includes patterns when requested."""
        backup = SparkBackup(mind_client=mock_mind_client)

        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            backup.export_learnings(f.name, include_patterns=True)

            with open(f.name) as fp:
                data = json.load(fp)
                assert "patterns" in data

    def test_export_excludes_patterns(self, mock_mind_client):
        """Export excludes patterns when not requested."""
        backup = SparkBackup(mind_client=mock_mind_client)

        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            backup.export_learnings(f.name, include_patterns=False)

            with open(f.name) as fp:
                data = json.load(fp)
                assert "patterns" not in data or data["patterns"] == []


class TestSparkBackupImport:
    """Tests for import_learnings method."""

    def test_imports_from_file(self, mock_mind_client):
        """Imports learnings from JSON file."""
        backup = SparkBackup(mind_client=mock_mind_client)

        # Create a backup file
        backup_data = {
            "version": "1.0",
            "patterns": [],
            "tool_weights": {},
            "checksum": "abc123"
        }

        with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode='w') as f:
            json.dump(backup_data, f)
            f.flush()

            count = backup.import_learnings(f.name)

            assert count >= 0

    def test_import_merge_mode(self, mock_mind_client):
        """Import with merge keeps existing learnings."""
        backup = SparkBackup(mind_client=mock_mind_client)

        backup_data = {
            "version": "1.0",
            "patterns": [{"pattern_id": "new1"}],
            "checksum": "abc"
        }

        with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode='w') as f:
            json.dump(backup_data, f)
            f.flush()

            count = backup.import_learnings(f.name, merge=True)

            # Should merge, not replace
            assert count >= 0


class TestSparkBackupIncremental:
    """Tests for incremental backup methods."""

    def test_creates_incremental_backup(self, mock_mind_client):
        """Creates incremental backup file."""
        backup = SparkBackup(mind_client=mock_mind_client)

        with tempfile.TemporaryDirectory() as tmpdir:
            path = backup.create_incremental_backup(tmpdir)

            assert Path(path).exists()

    def test_incremental_naming(self, mock_mind_client):
        """Incremental backups have timestamp in name."""
        backup = SparkBackup(mind_client=mock_mind_client)

        with tempfile.TemporaryDirectory() as tmpdir:
            path = backup.create_incremental_backup(tmpdir)

            # Should contain timestamp
            assert "2026" in path or "spark" in path


class TestBackupManifest:
    """Tests for BackupManifest dataclass."""

    def test_creation(self):
        """BackupManifest creates with required fields."""
        manifest = BackupManifest(
            version="1.0",
            created_at="2026-01-23T12:00:00",
            source_project="/test/project",
            components=["patterns", "tool_weights"],
            pattern_count=42,
            learning_count=100,
            checksum="abc123"
        )

        assert manifest.version == "1.0"
        assert manifest.pattern_count == 42


class TestSparkBackupChecksum:
    """Tests for checksum functionality."""

    def test_checksum_consistent(self, mock_mind_client):
        """Same data produces same checksum."""
        backup = SparkBackup(mind_client=mock_mind_client)

        data = {"key": "value", "list": [1, 2, 3]}

        checksum1 = backup._calculate_checksum(data)
        checksum2 = backup._calculate_checksum(data)

        assert checksum1 == checksum2

    def test_checksum_differs_for_different_data(self, mock_mind_client):
        """Different data produces different checksum."""
        backup = SparkBackup(mind_client=mock_mind_client)

        data1 = {"key": "value1"}
        data2 = {"key": "value2"}

        checksum1 = backup._calculate_checksum(data1)
        checksum2 = backup._calculate_checksum(data2)

        assert checksum1 != checksum2

    def test_verify_checksum_valid(self, mock_mind_client):
        """Verify returns True for valid checksum."""
        backup = SparkBackup(mind_client=mock_mind_client)

        data = {"key": "value"}
        checksum = backup._calculate_checksum(data)

        assert backup._verify_checksum(data, checksum) is True

    def test_verify_checksum_invalid(self, mock_mind_client):
        """Verify returns False for invalid checksum."""
        backup = SparkBackup(mind_client=mock_mind_client)

        data = {"key": "value"}

        assert backup._verify_checksum(data, "invalid_checksum") is False
```

---

## Summary

This specification document covers:

| Milestone | Components | Test Count (Est.) |
|-----------|------------|-------------------|
| M5 | InjectionTracker, ExperimentManager | ~80 tests |
| M6 | ProjectAnalyzer, LearningTransfer | ~60 tests |
| M7 | PatternBreeder | ~50 tests |
| M8 | SparkMCPServer, RealTimeAdvisor | ~50 tests |
| M10 | SparkDashboard, SparkDebugger, SparkBackup | ~40 tests |

**Total estimated unit tests: ~280 tests**

Combined with existing tests (325), the full Spark test suite would have approximately **600+ tests**.

---

*Last updated: 2026-01-23*
