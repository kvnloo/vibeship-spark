#!/usr/bin/env python3
"""
M7 Live Integration Test: Pattern Breeder Genetic Algorithm

This test demonstrates the PatternBreeder working in real-world scenarios:
1. Seeding population from real usage patterns
2. Simulating pattern usage with success/failure outcomes
3. Evolution over multiple generations
4. Selection pressure favoring successful patterns
5. Crossover creating offspring with mixed traits
6. Mutation exploring new variations
7. Elite preservation keeping best patterns
8. Diversity maintenance preventing premature convergence
9. Export/Import for persistence
10. Integration with PromptEvolver patterns

Run: python test_m7_live.py
"""

import sys
import random
from pathlib import Path

# Add lib to path
sys.path.insert(0, str(Path(__file__).parent))

from lib.pattern_breeder import PatternBreeder, MutationType, PopulationStats
from lib.prompt_evolver import PromptPattern, PromptEvolver
from lib.mind_client import MindClient


def create_realistic_patterns():
    """Create patterns that simulate real Claude Code usage patterns."""
    patterns = [
        # Search patterns with varying effectiveness
        PromptPattern(
            pattern_id="search_grep_first",
            pattern_type="tool_sequence",
            description="Use Grep before Read for code search",
            trigger_conditions={"task_category": "search", "prefer_fast": True},
            approach="First use Grep to find matches, then Read specific files",
            tool_sequence=["Grep", "Read"],
            total_uses=50,
            success_count=45,  # 90% success
            failure_count=5
        ),
        PromptPattern(
            pattern_id="search_glob_grep",
            pattern_type="tool_sequence",
            description="Use Glob then Grep for file discovery",
            trigger_conditions={"task_category": "search"},
            approach="First Glob to find files, then Grep for content",
            tool_sequence=["Glob", "Grep", "Read"],
            total_uses=40,
            success_count=32,  # 80% success
            failure_count=8
        ),
        PromptPattern(
            pattern_id="search_task_agent",
            pattern_type="tool_sequence",
            description="Use Task agent for complex searches",
            trigger_conditions={"task_category": "search", "complexity": "high"},
            approach="Delegate complex searches to Task agent",
            tool_sequence=["Task"],
            total_uses=30,
            success_count=21,  # 70% success
            failure_count=9
        ),
        # Edit patterns
        PromptPattern(
            pattern_id="edit_read_first",
            pattern_type="tool_sequence",
            description="Always Read before Edit",
            trigger_conditions={"task_category": "edit"},
            approach="Read file content before making edits to understand context",
            tool_sequence=["Read", "Edit"],
            total_uses=60,
            success_count=54,  # 90% success
            failure_count=6
        ),
        PromptPattern(
            pattern_id="edit_verify_after",
            pattern_type="tool_sequence",
            description="Verify edits with Read after",
            trigger_conditions={"task_category": "edit", "require_verification": True},
            approach="After editing, read the file to verify changes",
            tool_sequence=["Read", "Edit", "Read"],
            total_uses=35,
            success_count=33,  # 94% success
            failure_count=2
        ),
        # Error recovery patterns
        PromptPattern(
            pattern_id="error_file_not_found",
            pattern_type="error_recovery",
            description="Handle file not found with Glob",
            trigger_conditions={"error_type": "not_found"},
            approach="When file not found, use Glob to search for similar files",
            tool_sequence=["Glob", "Read"],
            total_uses=25,
            success_count=20,  # 80% success
            failure_count=5
        ),
        PromptPattern(
            pattern_id="error_permission",
            pattern_type="error_recovery",
            description="Handle permission errors",
            trigger_conditions={"error_type": "permission"},
            approach="Check file permissions and suggest alternatives",
            tool_sequence=["Bash", "Read"],
            total_uses=15,
            success_count=9,  # 60% success
            failure_count=6
        ),
        # Task patterns with mixed success
        PromptPattern(
            pattern_id="test_run_focused",
            pattern_type="task_approach",
            description="Run focused tests first",
            trigger_conditions={"task_category": "testing"},
            approach="Run specific test file before full suite",
            tool_sequence=["Bash"],
            total_uses=45,
            success_count=38,  # 84% success
            failure_count=7
        ),
    ]
    return patterns


