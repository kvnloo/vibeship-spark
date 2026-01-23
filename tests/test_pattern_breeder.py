"""
Unit tests for lib/pattern_breeder.py
"""

import pytest
import copy
from lib.pattern_breeder import (
    PatternBreeder, MutationType, MutationRecord,
    BreedingResult, PopulationStats
)
from lib.prompt_evolver import PromptPattern


@pytest.fixture
def sample_patterns():
    """Create sample patterns for testing."""
    patterns = []
    for i in range(10):
        # Ensure success_count + failure_count = total_uses
        total_uses = 20
        success_count = 10 + i  # 10 to 19
        failure_count = total_uses - success_count  # 10 to 1
        patterns.append(
            PromptPattern(
                pattern_id=f"p{i}",
                pattern_type="tool_sequence",
                description=f"Pattern {i}",
                trigger_conditions={"task_category": "search"},
                approach=f"Approach {i} for searching",
                tool_sequence=["Grep", "Read"],
                total_uses=total_uses,
                success_count=success_count,
                failure_count=failure_count
            )
        )
    return patterns


@pytest.fixture
def breeder():
    """Create a default breeder."""
    return PatternBreeder()


class TestPatternBreederInit:
    """Tests for PatternBreeder initialization."""

    def test_init_default(self):
        """Initializes with default values."""
        breeder = PatternBreeder()

        assert breeder.population_size == PatternBreeder.DEFAULT_POPULATION_SIZE
        assert breeder.mutation_rate == PatternBreeder.DEFAULT_MUTATION_RATE
        assert breeder.generation == 0
        assert len(breeder.population) == 0

    def test_init_custom(self):
        """Accepts custom parameters."""
        breeder = PatternBreeder(
            population_size=100,
            mutation_rate=0.2,
            crossover_rate=0.8
        )

        assert breeder.population_size == 100
        assert breeder.mutation_rate == 0.2
        assert breeder.crossover_rate == 0.8


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

    def test_handles_empty_seeds(self):
        """Handles empty seed list."""
        breeder = PatternBreeder(population_size=10)

        count = breeder.initialize_population([])

        assert count == 0
        assert len(breeder.population) == 0

    def test_resets_generation(self, sample_patterns):
        """Resets generation counter on initialization."""
        breeder = PatternBreeder(population_size=10)
        breeder.generation = 5

        breeder.initialize_population(sample_patterns)

        assert breeder.generation == 0


class TestPatternBreederSelect:
    """Tests for select method."""

    def test_selects_k_patterns(self, sample_patterns):
        """Selects requested number of patterns."""
        breeder = PatternBreeder()
        breeder.population = sample_patterns

        selected = breeder.select(5)

        assert len(selected) == 5

    def test_returns_copies(self, sample_patterns):
        """Returns copies, not originals."""
        breeder = PatternBreeder()
        breeder.population = sample_patterns

        selected = breeder.select(1)

        # Modify selected pattern
        selected[0].approach = "Modified"

        # Original should be unchanged
        assert sample_patterns[0].approach != "Modified"

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
        # Last patterns have higher success rates (more successes, fewer failures)
        high_fitness_count = sum(selection_counts[f"p{i}"] for i in range(7, 10))
        low_fitness_count = sum(selection_counts[f"p{i}"] for i in range(0, 3))

        assert high_fitness_count > low_fitness_count

    def test_raises_on_empty_population(self):
        """Raises error when selecting from empty population."""
        breeder = PatternBreeder()

        with pytest.raises(ValueError):
            breeder.select(1)


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

        # Should have same pattern type as parent
        assert offspring.pattern_type == parent_a.pattern_type

    def test_records_crossover_point(self, sample_patterns):
        """Records what was crossed over."""
        breeder = PatternBreeder()

        result = breeder.crossover(sample_patterns[0], sample_patterns[1])

        assert result.crossover_point is not None
        assert result.crossover_point in ["triggers", "approach", "metadata"]

    def test_offspring_generation_increments(self, sample_patterns):
        """Offspring has incremented generation."""
        breeder = PatternBreeder()
        sample_patterns[0].generation = 2
        sample_patterns[1].generation = 3

        result = breeder.crossover(sample_patterns[0], sample_patterns[1])

        assert result.offspring.generation == 4  # max(2, 3) + 1


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

        # Should have at least one mutation
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

    def test_original_unchanged(self, sample_patterns):
        """Original pattern is not modified."""
        breeder = PatternBreeder(mutation_rate=1.0)
        original = sample_patterns[0]
        original_approach = original.approach

        breeder.mutate(original)

        assert original.approach == original_approach


