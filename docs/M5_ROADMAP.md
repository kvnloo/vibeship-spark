# M5+ Roadmap: Future Enhancements

## Status Overview

| Milestone | Status | Description |
|-----------|--------|-------------|
| M5 | Saved | Feedback Loop Completion |
| M6 | Saved | Cross-Project Intelligence |
| M7 | Saved | Advanced Prompt Evolution |
| M8 | Saved | MCP Server Enhancement |
| M9 | **IN PROGRESS** | Integration Tests |
| M10 | Saved | Observability & Debugging |

---

## M5: Feedback Loop Completion (SAVED)

**Goal:** Track when injected context actually helped, close the improvement cycle.

### 5.1 Injection Tracking
```python
# Key implementation details:
class InjectionTracker:
    def tag_injection(self, learning_id: str, session_id: str) -> str:
        """Tag injected learning with tracking ID."""
        tracking_id = f"inj_{learning_id}_{session_id}"
        self.active_injections[tracking_id] = {
            "learning_id": learning_id,
            "injected_at": time.time(),
            "session_id": session_id,
            "was_used": None
        }
        return tracking_id

    def detect_usage(self, event: SparkEvent) -> Optional[str]:
        """Detect if an injected suggestion was followed."""
        # Check if tool usage matches injected recommendation
        # Check if error was avoided that we warned about
        pass

    def record_outcome(self, tracking_id: str, was_helpful: bool):
        """Record whether injection helped."""
        # Update learning confidence based on feedback
        # Feed to meta-learner
        pass
```

### 5.2 A/B Testing for Patterns
```python
class PatternExperiment:
    experiment_id: str
    pattern_a: PromptPattern  # Control
    pattern_b: PromptPattern  # Variant
    sessions_a: List[str]
    sessions_b: List[str]
    success_a: int
    success_b: int

    def assign_session(self, session_id: str) -> str:
        """Randomly assign session to A or B."""
        pass

    def is_significant(self, confidence: float = 0.95) -> bool:
        """Check if difference is statistically significant."""
        # Chi-squared test or similar
        pass
```

### 5.3 User Feedback Integration
```python
# Hook into Claude's response rating if available
# Or provide explicit feedback commands:
# /spark helpful - last suggestion was helpful
# /spark not-helpful - last suggestion wasn't helpful
```

**Files to create:**
- `lib/injection_tracker.py`
- `lib/experiment.py`
- `tests/test_injection_tracker.py`
- `tests/test_experiment.py`

---

## M6: Cross-Project Intelligence (SAVED)

**Goal:** Share learnings across projects intelligently.

### 6.1 Project Fingerprinting
```python
@dataclass
class ProjectFingerprint:
    project_type: str  # "web_app", "cli", "library", "api", etc.
    languages: List[str]  # ["python", "typescript"]
    frameworks: List[str]  # ["fastapi", "react"]
    tools_used: List[str]  # ["pytest", "eslint"]
    patterns_detected: List[str]  # ["mvc", "microservices"]

    def similarity(self, other: 'ProjectFingerprint') -> float:
        """Calculate similarity score 0-1."""
        pass

class ProjectAnalyzer:
    def analyze(self, cwd: str) -> ProjectFingerprint:
        """Analyze project from file structure."""
        # Check package.json, requirements.txt, etc.
        # Detect patterns from directory structure
        # Identify frameworks from imports
        pass
```

### 6.2 Transferable Learnings
```python
@dataclass
class Learning:
    # Existing fields...
    scope: str  # "universal", "language", "framework", "project"
    applicable_to: List[str]  # ["python", "fastapi"] or ["*"]

class LearningTransfer:
    def classify_scope(self, pattern: Pattern) -> str:
        """Determine if learning is transferable."""
        # Tool effectiveness → usually universal
        # Error patterns → often language-specific
        # Skill usage → framework-specific
        pass

    def get_applicable_learnings(self, fingerprint: ProjectFingerprint) -> List[Learning]:
        """Get learnings applicable to this project."""
        pass
```

### 6.3 Team Learning (Optional)
```python
# Requires shared Mind instance or sync mechanism
# Privacy considerations:
# - Anonymize before sharing
# - Opt-in only
# - No code content, only patterns
```

**Files to create:**
- `lib/project_analyzer.py`
- `lib/learning_transfer.py`
- `tests/test_project_analyzer.py`

---

## M7: Advanced Prompt Evolution (SAVED)

**Goal:** Sophisticated genetic algorithm for pattern optimization.