def simulate_usage(breeder: PatternBreeder, rounds: int = 20):
    """Simulate real usage where patterns are tried and outcomes recorded."""
    print(f"\n  Simulating {rounds} rounds of pattern usage...")

    for round_num in range(rounds):
        # Pick random patterns to "use"
        if not breeder.population:
            continue

        patterns_to_use = random.sample(
            breeder.population,
            min(3, len(breeder.population))
        )

        for pattern in patterns_to_use:
            # Simulate success probability based on pattern's historical rate
            base_success_rate = pattern.success_rate if pattern.total_uses > 0 else 0.5

            # Add some randomness
            success = random.random() < base_success_rate

            # Record outcome
            breeder.record_outcome(pattern.pattern_id, success)

    print(f"       Completed {rounds} usage rounds")


def test_basic_evolution():
    """Test 1: Basic evolution cycle."""
    print("\n" + "=" * 60)
    print("TEST 1: Basic Evolution Cycle")
    print("=" * 60)

    patterns = create_realistic_patterns()
    breeder = PatternBreeder(population_size=15, mutation_rate=0.3, crossover_rate=0.7)

    # Initialize
    count = breeder.initialize_population(patterns)
    print(f"\n  Initialized population with {count} patterns")

    initial_stats = breeder.get_stats()
    print(f"  Initial: avg_fitness={initial_stats.avg_fitness:.3f}, "
          f"max={initial_stats.max_fitness:.3f}, diversity={initial_stats.diversity_score:.2f}")

    # Evolve for 5 generations
    print("\n  Evolving for 5 generations...")
    for gen in range(5):
        stats = breeder.evolve_generation()
        print(f"    Gen {gen + 1}: avg={stats.avg_fitness:.3f}, "
              f"max={stats.max_fitness:.3f}, mutations={stats.total_mutations}")

    # Verify evolution happened
    assert breeder.generation == 5, f"Expected 5 generations, got {breeder.generation}"
    assert len(breeder.population) == 15, f"Population size changed unexpectedly"
    assert len(breeder.stats_history) == 5, f"Stats history incomplete"

    print("\n  [PASS] Basic evolution cycle works correctly")
    return True


def test_selection_pressure():
    """Test 2: Selection favors fitter patterns."""
    print("\n" + "=" * 60)
    print("TEST 2: Selection Pressure")
    print("=" * 60)

    breeder = PatternBreeder(population_size=20)

    # Create patterns with clear fitness differences
    high_fitness = PromptPattern(
        pattern_id="high",
        pattern_type="test",
        description="High fitness pattern",
        trigger_conditions={"task": "search"},
        approach="Very effective approach",
        total_uses=100,
        success_count=95,
        failure_count=5
    )

    low_fitness = PromptPattern(
        pattern_id="low",
        pattern_type="test",
        description="Low fitness pattern",
        trigger_conditions={"task": "search"},
        approach="Less effective approach",
        total_uses=100,
        success_count=40,
        failure_count=60
    )

    breeder.initialize_population([high_fitness, low_fitness])

    # Select many times and count
    high_count = 0
    low_count = 0

    for _ in range(100):
        selected = breeder.select(1)[0]
        if "high" in selected.pattern_id or selected.success_count > 80:
            high_count += 1
        else:
            low_count += 1

    print(f"\n  Selection results over 100 trials:")
    print(f"    High fitness selected: {high_count} times")
    print(f"    Low fitness selected: {low_count} times")
    print(f"    Selection ratio: {high_count / max(1, low_count):.1f}x")

    # High fitness should be selected more often
    assert high_count > low_count, "Selection should favor high fitness patterns"

    print("\n  [PASS] Selection correctly favors fitter patterns")
    return True