class TestMutationTypes:
    """Tests for specific mutation operations."""

    def test_trigger_expand(self, sample_patterns):
        """Trigger expand adds a condition."""
        breeder = PatternBreeder()
        pattern = copy.deepcopy(sample_patterns[0])
        original_count = len(pattern.trigger_conditions)

        record = breeder._mutate_trigger_expand(pattern)

        if record:
            assert len(pattern.trigger_conditions) > original_count

    def test_trigger_narrow(self, sample_patterns):
        """Trigger narrow removes a condition."""
        breeder = PatternBreeder()
        pattern = copy.deepcopy(sample_patterns[0])
        # Add extra conditions to remove
        pattern.trigger_conditions["extra1"] = "value1"
        pattern.trigger_conditions["extra2"] = "value2"
        original_count = len(pattern.trigger_conditions)

        record = breeder._mutate_trigger_narrow(pattern)

        if record:
            assert len(pattern.trigger_conditions) < original_count

    def test_approach_rephrase(self, sample_patterns):
        """Approach rephrase modifies text."""
        breeder = PatternBreeder()
        pattern = copy.deepcopy(sample_patterns[0])
        original_approach = pattern.approach

        record = breeder._mutate_approach_rephrase(pattern)

        if record:
            assert pattern.approach != original_approach

    def test_tool_swap(self, sample_patterns):
        """Tool swap changes a tool in sequence."""
        breeder = PatternBreeder()
        pattern = copy.deepcopy(sample_patterns[0])
        pattern.tool_sequence = ["Grep", "Read"]
        original_sequence = list(pattern.tool_sequence)

        record = breeder._mutate_tool_swap(pattern)

        if record:
            assert pattern.tool_sequence != original_sequence


class TestPatternBreederEvaluateFitness:
    """Tests for evaluate_fitness method."""

    def test_higher_success_rate_higher_fitness(self):
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

    def test_simplicity_bonus(self):
        """Fewer trigger conditions is better."""
        breeder = PatternBreeder()

        simple = PromptPattern(
            pattern_id="simple",
            pattern_type="test",
            description="Simple",
            trigger_conditions={"task": "search"},
            approach="Test",
            total_uses=20,
            success_count=16,
            failure_count=4
        )

        complex_pattern = PromptPattern(
            pattern_id="complex",
            pattern_type="test",
            description="Complex",
            trigger_conditions={
                "task": "search",
                "extra1": True,
                "extra2": True,
                "extra3": True,
                "extra4": True
            },
            approach="Test",
            total_uses=20,
            success_count=16,
            failure_count=4
        )

        simple_fitness = breeder.evaluate_fitness(simple)
        complex_fitness = breeder.evaluate_fitness(complex_pattern)

        # Same success rate, but simpler should be slightly better
        assert simple_fitness >= complex_fitness


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

    def test_preserves_population_size(self, sample_patterns):
        """Evolution maintains population size."""
        breeder = PatternBreeder(population_size=10)
        breeder.initialize_population(sample_patterns)

        for _ in range(3):
            breeder.evolve_generation()

        assert len(breeder.population) == 10

    def test_records_stats_history(self, sample_patterns):
        """Evolution records stats history."""
        breeder = PatternBreeder(population_size=10)
        breeder.initialize_population(sample_patterns)

        for _ in range(3):
            breeder.evolve_generation()

        assert len(breeder.stats_history) == 3

    def test_handles_empty_population(self):
        """Handles empty population gracefully."""
        breeder = PatternBreeder()

        stats = breeder.evolve_generation()

        assert stats.size == 0
        assert stats.avg_fitness == 0.0


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

    def test_handles_empty_population(self):
        """Returns empty list for empty population."""
        breeder = PatternBreeder()

        best = breeder.get_best_patterns(5)

        assert best == []


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
            approach="Do X",
            tool_sequence=["Grep"]
        )
        breeder.population = [copy.deepcopy(pattern) for _ in range(10)]
        for i, p in enumerate(breeder.population):
            p.pattern_id = f"p{i}"

        diversity = breeder.calculate_diversity()

        assert diversity < 0.3  # Low diversity

    def test_varied_population_high_diversity(self, sample_patterns):
        """Varied patterns have high diversity."""
        breeder = PatternBreeder()

        # Make patterns more varied
        for i, p in enumerate(sample_patterns):
            p.approach = f"Unique approach {i} with special words"
            p.trigger_conditions = {f"condition_{i}": True}
            p.tool_sequence = [["Grep", "Read", "Bash", "Edit", "Write"][i % 5]]

        breeder.population = sample_patterns

        diversity = breeder.calculate_diversity()

        assert diversity > 0.5  # Higher diversity

    def test_handles_small_population(self):
        """Handles population with single pattern."""
        breeder = PatternBreeder()
        breeder.population = [
            PromptPattern(
                pattern_id="p1",
                pattern_type="test",
                description="Test",
                trigger_conditions={},
                approach="Test"
            )
        ]

        diversity = breeder.calculate_diversity()

        assert diversity == 0.0


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

    def test_preserves_pattern_ids(self, sample_patterns):
        """Pattern IDs are preserved through export/import."""
        breeder = PatternBreeder()
        breeder.population = sample_patterns

        exported = breeder.export_population()

        new_breeder = PatternBreeder()
        new_breeder.import_population(exported)

        original_ids = {p.pattern_id for p in sample_patterns}
        imported_ids = {p.pattern_id for p in new_breeder.population}
        assert original_ids == imported_ids

    def test_preserves_statistics(self, sample_patterns):
        """Pattern statistics are preserved."""
        breeder = PatternBreeder()
        breeder.population = sample_patterns

        exported = breeder.export_population()

        new_breeder = PatternBreeder()
        new_breeder.import_population(exported)

        for orig, imported in zip(sample_patterns, new_breeder.population):
            assert imported.total_uses == orig.total_uses
            assert imported.success_count == orig.success_count