### 7.1 Genetic Mutations
```python
class PatternBreeder:
    def crossover(self, parent_a: PromptPattern, parent_b: PromptPattern) -> PromptPattern:
        """Combine successful patterns."""
        # Take trigger_conditions from A
        # Take approach elements from both
        # Inherit metadata from fitter parent
        pass

    def mutate(self, pattern: PromptPattern, mutation_rate: float = 0.1) -> PromptPattern:
        """Random mutations to explore solution space."""
        # Modify trigger conditions slightly
        # Adjust approach wording
        # Add/remove tool recommendations
        pass

    def select(self, population: List[PromptPattern], k: int) -> List[PromptPattern]:
        """Tournament selection based on fitness."""
        pass

    def evolve_generation(self, population: List[PromptPattern]) -> List[PromptPattern]:
        """Run one generation of evolution."""
        # Select fittest
        # Crossover pairs
        # Mutate offspring
        # Return new population
        pass
```

### 7.2 Context-Aware Prompts
```python
class DynamicPromptAssembler:
    def assemble(self, context: SuggestionContext) -> str:
        """Build prompt dynamically based on context."""
        sections = []

        # Task-specific guidance
        if context.task_category == "search":
            sections.append(self.get_search_guidance())

        # Tool-specific warnings
        if context.current_tool:
            sections.append(self.get_tool_warnings(context.current_tool))

        # Error recovery if recent failure
        if context.recent_errors:
            sections.append(self.get_recovery_guidance(context.recent_errors))

        return "\n".join(sections)
```

### 7.3 Multi-Turn Strategy Learning
```python
@dataclass
class ConversationStrategy:
    strategy_id: str
    when_to_clarify: List[str]  # Conditions for asking questions
    when_to_proceed: List[str]  # Conditions for acting
    verification_points: List[str]  # When to confirm understanding

class StrategyLearner:
    def analyze_conversation(self, session_traces: List[ExecutionTrace]) -> ConversationStrategy:
        """Learn optimal conversation flow from successful sessions."""
        pass
```

**Files to create:**
- `lib/pattern_breeder.py`
- `lib/dynamic_prompt.py`
- `lib/strategy_learner.py`
- `tests/test_pattern_breeder.py`

---

## M8: MCP Server Enhancement (SAVED)

**Goal:** Enable real-time interaction with Spark during sessions.

### 8.1 Mid-Session Queries
```python
# MCP Server endpoints:
@server.tool("spark_status")
async def get_status() -> dict:
    """Get current Spark learning state."""
    return {
        "patterns_active": len(evolver.patterns),
        "suggestions_ready": len(suggester.suggestions),
        "meta_insights": learner.get_recent_insights()
    }

@server.tool("spark_suggest")
async def get_suggestions(task: str) -> List[dict]:
    """Get recommendations for current task."""
    suggester.update_context(task_description=task)
    return suggester.get_relevant_suggestions()

@server.tool("spark_reflect")
async def trigger_reflection(session_id: str) -> dict:
    """Trigger reflection on current session."""
    return evolver.reflect_on_session(session_id)
```

### 8.2 Real-Time Guidance
```python
class RealTimeAdvisor:
    def pre_tool_check(self, tool_name: str, tool_input: dict) -> Optional[str]:
        """Check before tool execution, warn if likely to fail."""
        warnings = suggester.get_warnings_for_tool(tool_name)
        if warnings:
            return self.format_warning(warnings[0])
        return None

    def suggest_alternative(self, failed_tool: str, error: str) -> Optional[str]:
        """Suggest alternative after failure."""
        recovery = evolver.get_pattern_for_task(f"recover_from_{failed_tool}")
        if recovery:
            return recovery.approach
        return None
```

### 8.3 Interactive Evolution
```python
@server.tool("spark_accept")
async def accept_pattern(pattern_id: str) -> bool:
    """Manually accept a pattern suggestion."""
    pass

@server.tool("spark_reject")
async def reject_pattern(pattern_id: str, reason: str) -> bool:
    """Reject a pattern with reason."""
    pass

@server.tool("spark_create")
async def create_pattern(pattern_type: str, description: str, approach: str) -> str:
    """Manually create a new pattern."""
    pass
```

**Files to create/modify:**
- `mcp-server/src/index.ts` (or Python equivalent)
- `lib/realtime_advisor.py`
- `tests/test_mcp_server.py`

---

## M9: Integration Tests (IN PROGRESS)

**Goal:** End-to-end testing to ensure system reliability.