def test_crossover_creates_offspring():
    """Test 3: Crossover combines parent traits."""
    print("\n" + "=" * 60)
    print("TEST 3: Crossover Creates Offspring")
    print("=" * 60)

    breeder = PatternBreeder()

    parent_a = PromptPattern(
        pattern_id="parent_a",
        pattern_type="tool_sequence",
        description="Parent A",
        trigger_conditions={"task": "search", "fast": True},
        approach="Use Grep first for speed",
        tool_sequence=["Grep", "Read"],
        generation=2
    )

    parent_b = PromptPattern(
        pattern_id="parent_b",
        pattern_type="tool_sequence",
        description="Parent B",
        trigger_conditions={"task": "search", "thorough": True},
        approach="Use Glob for completeness",
        tool_sequence=["Glob", "Grep"],
        generation=3
    )

    # Perform multiple crossovers to see variety
    crossover_points = set()
    offspring_traits = []

    for _ in range(10):
        result = breeder.crossover(parent_a, parent_b)
        crossover_points.add(result.crossover_point)
        offspring_traits.append({
            "id": result.offspring.pattern_id,
            "generation": result.offspring.generation,
            "approach_len": len(result.offspring.approach),
            "triggers": len(result.offspring.trigger_conditions)
        })

    print(f"\n  Performed 10 crossovers:")
    print(f"    Crossover points used: {crossover_points}")
    print(f"    All offspring have unique IDs: {len(set(t['id'] for t in offspring_traits)) == 10}")
    print(f"    Offspring generation: {offspring_traits[0]['generation']} (expected: 4)")

    # Verify offspring properties
    assert len(crossover_points) >= 2, "Should use multiple crossover strategies"
    assert offspring_traits[0]["generation"] == 4, "Offspring generation should be max(parents) + 1"

    print("\n  [PASS] Crossover correctly creates diverse offspring")
    return True


def test_mutation_explores_space():
    """Test 4: Mutation creates variations."""
    print("\n" + "=" * 60)
    print("TEST 4: Mutation Explores Solution Space")
    print("=" * 60)

    breeder = PatternBreeder(mutation_rate=1.0)  # Force all mutations

    original = PromptPattern(
        pattern_id="original",
        pattern_type="tool_sequence",
        description="Original pattern",
        trigger_conditions={"task": "edit"},
        approach="Edit files carefully",
        tool_sequence=["Read", "Edit"]
    )

    # Track mutation types that occur
    mutation_types_seen = set()
    changes = {
        "approach_changed": 0,
        "triggers_changed": 0,
        "tools_changed": 0
    }

    for _ in range(20):
        mutated, records = breeder.mutate(original)

        for record in records:
            mutation_types_seen.add(record.mutation_type)

            if record.mutation_type == MutationType.APPROACH_REPHRASE:
                changes["approach_changed"] += 1
            elif record.mutation_type in [MutationType.TRIGGER_EXPAND, MutationType.TRIGGER_NARROW]:
                changes["triggers_changed"] += 1
            elif record.mutation_type == MutationType.TOOL_SWAP:
                changes["tools_changed"] += 1

    print(f"\n  Mutation types observed:")
    for mt in mutation_types_seen:
        print(f"    - {mt.value}")

    print(f"\n  Changes across 20 mutations:")
    print(f"    Approach rephrased: {changes['approach_changed']}x")
    print(f"    Triggers modified: {changes['triggers_changed']}x")
    print(f"    Tools swapped: {changes['tools_changed']}x")

    assert len(mutation_types_seen) >= 2, "Should see multiple mutation types"

    print("\n  [PASS] Mutation correctly explores solution space")
    return True


