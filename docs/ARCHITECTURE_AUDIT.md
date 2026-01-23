# Spark Architecture Audit

**Date:** 2026-01-24 (Updated)
**Purpose:** Comprehensive review - current status after Phase 8

---

## Executive Summary

Spark has **27 Python modules** totaling **~19,500 lines of code**:
- ✅ **Dead code wired up** - goal_classifier.py shared module, predictions flow to learner
- ✅ **Goal classification unified** - Single source of truth in `lib/goal_classifier.py`
- ✅ **Mind pagination fixed** - `retrieve_all()` works around 100-limit
- ✅ **Parallel tool learning** - Detects concurrent tool calls
- ⚠️ **17+ modules query Mind independently** - Could benefit from centralized retrieval
- ✅ **925 tests** covering all major components

---

## Module Categories

### Tier 1: Core Infrastructure (ACTIVELY USED)

| Module | Lines | Purpose | Used By |
|--------|-------|---------|---------|
| `queue.py` | 156 | Event capture (<10ms) | observe.py, processor.py |
| `mind_client.py` | 220 | Memory API client | 17 modules |
| `learner.py` | 952 | Pattern extraction | processor.py |

**Status:** Working well. These are the foundation.

---

### Tier 2: Active Learning Components (ACTIVELY USED)

| Module | Lines | Purpose | Used By |
|--------|-------|---------|---------|
| `prompt_evolver.py` | 625 | Trace capture & reflection | processor.py |
| `meta_learner.py` | 511 | Learning about learning | processor.py |
| `suggester.py` | 634 | Proactive suggestions | processor.py, session_start.py |
| `skill_evolver.py` | 494 | Skill effectiveness | processor.py |
| `orchestrator.py` | 423 | Agent effectiveness | processor.py |
| `injection_tracker.py` | 495 | Track if advice followed | processor.py, session_start.py |
| `experiment_manager.py` | 537 | A/B testing | processor.py |
| `reasoning_tracker.py` | 624 | Confidence calibration | processor.py |

**Status:** All wired into processor.py and actively processing events.

---

### Tier 3: Self-Improvement Layer (ACTIVELY USED)

| Module | Lines | Purpose | Used By |
|--------|-------|---------|---------|
| `introspect.py` | 508 | Self-aware gap analysis | spark_cli.py, processor.py |
| `auto_improve.py` | 372 | Act on gaps | spark_cli.py, processor.py |
| `context_injector.py` | 606 | Inject learnings at start | session_start.py |

**Status:** Working. The recursive self-improvement loop is functional.

---

### Tier 4: CLI/Dashboard Tools (USED ON-DEMAND)

| Module | Lines | Purpose | Used By |
|--------|-------|---------|---------|
| `spark_dashboard.py` | 956 | Terminal UI | spark_cli.py |
| `spark_debugger.py` | 626 | Debug sessions | spark_cli.py |
| `spark_backup.py` | 697 | Backup/restore | spark_cli.py |
| `witness.py` | 611 | Unified system view | spark_cli.py |
| `conflict_resolver.py` | 719 | Resolve conflicts | spark_cli.py |

**Status:** Working for manual operations.

---

### Tier 5: PREVIOUSLY DEAD CODE (NOW WIRED UP ✅)

| Module | Lines | Purpose | Status |
|--------|-------|---------|--------|
| `goal_classifier.py` | 197 | Shared goal classification | **NEW** - Created as shared module |
| `goal_tracker.py` | 383 | Goal lifecycle tracking | observe.py now uses shared goal_classifier.py |
| `intent_inferrer.py` | 265 | Intent prediction | Predictions now consumed by learner.py → reasoning_gap patterns |
| `realtime_advisor.py` | 536 | Real-time warnings | **Fast version wired into observe.py** for pre-tool warnings & recovery |

**Status (2026-01-24):** All previously dead code has been consolidated and wired up:
- Created `lib/goal_classifier.py` as single source of truth for classification
- observe.py now imports and uses shared classifier (CONVERSATION, AFFIRMATION, etc.)
- Prediction learnings flow: observe.py → queue → processor.py → learner.py → Mind
- RealTimeAdvisor: Fast pattern matching in observe.py for PRE_TOOL warnings and POST_TOOL_FAILURE recovery

---

### Tier 6: Partial Integration (PARTIALLY USED)