class TestMutationRecord:
    """Tests for MutationRecord dataclass."""

    def test_creation(self):
        """MutationRecord creates with required fields."""
        record = MutationRecord(
            mutation_type=MutationType.TOOL_SWAP,
            original_value="['Grep']",
            new_value="['Glob']"
        )

        assert record.mutation_type == MutationType.TOOL_SWAP
        assert record.original_value == "['Grep']"
        assert record.timestamp > 0


class TestBreedingResult:
    """Tests for BreedingResult dataclass."""

    def test_creation(self, sample_patterns):
        """BreedingResult creates with required fields."""
        result = BreedingResult(
            parent_a_id="p1",
            parent_b_id="p2",
            offspring=sample_patterns[0],
            crossover_point="approach"
        )

        assert result.parent_a_id == "p1"
        assert result.crossover_point == "approach"
        assert result.mutations_applied == []


class TestPopulationStats:
    """Tests for PopulationStats dataclass."""

    def test_creation(self):
        """PopulationStats creates with required fields."""
        stats = PopulationStats(
            size=50,
            avg_fitness=0.75,
            max_fitness=0.95,
            min_fitness=0.45,
            diversity_score=0.6,
            generations_evolved=10,
            total_mutations=100,
            successful_mutations=75
        )

        assert stats.size == 50
        assert stats.avg_fitness == 0.75
        assert stats.diversity_score == 0.6


class TestPatternBreederRecordOutcome:
    """Tests for record_outcome method."""

    def test_records_success(self, sample_patterns):
        """Records successful outcome."""
        breeder = PatternBreeder()
        breeder.population = sample_patterns
        original_uses = sample_patterns[0].total_uses
        original_success = sample_patterns[0].success_count

        breeder.record_outcome("p0", success=True)

        assert sample_patterns[0].total_uses == original_uses + 1
        assert sample_patterns[0].success_count == original_success + 1

    def test_records_failure(self, sample_patterns):
        """Records failed outcome."""
        breeder = PatternBreeder()
        breeder.population = sample_patterns
        original_uses = sample_patterns[0].total_uses
        original_failure = sample_patterns[0].failure_count

        breeder.record_outcome("p0", success=False)

        assert sample_patterns[0].total_uses == original_uses + 1
        assert sample_patterns[0].failure_count == original_failure + 1

    def test_handles_unknown_pattern(self, sample_patterns):
        """Handles unknown pattern ID gracefully."""
        breeder = PatternBreeder()
        breeder.population = sample_patterns

        # Should not raise
        breeder.record_outcome("unknown_id", success=True)


class TestPatternBreederGetStats:
    """Tests for get_stats method."""

    def test_returns_current_stats(self, sample_patterns):
        """Returns current population stats."""
        breeder = PatternBreeder()
        breeder.population = sample_patterns

        stats = breeder.get_stats()

        assert stats.size == len(sample_patterns)
        assert stats.avg_fitness > 0

    def test_handles_empty_population(self):
        """Handles empty population."""
        breeder = PatternBreeder()

        stats = breeder.get_stats()

        assert stats.size == 0
        assert stats.avg_fitness == 0.0


class TestEvolutionConvergence:
    """Tests for evolution behavior over multiple generations."""

    def test_best_patterns_preserved(self, sample_patterns):
        """Elite patterns should be preserved across generations."""
        breeder = PatternBreeder(population_size=20, mutation_rate=0.3)
        breeder.initialize_population(sample_patterns)

        initial_best = breeder.get_best_patterns(2)
        initial_max_fitness = max(breeder.evaluate_fitness(p) for p in initial_best)

        # Evolve several generations
        for _ in range(10):
            breeder.evolve_generation()

        final_best = breeder.get_best_patterns(2)
        final_max_fitness = max(breeder.evaluate_fitness(p) for p in final_best)

        # Best fitness should be preserved (elite survive)
        # Note: new patterns start with 0 usage so avg drops, but max stays
        assert final_max_fitness >= initial_max_fitness * 0.95

    def test_multiple_generations_stable(self, sample_patterns):
        """Population remains stable through many generations."""
        breeder = PatternBreeder(population_size=10, mutation_rate=0.1)
        breeder.initialize_population(sample_patterns)

        for _ in range(20):
            stats = breeder.evolve_generation()
            assert stats.size == 10

        assert breeder.generation == 20
        assert len(breeder.population) == 10