def test_elite_preservation():
    """Test 5: Elite patterns survive evolution."""
    print("\n" + "=" * 60)
    print("TEST 5: Elite Preservation")
    print("=" * 60)

    patterns = create_realistic_patterns()
    breeder = PatternBreeder(population_size=10, mutation_rate=0.5)
    breeder.ELITE_PERCENTAGE = 0.2  # Top 20% (2 patterns)

    breeder.initialize_population(patterns)

    # Get the best patterns before evolution
    best_before = breeder.get_best_patterns(2)
    best_ids_before = {p.pattern_id for p in best_before}
    best_fitness_before = max(breeder.evaluate_fitness(p) for p in best_before)

    print(f"\n  Before evolution:")
    print(f"    Top 2 pattern IDs: {best_ids_before}")
    print(f"    Best fitness: {best_fitness_before:.3f}")

    # Evolve several generations
    for _ in range(5):
        breeder.evolve_generation()

    # Check that elite are preserved or replaced by better
    best_after = breeder.get_best_patterns(2)
    best_fitness_after = max(breeder.evaluate_fitness(p) for p in best_after)

    print(f"\n  After 5 generations:")
    print(f"    Best fitness: {best_fitness_after:.3f}")

    # Best fitness should not decrease significantly
    assert best_fitness_after >= best_fitness_before * 0.95, \
        f"Elite fitness dropped too much: {best_fitness_after:.3f} < {best_fitness_before * 0.95:.3f}"

    print("\n  [PASS] Elite patterns are preserved across generations")
    return True


def test_diversity_maintenance():
    """Test 6: Population maintains diversity."""
    print("\n" + "=" * 60)
    print("TEST 6: Diversity Maintenance")
    print("=" * 60)

    patterns = create_realistic_patterns()
    breeder = PatternBreeder(population_size=15, mutation_rate=0.4)

    breeder.initialize_population(patterns)

    initial_diversity = breeder.calculate_diversity()
    print(f"\n  Initial diversity: {initial_diversity:.3f}")

    # Evolve and track diversity
    diversity_history = [initial_diversity]
    for gen in range(10):
        stats = breeder.evolve_generation()
        diversity_history.append(stats.diversity_score)

    final_diversity = diversity_history[-1]
    min_diversity = min(diversity_history)

    print(f"  Final diversity: {final_diversity:.3f}")
    print(f"  Minimum diversity during evolution: {min_diversity:.3f}")
    print(f"  Diversity range: {min(diversity_history):.3f} - {max(diversity_history):.3f}")

    # Diversity shouldn't collapse completely
    assert min_diversity > 0.1, "Diversity collapsed too much"

    print("\n  [PASS] Population maintains reasonable diversity")
    return True


def test_export_import_persistence():
    """Test 7: Population survives export/import."""
    print("\n" + "=" * 60)
    print("TEST 7: Export/Import Persistence")
    print("=" * 60)

    patterns = create_realistic_patterns()
    breeder1 = PatternBreeder(population_size=10)
    breeder1.initialize_population(patterns)

    # Evolve a few generations
    for _ in range(3):
        breeder1.evolve_generation()

    # Export
    exported = breeder1.export_population()
    print(f"\n  Exported {len(exported)} patterns after 3 generations")

    # Import into new breeder
    breeder2 = PatternBreeder()
    breeder2.import_population(exported)

    print(f"  Imported {len(breeder2.population)} patterns")

    # Verify data integrity
    original_ids = {p.pattern_id for p in breeder1.population}
    imported_ids = {p.pattern_id for p in breeder2.population}

    assert original_ids == imported_ids, "Pattern IDs don't match after import"

    # Verify statistics preserved
    for orig in breeder1.population:
        imported = next(p for p in breeder2.population if p.pattern_id == orig.pattern_id)
        assert imported.total_uses == orig.total_uses, "Usage stats not preserved"
        assert imported.success_count == orig.success_count, "Success count not preserved"
        assert imported.generation == orig.generation, "Generation not preserved"

    print("  All pattern data preserved correctly")

    print("\n  [PASS] Export/import preserves all pattern data")
    return True