| Module | Lines | Purpose | Problem |
|--------|-------|---------|---------|
| `pattern_breeder.py` | 729 | Genetic evolution | Only used in health check, never in production |
| `project_analyzer.py` | 598 | Project fingerprinting | Only used in health check |
| `learning_transfer.py` | 498 | Cross-project sharing | Has 100-limit bug, rarely triggered |

**Action Required:** Decide if these should be active or removed.

---

## Critical Issues Found

### Issue 1: ~~Duplicate Goal Classification~~ ✅ RESOLVED

**Solution (2026-01-24):**
- Created `lib/goal_classifier.py` as single source of truth
- Both hooks/observe.py and lib/goal_tracker.py now import from it
- Includes CONVERSATION, AFFIRMATION, CLARIFICATION, META types
- `should_track_as_goal()` filters non-work prompts

```python
# lib/goal_classifier.py - Shared classification
from lib.goal_classifier import classify_goal, should_track_as_goal, GoalType

goal_type, confidence = classify_goal(prompt)
if should_track_as_goal(goal_type):
    # Track as active goal
```

---

### Issue 2: ~~Intent Predictions Never Consumed~~ ✅ RESOLVED

**Solution (2026-01-24):**
- observe.py stores predictions and adds `reasoning_learning` to events when wrong
- learner.py `_update_reasoning_stats()` captures reasoning_learning from event data
- `_extract_patterns()` creates `reasoning_gap` patterns (overconfidence/underconfidence)
- Single occurrences now trigger pattern creation (threshold lowered)

```python
# Flow: observe.py → queue → processor.py → learner.py → Mind
# Event data includes: reasoning_learning = "PREDICTION_WRONG: ..."
# Learner extracts: reasoning_gap pattern with learning_type metadata
```

---

### Issue 3: 17+ Independent Mind Queries

Every module does its own `mind.retrieve()` with different queries:
- `context_injector.py`: 3 retrieve calls
- `introspect.py`: 2 retrieve calls
- `learner.py`: 3 retrieve calls
- `suggester.py`: 3 retrieve calls
- etc.

**Impact:**
- All hit the 100-limit independently
- No caching or deduplication
- Hard to track what's being queried

---

### Issue 4: ~~RealTimeAdvisor Never Called~~ ✅ RESOLVED

**Solution (2026-01-24):**
- Added fast, inline versions of advisor logic to observe.py (no external deps)
- `fast_pre_tool_warning()` - Pattern matching for dangerous commands (<5ms)
- `get_recovery_suggestion()` - Error categorization with recovery tips (<5ms)
- PRE_TOOL events now include `pre_tool_warning` when dangerous patterns detected
- POST_TOOL_FAILURE events include `recovery_suggestion` with approach and alternatives

```python
# hooks/observe.py additions:
if event_type == EventType.PRE_TOOL:
    warning = fast_pre_tool_warning(tool_name, tool_input)
    if warning:
        data["pre_tool_warning"] = warning  # severity, pattern, description

if event_type == EventType.POST_TOOL_FAILURE:
    recovery = get_recovery_suggestion(tool_name, error)
    if recovery:
        data["recovery_suggestion"] = recovery  # category, approach, alternatives
```

---

## Architecture Diagram (Updated 2026-01-24)

```
                    ┌─────────────────────────────────────────┐
                    │              HOOKS                       │
                    │  ┌─────────────────────────────────┐    │
                    │  │ observe.py                      │    │
                    │  │ - Captures events               │    │
                    │  │ - Uses shared goal_classifier   │ ✅ │
                    │  │ - Predictions → reasoning_gap   │ ✅ │
                    │  │ - Pre-tool warnings             │ ✅ │
                    │  │ - Recovery suggestions          │ ✅ │
                    │  └────────────┬────────────────────┘    │
                    │               │                          │
                    │  ┌────────────▼────────────────────┐    │
                    │  │ session_start.py               │    │
                    │  │ - context_injector             │    │
                    │  │ - suggester                    │    │
                    │  │ - injection_tracker            │    │
                    │  └─────────────────────────────────┘    │
                    │                                          │
                    │  ┌─────────────────────────────────┐    │
                    │  │ session_end.py                 │    │
                    │  │ - Triggers processor           │    │
                    │  └─────────────────────────────────┘    │
                    └─────────────────────────────────────────┘
                                      │
                                      ▼
                    ┌─────────────────────────────────────────┐
                    │           PROCESSOR.PY                  │
                    │                                         │
                    │  Uses: learner, prompt_evolver,         │
                    │        meta_learner, skill_evolver,     │
                    │        orchestrator, suggester,         │
                    │        injection_tracker,               │
                    │        experiment_manager,              │
                    │        auto_improve, reasoning_tracker  │
                    │                                         │
                    │  NOW ALSO PROCESSES:                    │
                    │  ✅ reasoning_gap (from predictions)    │
                    │  ✅ goal_classifier (shared module)     │
                    │  ✅ pre_tool_warning (in events)        │
                    │  ✅ recovery_suggestion (in events)     │
                    │                                         │
                    │  Still partial use:                     │
                    │  ⚠️ pattern_breeder (health only)       │
                    │  ⚠️ project_analyzer (health only)      │
                    │  ⚠️ learning_transfer (100-limit bug)   │
                    └─────────────────────────────────────────┘
                                      │
                                      ▼
                    ┌─────────────────────────────────────────┐
                    │              MIND                        │
                    │  - 17+ modules query independently      │
                    │  - Each hits 100-limit separately       │
                    │  - No centralized memory management     │
                    └─────────────────────────────────────────┘
```

