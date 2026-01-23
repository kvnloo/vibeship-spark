"""
Spark Pattern Breeder: Genetic algorithm for evolving prompt patterns.

Implements genetic operations:
1. Selection: Tournament selection favoring fitter patterns
2. Crossover: Combine two patterns to create offspring
3. Mutation: Random changes to explore solution space
4. Evaluation: Score pattern fitness
5. Replacement: Update population with better patterns

Based on standard genetic algorithm principles applied to prompt optimization.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple, Callable, Any
from enum import Enum
import random
import copy
import hashlib
from datetime import datetime

from .prompt_evolver import PromptPattern


class MutationType(Enum):
    """Types of mutations that can be applied to patterns."""
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
    timestamp: float = field(default_factory=lambda: datetime.now().timestamp())


@dataclass
class BreedingResult:
    """Result of a breeding operation."""
    parent_a_id: str
    parent_b_id: str
    offspring: PromptPattern
    crossover_point: str          # What was crossed over: "triggers", "approach", "metadata"
    mutations_applied: List[MutationRecord] = field(default_factory=list)


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

    # Alternative tools for mutation swapping
    TOOL_ALTERNATIVES = {
        "Grep": ["Glob", "Read"],
        "Glob": ["Grep", "Read"],
        "Read": ["Grep", "Glob"],
        "Bash": ["Read", "Write"],
        "Write": ["Edit", "Bash"],
        "Edit": ["Write", "Bash"],
        "Task": ["Bash", "Read"],
    }

    # Approach modifiers for rephrasing
    APPROACH_MODIFIERS = [
        "first verify, then ",
        "efficiently ",
        "carefully ",
        "systematically ",
        "iteratively ",
        "before proceeding, ",
    ]

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
        self._total_mutations = 0
        self._successful_mutations = 0
        self._register_mutation_operators()

    def _register_mutation_operators(self):
        """Register all mutation operators."""
        self._mutation_operators = {
            MutationType.TRIGGER_EXPAND: self._mutate_trigger_expand,
            MutationType.TRIGGER_NARROW: self._mutate_trigger_narrow,
            MutationType.APPROACH_REPHRASE: self._mutate_approach_rephrase,
            MutationType.TOOL_SWAP: self._mutate_tool_swap,
        }

    def initialize_population(self, seed_patterns: List[PromptPattern]) -> int:
        """
        Initialize population from seed patterns.

        Args:
            seed_patterns: Initial patterns to seed population

        Returns:
            Number of patterns in population
        """
        if not seed_patterns:
            self.population = []
            return 0

        # Start with seed patterns
        self.population = [copy.deepcopy(p) for p in seed_patterns]

        # Fill to target size by creating variations
        while len(self.population) < self.population_size:
            # Pick a random seed to vary
            seed = random.choice(seed_patterns)
            variant = self._create_variant(seed)
            self.population.append(variant)

        # Trim if we have too many
        if len(self.population) > self.population_size:
            self.population = self.population[:self.population_size]

        self.generation = 0
        return len(self.population)

    def _create_variant(self, pattern: PromptPattern) -> PromptPattern:
        """Create a variant of a pattern with slight modifications."""
        variant = copy.deepcopy(pattern)

        # Generate new ID
        variant.pattern_id = hashlib.md5(
            f"{pattern.pattern_id}:var:{random.random()}".encode()
        ).hexdigest()[:12]

        # Apply a random mutation
        variant, _ = self.mutate(variant, mutation_rate=1.0)

        return variant

    def select(self, k: int) -> List[PromptPattern]:
        """
        Select k patterns using tournament selection.

        Args:
            k: Number of patterns to select

        Returns:
            Selected patterns
        """
        selected = []
        for _ in range(k):
            winner = self._tournament_select()
            selected.append(copy.deepcopy(winner))
        return selected

    def _tournament_select(self) -> PromptPattern:
        """Select one pattern via tournament."""
        if not self.population:
            raise ValueError("Cannot select from empty population")

        # Pick TOURNAMENT_SIZE random patterns
        tournament_size = min(self.TOURNAMENT_SIZE, len(self.population))
        contestants = random.sample(self.population, tournament_size)

        # Return the fittest
        return max(contestants, key=lambda p: self.evaluate_fitness(p))

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
        # Generate new ID for offspring
        offspring_id = hashlib.md5(
            f"{parent_a.pattern_id}:{parent_b.pattern_id}:{random.random()}".encode()
        ).hexdigest()[:12]

        # Choose crossover point randomly
        crossover_point = random.choice(["triggers", "approach", "metadata"])

        # Start with parent_a as base
        offspring = PromptPattern(
            pattern_id=offspring_id,
            pattern_type=parent_a.pattern_type,
            description=f"Bred from {parent_a.pattern_id[:6]} x {parent_b.pattern_id[:6]}",
            trigger_conditions={},
            approach="",
            generation=max(parent_a.generation, parent_b.generation) + 1,
            parent_id=parent_a.pattern_id
        )

        if crossover_point == "triggers":
            # Combine trigger conditions from both
            offspring.trigger_conditions = self._crossover_triggers(
                parent_a.trigger_conditions,
                parent_b.trigger_conditions
            )
            offspring.approach = parent_a.approach
            offspring.tool_sequence = parent_a.tool_sequence

        elif crossover_point == "approach":
            # Merge approaches
            offspring.trigger_conditions = parent_a.trigger_conditions.copy()
            offspring.approach = self._crossover_approach(
                parent_a.approach,
                parent_b.approach
            )
            # Mix tool sequences
            if parent_a.tool_sequence and parent_b.tool_sequence:
                offspring.tool_sequence = list(set(parent_a.tool_sequence) | set(parent_b.tool_sequence))
            else:
                offspring.tool_sequence = parent_a.tool_sequence or parent_b.tool_sequence

        else:  # metadata
            # Take triggers from A, approach from B
            offspring.trigger_conditions = parent_a.trigger_conditions.copy()
            offspring.approach = parent_b.approach
            offspring.tool_sequence = parent_b.tool_sequence

        return BreedingResult(
            parent_a_id=parent_a.pattern_id,
            parent_b_id=parent_b.pattern_id,
            offspring=offspring,
            crossover_point=crossover_point,
            mutations_applied=[]
        )

    def _crossover_triggers(
        self,
        triggers_a: Dict[str, Any],
        triggers_b: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Combine trigger conditions from both parents."""
        combined = {}

        # Get all keys from both
        all_keys = set(triggers_a.keys()) | set(triggers_b.keys())

        for key in all_keys:
            if key in triggers_a and key in triggers_b:
                # Both have this key - randomly choose one
                combined[key] = random.choice([triggers_a[key], triggers_b[key]])
            elif key in triggers_a:
                # Only in A - 50% chance to include
                if random.random() > 0.5:
                    combined[key] = triggers_a[key]
            else:
                # Only in B - 50% chance to include
                if random.random() > 0.5:
                    combined[key] = triggers_b[key]

        return combined

    def _crossover_approach(
        self,
        approach_a: str,
        approach_b: str
    ) -> str:
        """Combine approach text from both parents."""
        # Strategy: Take first half of A, second half of B
        words_a = approach_a.split()
        words_b = approach_b.split()

        if not words_a:
            return approach_b
        if not words_b:
            return approach_a

        mid_a = len(words_a) // 2
        mid_b = len(words_b) // 2

        # Combine halves
        combined = words_a[:mid_a] + words_b[mid_b:]

        return " ".join(combined) if combined else approach_a

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
        rate = mutation_rate if mutation_rate is not None else self.mutation_rate
        records = []

        mutated = copy.deepcopy(pattern)

        # Check each mutation type
        for mutation_type in MutationType:
            if mutation_type not in self._mutation_operators:
                continue

            if random.random() < rate:
                try:
                    record = self._apply_mutation(mutated, mutation_type)
                    if record:
                        records.append(record)
                        self._total_mutations += 1
                except Exception:
                    # Mutation failed, skip it
                    pass

        return mutated, records

    def _apply_mutation(
        self,
        pattern: PromptPattern,
        mutation_type: MutationType
    ) -> Optional[MutationRecord]:
        """Apply a specific mutation type."""
        operator = self._mutation_operators.get(mutation_type)
        if operator:
            return operator(pattern)
        return None

    def _mutate_trigger_expand(self, pattern: PromptPattern) -> Optional[MutationRecord]:
        """Add a new trigger condition."""
        original = str(pattern.trigger_conditions)

        # Possible new conditions
        new_conditions = [
            ("min_confidence", random.uniform(0.5, 0.9)),
            ("require_verification", True),
            ("max_attempts", random.randint(2, 5)),
            ("prefer_fast", random.choice([True, False])),
        ]

        # Pick one that's not already present
        for key, value in new_conditions:
            if key not in pattern.trigger_conditions:
                pattern.trigger_conditions[key] = value
                return MutationRecord(
                    mutation_type=MutationType.TRIGGER_EXPAND,
                    original_value=original,
                    new_value=str(pattern.trigger_conditions)
                )

        return None

    def _mutate_trigger_narrow(self, pattern: PromptPattern) -> Optional[MutationRecord]:
        """Remove a trigger condition."""
        if not pattern.trigger_conditions:
            return None

        # Don't remove task_category as it's usually essential
        removable = [k for k in pattern.trigger_conditions.keys() if k != "task_category"]
        if not removable:
            return None

        original = str(pattern.trigger_conditions)
        key_to_remove = random.choice(removable)
        del pattern.trigger_conditions[key_to_remove]

        return MutationRecord(
            mutation_type=MutationType.TRIGGER_NARROW,
            original_value=original,
            new_value=str(pattern.trigger_conditions)
        )

    def _mutate_approach_rephrase(self, pattern: PromptPattern) -> Optional[MutationRecord]:
        """Rephrase the approach text."""
        original = pattern.approach

        # Add a modifier
        modifier = random.choice(self.APPROACH_MODIFIERS)

        # Check if approach already starts with a modifier
        for m in self.APPROACH_MODIFIERS:
            if pattern.approach.lower().startswith(m.lower()):
                # Remove existing modifier and add new one
                pattern.approach = modifier + pattern.approach[len(m):]
                break
        else:
            # No existing modifier, add one
            pattern.approach = modifier + pattern.approach

        if pattern.approach != original:
            return MutationRecord(
                mutation_type=MutationType.APPROACH_REPHRASE,
                original_value=original,
                new_value=pattern.approach
            )

        return None

    def _mutate_tool_swap(self, pattern: PromptPattern) -> Optional[MutationRecord]:
        """Swap a recommended tool for an alternative."""
        if not pattern.tool_sequence:
            return None

        original = str(pattern.tool_sequence)

        # Find a tool we can swap
        for i, tool in enumerate(pattern.tool_sequence):
            if tool in self.TOOL_ALTERNATIVES:
                alternatives = self.TOOL_ALTERNATIVES[tool]
                # Pick an alternative not already in sequence
                available = [a for a in alternatives if a not in pattern.tool_sequence]
                if available:
                    new_tool = random.choice(available)
                    pattern.tool_sequence[i] = new_tool
                    return MutationRecord(
                        mutation_type=MutationType.TOOL_SWAP,
                        original_value=original,
                        new_value=str(pattern.tool_sequence)
                    )

        return None

    def evaluate_fitness(self, pattern: PromptPattern) -> float:
        """
        Evaluate pattern fitness.

        Factors:
        - Success rate (weighted heavily)
        - Sample size confidence
        - Generalization (not overfitted)
        - Simplicity (fewer conditions is better)
        """
        # Use the pattern's built-in fitness score (Wilson score)
        base_fitness = pattern.fitness_score

        # Bonus for larger sample sizes (more confidence)
        sample_bonus = 0.0
        if pattern.total_uses >= 10:
            sample_bonus = 0.1
        elif pattern.total_uses >= 5:
            sample_bonus = 0.05

        # Simplicity bonus (fewer trigger conditions = more general)
        trigger_count = len(pattern.trigger_conditions)
        simplicity_bonus = max(0, 0.05 * (3 - trigger_count))  # Max bonus at 0-3 triggers

        # Penalize patterns that are too new (high generation but no usage)
        generation_penalty = 0.0
        if pattern.generation > 0 and pattern.total_uses < 3:
            generation_penalty = 0.1 * pattern.generation

        fitness = base_fitness + sample_bonus + simplicity_bonus - generation_penalty

        return max(0.0, min(1.0, fitness))

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
        if not self.population:
            return PopulationStats(
                size=0,
                avg_fitness=0.0,
                max_fitness=0.0,
                min_fitness=0.0,
                diversity_score=0.0,
                generations_evolved=self.generation,
                total_mutations=self._total_mutations,
                successful_mutations=self._successful_mutations
            )

        # Step 1: Evaluate all patterns
        fitnesses = [(p, self.evaluate_fitness(p)) for p in self.population]
        fitnesses.sort(key=lambda x: x[1], reverse=True)

        # Step 2: Select elite to preserve
        elite_count = max(1, int(len(self.population) * self.ELITE_PERCENTAGE))
        elite = [copy.deepcopy(p) for p, _ in fitnesses[:elite_count]]

        # Step 3 & 4: Create offspring
        offspring = []
        target_offspring = self.population_size - elite_count

        while len(offspring) < target_offspring:
            # Select parents
            parents = self.select(2)
            parent_a, parent_b = parents[0], parents[1]

            # Crossover with probability
            if random.random() < self.crossover_rate:
                result = self.crossover(parent_a, parent_b)
                child = result.offspring
            else:
                # No crossover, clone one parent
                child = copy.deepcopy(random.choice([parent_a, parent_b]))
                child.pattern_id = hashlib.md5(
                    f"{child.pattern_id}:clone:{random.random()}".encode()
                ).hexdigest()[:12]

            # Step 5: Apply mutations
            child, mutations = self.mutate(child)

            offspring.append(child)

        # Step 6: Replace population
        self.population = elite + offspring[:target_offspring]

        # Step 7: Record statistics
        self.generation += 1

        current_fitnesses = [self.evaluate_fitness(p) for p in self.population]
        stats = PopulationStats(
            size=len(self.population),
            avg_fitness=sum(current_fitnesses) / len(current_fitnesses) if current_fitnesses else 0.0,
            max_fitness=max(current_fitnesses) if current_fitnesses else 0.0,
            min_fitness=min(current_fitnesses) if current_fitnesses else 0.0,
            diversity_score=self.calculate_diversity(),
            generations_evolved=self.generation,
            total_mutations=self._total_mutations,
            successful_mutations=self._successful_mutations
        )

        self.stats_history.append(stats)

        return stats

    def get_best_patterns(self, n: int = 5) -> List[PromptPattern]:
        """Get top N patterns by fitness."""
        if not self.population:
            return []

        sorted_patterns = sorted(
            self.population,
            key=lambda p: self.evaluate_fitness(p),
            reverse=True
        )

        return sorted_patterns[:n]

    def calculate_diversity(self) -> float:
        """
        Calculate population diversity score.

        Measures how different patterns are from each other.
        Returns value between 0 (identical) and 1 (very diverse).
        """
        if len(self.population) < 2:
            return 0.0

        diversity_factors = []

        # Measure approach diversity
        approaches = [p.approach for p in self.population]
        unique_approaches = len(set(approaches))
        approach_diversity = unique_approaches / len(approaches)
        diversity_factors.append(approach_diversity)

        # Measure trigger diversity
        trigger_sets = [frozenset(p.trigger_conditions.keys()) for p in self.population]
        unique_triggers = len(set(trigger_sets))
        trigger_diversity = unique_triggers / len(trigger_sets)
        diversity_factors.append(trigger_diversity)

        # Measure tool sequence diversity
        sequences = [tuple(p.tool_sequence) if p.tool_sequence else () for p in self.population]
        unique_sequences = len(set(sequences))
        sequence_diversity = unique_sequences / len(sequences) if sequences else 0.0
        diversity_factors.append(sequence_diversity)

        # Measure generation spread
        generations = [p.generation for p in self.population]
        if max(generations) > 0:
            gen_spread = len(set(generations)) / (max(generations) + 1)
            diversity_factors.append(min(1.0, gen_spread))

        return sum(diversity_factors) / len(diversity_factors) if diversity_factors else 0.0

    def get_stats(self) -> PopulationStats:
        """Get current population statistics."""
        if not self.population:
            return PopulationStats(
                size=0,
                avg_fitness=0.0,
                max_fitness=0.0,
                min_fitness=0.0,
                diversity_score=0.0,
                generations_evolved=self.generation,
                total_mutations=self._total_mutations,
                successful_mutations=self._successful_mutations
            )

        fitnesses = [self.evaluate_fitness(p) for p in self.population]

        return PopulationStats(
            size=len(self.population),
            avg_fitness=sum(fitnesses) / len(fitnesses),
            max_fitness=max(fitnesses),
            min_fitness=min(fitnesses),
            diversity_score=self.calculate_diversity(),
            generations_evolved=self.generation,
            total_mutations=self._total_mutations,
            successful_mutations=self._successful_mutations
        )

    def export_population(self) -> List[Dict]:
        """Export population for persistence."""
        exported = []

        for pattern in self.population:
            exported.append({
                "pattern_id": pattern.pattern_id,
                "pattern_type": pattern.pattern_type,
                "description": pattern.description,
                "trigger_conditions": pattern.trigger_conditions,
                "approach": pattern.approach,
                "tool_sequence": pattern.tool_sequence,
                "success_count": pattern.success_count,
                "failure_count": pattern.failure_count,
                "total_uses": pattern.total_uses,
                "avg_duration_ms": pattern.avg_duration_ms,
                "generation": pattern.generation,
                "parent_id": pattern.parent_id,
                "created_at": pattern.created_at
            })

        return exported

    def import_population(self, data: List[Dict]):
        """Import population from persistence."""
        self.population = []

        for item in data:
            pattern = PromptPattern(
                pattern_id=item.get("pattern_id", ""),
                pattern_type=item.get("pattern_type", "unknown"),
                description=item.get("description", ""),
                trigger_conditions=item.get("trigger_conditions", {}),
                approach=item.get("approach", ""),
                tool_sequence=item.get("tool_sequence"),
                success_count=item.get("success_count", 0),
                failure_count=item.get("failure_count", 0),
                total_uses=item.get("total_uses", 0),
                avg_duration_ms=item.get("avg_duration_ms", 0.0),
                generation=item.get("generation", 0),
                parent_id=item.get("parent_id")
            )
            # Handle created_at if present
            if "created_at" in item:
                pattern.created_at = item["created_at"]

            self.population.append(pattern)

    def record_outcome(self, pattern_id: str, success: bool):
        """
        Record the outcome of using a pattern.

        Args:
            pattern_id: Pattern that was used
            success: Whether it succeeded
        """
        for pattern in self.population:
            if pattern.pattern_id == pattern_id:
                pattern.total_uses += 1
                if success:
                    pattern.success_count += 1
                    self._successful_mutations += 1
                else:
                    pattern.failure_count += 1
                break