### 9.1 End-to-End Simulation
```python
class SessionSimulator:
    """Simulate a full Claude Code session."""

    async def simulate_session(self, scenario: SessionScenario) -> SessionResult:
        """Run a complete session simulation."""
        # 1. Trigger session_start hook
        # 2. Generate tool events
        # 3. Process through queue
        # 4. Run processor
        # 5. Verify learnings stored
        # 6. Trigger session_end
        # 7. Check injection on next session
        pass

@dataclass
class SessionScenario:
    name: str
    events: List[SparkEvent]
    expected_patterns: List[str]
    expected_learnings: int
```

### 9.2 Chaos Testing
```python
class ChaosTests:
    async def test_mind_unavailable(self):
        """System degrades gracefully when Mind is down."""
        pass

    async def test_malformed_events(self):
        """Handles corrupted event data."""
        pass

    async def test_queue_overflow(self):
        """Handles queue at capacity."""
        pass

    async def test_concurrent_processing(self):
        """Multiple processors don't conflict."""
        pass
```

### 9.3 Performance Benchmarks
```python
class PerformanceBenchmarks:
    def benchmark_hook_latency(self, iterations: int = 1000) -> dict:
        """Measure hook execution time."""
        pass

    def benchmark_queue_throughput(self, events: int = 10000) -> dict:
        """Measure queue write/read speed."""
        pass

    def benchmark_pattern_extraction(self, events: int = 1000) -> dict:
        """Measure learner processing speed."""
        pass
```

**Files to create:**
- `tests/integration/test_session_e2e.py`
- `tests/integration/test_chaos.py`
- `tests/integration/test_performance.py`
- `tests/integration/conftest.py`

---

## M10: Observability & Debugging (SAVED)

**Goal:** Make Spark's behavior transparent and debuggable.

### 10.1 Learning Dashboard
```python
# Streamlit dashboard showing:
# - Pattern count over time
# - Tool effectiveness trends
# - Confidence score distributions
# - Recent learnings list
# - Suggestion hit rate

# File: dashboard/spark_dashboard.py
import streamlit as st

def main():
    st.title("Spark Learning Dashboard")

    # Metrics row
    col1, col2, col3 = st.columns(3)
    col1.metric("Patterns", len(patterns), "+3 today")
    col2.metric("Avg Confidence", "0.78", "+0.02")
    col3.metric("Suggestion Hit Rate", "67%", "+5%")

    # Charts
    st.line_chart(confidence_over_time)
    st.bar_chart(tool_effectiveness)
```

### 10.2 Debug Mode
```python
class SparkDebugger:
    def __init__(self, verbose: bool = True):
        self.verbose = verbose
        self.trace_log = []

    def trace(self, component: str, action: str, details: dict):
        """Log detailed trace information."""
        entry = {
            "timestamp": time.time(),
            "component": component,
            "action": action,
            "details": details
        }
        self.trace_log.append(entry)
        if self.verbose:
            print(f"[SPARK DEBUG] {component}.{action}: {details}")

    def explain_decision(self, decision_type: str) -> str:
        """Explain why Spark made a decision."""
        # Why was this pattern chosen?
        # Why was this suggestion shown?
        # Why was this learning stored/rejected?
        pass
```

### 10.3 Export/Import
```python
class SparkBackup:
    def export_learnings(self, filepath: str):
        """Export all learnings to JSON file."""
        data = {
            "version": "1.0",
            "exported_at": datetime.now().isoformat(),
            "patterns": [p.to_dict() for p in patterns],
            "tool_weights": dict(tool_weights),
            "skill_stats": dict(skill_stats)
        }
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)

    def import_learnings(self, filepath: str, merge: bool = True):
        """Import learnings from JSON file."""
        pass

    def sync_to_git(self, repo_path: str):
        """Version control learnings in git."""
        pass
```

**Files to create:**
- `dashboard/spark_dashboard.py`
- `lib/debugger.py`
- `lib/backup.py`
- `tests/test_backup.py`

---

## Priority Order (Updated)

1. **M9 Integration Tests** ← IN PROGRESS
2. M5 Feedback Loop - Close the improvement cycle
3. M8 MCP Server - Enable real-time interaction
4. M6 Cross-Project - Expand learning scope
5. M7 Advanced Evolution - Sophisticated optimization
6. M10 Observability - Debug and monitor

---

## Success Metrics

| Milestone | Key Metric | Target |
|-----------|------------|--------|
| M5 | Feedback capture rate | >80% of injections tracked |
| M6 | Cross-project transfer | >50% learnings reusable |
| M7 | Pattern fitness improvement | >20% over baseline |
| M8 | Mid-session suggestion usage | >30% acceptance rate |
| M9 | Test coverage | >90% of critical paths |
| M10 | Debug time reduction | <5 min to diagnose issues |

---

*Last updated: 2026-01-23*