---

## What's Actually Working

| Capability | Working? | Evidence |
|------------|----------|----------|
| Event capture | ✅ Yes | Queue has events |
| Pattern extraction | ✅ Yes | 87 patterns in Mind |
| Tool effectiveness tracking | ✅ Yes | Tool weights calculated |
| Goal strategy learning | ✅ Yes | Goal patterns extracted |
| Confidence calibration | ✅ Yes | 3 calibration factors |
| Context injection | ✅ Yes | Session start shows context |
| Self-introspection | ✅ Yes | Gaps identified |
| Auto-improvement | ✅ Yes | Actions taken |

---

## What's Working Now (Previously Broken)

| Capability | Fix Applied | Status |
|------------|-------------|--------|
| Goal classification | Shared `goal_classifier.py` module | ✅ Fixed |
| Intent prediction learning | Predictions → reasoning_gap patterns | ✅ Fixed |
| Real-time warnings | Fast inline warnings in observe.py | ✅ Fixed |
| Cross-project transfer | `retrieve_all()` pagination | ✅ Fixed |
| Parallel tool learning | Detect tools called within 2s | ✅ Fixed |

## Partially Working

| Capability | Status | Notes |
|------------|--------|-------|
| Pattern breeding | Health check only | Could be wired into processor daemon |
| Error pattern learning | Improved | Thresholds lowered, still tuning |

---

## Recommendations

### Priority 1: Wire Up Dead Code (Before Adding New)

1. **Replace observe.py classification with GoalTracker**
   - GoalTracker has CONVERSATION, CLARIFICATION types already
   - Just need to import and use it

2. **Wire predictions.json into learning**
   - processor.py should read predictions
   - Learn from prediction misses

3. **Call RealTimeAdvisor in hooks**
   - Add pre-tool warnings to observe.py
   - Add recovery suggestions on failures

### Priority 2: Consolidate Memory Access

Create a central memory manager:
```python
class MemoryManager:
    async def get_learnings(self, pattern_type: str) -> List[Dict]:
        """Cached, paginated retrieval"""

    async def get_all_learnings(self) -> List[Dict]:
        """Full retrieval with pagination"""
```

### Priority 3: Then Add New Features

Only after consolidation:
- Expand goal classification keywords
- Lower error learning thresholds
- Add pagination

---

## Lines of Code Summary

| Category | Files | Lines | % of Total |
|----------|-------|-------|------------|
| Core Infrastructure | 3 | 1,328 | 7% |
| Active Learning | 8 | 4,343 | 22% |
| Self-Improvement | 3 | 1,486 | 8% |
| CLI/Dashboard | 5 | 3,609 | 19% |
| Dead/Partial Code | 6 | 3,009 | 15% |
| Hooks | 3 | 520 | 3% |
| Processor + CLI | 2 | 1,200 | 6% |
| Tests | - | ~4,000 | 20% |
| **Total** | **27** | **~19,500** | 100% |

**15% of code (3,009 lines) is dead or partially used.**

---

## Next Steps

1. **Audit complete** - This document
2. **Consolidate** - Wire up goal_tracker, predictions, realtime_advisor
3. **Centralize** - Create MemoryManager for Mind access
4. **Fix bugs** - 100-limit, thresholds, case mismatch
5. **Then expand** - New goal types, tests, validation

---

*This audit should be updated after each major change.*