def test_usage_feedback_loop():
    """Test 8: Patterns improve with usage feedback."""
    print("\n" + "=" * 60)
    print("TEST 8: Usage Feedback Loop")
    print("=" * 60)

    patterns = create_realistic_patterns()
    breeder = PatternBreeder(population_size=12, mutation_rate=0.2)
    breeder.initialize_population(patterns)

    print("\n  Simulating real usage with feedback...")

    # Record initial state
    initial_best = breeder.get_best_patterns(3)
    initial_max_fitness = max(breeder.evaluate_fitness(p) for p in initial_best)

    # Simulate 5 cycles of: use → record outcomes → evolve
    for cycle in range(5):
        # Simulate usage
        simulate_usage(breeder, rounds=10)

        # Evolve
        stats = breeder.evolve_generation()

        print(f"    Cycle {cycle + 1}: population={stats.size}, "
              f"avg_fitness={stats.avg_fitness:.3f}, "
              f"total_mutations={stats.total_mutations}")

    # Check final state
    final_best = breeder.get_best_patterns(3)
    final_max_fitness = max(breeder.evaluate_fitness(p) for p in final_best)

    print(f"\n  Initial max fitness: {initial_max_fitness:.3f}")
    print(f"  Final max fitness: {final_max_fitness:.3f}")

    # With usage feedback, best patterns should stay good
    assert final_max_fitness >= initial_max_fitness * 0.9, \
        "Best patterns degraded too much with usage"

    print("\n  [PASS] Usage feedback loop maintains pattern quality")
    return True


def test_integration_with_prompt_evolver():
    """Test 9: Integration with existing PromptEvolver."""
    print("\n" + "=" * 60)
    print("TEST 9: Integration with PromptEvolver")
    print("=" * 60)

    # Create a PromptEvolver and add some patterns
    evolver = PromptEvolver()

    # Manually add patterns to evolver
    evolver.patterns["search_1"] = PromptPattern(
        pattern_id="search_1",
        pattern_type="tool_sequence",
        description="Search pattern from evolver",
        trigger_conditions={"task_category": "search"},
        approach="Use Grep for searching",
        tool_sequence=["Grep"],
        total_uses=25,
        success_count=20,
        failure_count=5
    )
    evolver.patterns["edit_1"] = PromptPattern(
        pattern_id="edit_1",
        pattern_type="tool_sequence",
        description="Edit pattern from evolver",
        trigger_conditions={"task_category": "edit"},
        approach="Read before edit",
        tool_sequence=["Read", "Edit"],
        total_uses=30,
        success_count=27,
        failure_count=3
    )

    print(f"\n  PromptEvolver has {len(evolver.patterns)} patterns")

    # Feed evolver patterns to breeder for evolution
    breeder = PatternBreeder(population_size=10, mutation_rate=0.3)
    evolver_patterns = list(evolver.patterns.values())
    breeder.initialize_population(evolver_patterns)

    print(f"  PatternBreeder initialized with {len(breeder.population)} patterns")

    # Evolve
    for _ in range(3):
        breeder.evolve_generation()

    print(f"  Evolved to generation {breeder.generation}")

    # Get evolved best patterns
    best = breeder.get_best_patterns(3)

    print(f"\n  Top 3 patterns after evolution:")
    for i, p in enumerate(best, 1):
        fitness = breeder.evaluate_fitness(p)
        print(f"    {i}. {p.pattern_id[:20]}: fitness={fitness:.3f}, gen={p.generation}")

    # Could update evolver with best evolved patterns
    print("\n  [PASS] PatternBreeder integrates with PromptEvolver")
    return True


def test_full_evolution_simulation():
    """Test 10: Full realistic evolution simulation."""
    print("\n" + "=" * 60)
    print("TEST 10: Full Evolution Simulation")
    print("=" * 60)

    print("\n  Simulating 20 generations of real-world pattern evolution...")

    patterns = create_realistic_patterns()
    breeder = PatternBreeder(
        population_size=20,
        mutation_rate=0.25,
        crossover_rate=0.7
    )

    breeder.initialize_population(patterns)

    # Track metrics over time
    metrics = {
        "generations": [],
        "avg_fitness": [],
        "max_fitness": [],
        "diversity": [],
        "mutations": []
    }

    initial_stats = breeder.get_stats()
    metrics["generations"].append(0)
    metrics["avg_fitness"].append(initial_stats.avg_fitness)
    metrics["max_fitness"].append(initial_stats.max_fitness)
    metrics["diversity"].append(initial_stats.diversity_score)
    metrics["mutations"].append(0)

    # Evolution loop
    for gen in range(20):
        # Simulate some usage
        if gen % 4 == 0:
            simulate_usage(breeder, rounds=5)

        # Evolve
        stats = breeder.evolve_generation()

        metrics["generations"].append(gen + 1)
        metrics["avg_fitness"].append(stats.avg_fitness)
        metrics["max_fitness"].append(stats.max_fitness)
        metrics["diversity"].append(stats.diversity_score)
        metrics["mutations"].append(stats.total_mutations)

        if (gen + 1) % 5 == 0:
            print(f"    Gen {gen + 1:2d}: avg={stats.avg_fitness:.3f}, "
                  f"max={stats.max_fitness:.3f}, "
                  f"div={stats.diversity_score:.2f}")

    # Summary
    print(f"\n  Evolution Summary:")
    print(f"    Starting avg fitness: {metrics['avg_fitness'][0]:.3f}")
    print(f"    Final avg fitness: {metrics['avg_fitness'][-1]:.3f}")
    print(f"    Peak max fitness: {max(metrics['max_fitness']):.3f}")
    print(f"    Diversity range: {min(metrics['diversity']):.2f} - {max(metrics['diversity']):.2f}")
    print(f"    Total mutations: {metrics['mutations'][-1]}")

    # Show best patterns
    print(f"\n  Final Top 5 Patterns:")
    for i, p in enumerate(breeder.get_best_patterns(5), 1):
        print(f"    {i}. [{p.pattern_type}] {p.description[:40]}...")
        print(f"       Fitness: {breeder.evaluate_fitness(p):.3f}, "
              f"Gen: {p.generation}, "
              f"Uses: {p.total_uses}")

    print("\n  [PASS] Full evolution simulation completed successfully")
    return True


def main():
    """Run all M7 live integration tests."""
    print("\n" + "=" * 70)
    print("  M7 LIVE INTEGRATION TEST: Pattern Breeder Genetic Algorithm")
    print("=" * 70)

    tests = [
        ("Basic Evolution Cycle", test_basic_evolution),
        ("Selection Pressure", test_selection_pressure),
        ("Crossover Creates Offspring", test_crossover_creates_offspring),
        ("Mutation Explores Space", test_mutation_explores_space),
        ("Elite Preservation", test_elite_preservation),
        ("Diversity Maintenance", test_diversity_maintenance),
        ("Export/Import Persistence", test_export_import_persistence),
        ("Usage Feedback Loop", test_usage_feedback_loop),
        ("Integration with PromptEvolver", test_integration_with_prompt_evolver),
        ("Full Evolution Simulation", test_full_evolution_simulation),
    ]

    results = []

    for name, test_func in tests:
        try:
            passed = test_func()
            results.append((name, passed, None))
        except Exception as e:
            results.append((name, False, str(e)))
            print(f"\n  [FAIL] {name}: {e}")

    # Final Summary
    print("\n" + "=" * 70)
    print("  FINAL RESULTS")
    print("=" * 70)

    passed = sum(1 for _, p, _ in results if p)
    total = len(results)

    for name, passed_test, error in results:
        status = "[PASS]" if passed_test else "[FAIL]"
        print(f"  {status} {name}")
        if error:
            print(f"         Error: {error}")

    print()
    print(f"  Total: {passed}/{total} tests passed")
    print()

    if passed == total:
        print("  " + "=" * 50)
        print("  ALL M7 LIVE TESTS PASSED!")
        print("  Pattern Breeder Genetic Algorithm is working correctly.")
        print("  " + "=" * 50)
    else:
        print("  Some tests failed. Please review the output above.")

    return passed == total


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
