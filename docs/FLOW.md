# Spark System Flow

## Overview

Spark is an ambient self-evolving intelligence layer. It observes every action, learns from outcomes, and improves future behavior automatically.

```
SESSION START
     │
     ▼
┌─────────────────────────────────────────────────────────────────┐
│                    SPARK INTELLIGENCE LAYER                      │
│                                                                   │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐   │
│  │ Context  │    │ Real-Time│    │ Pattern  │    │ Conflict │   │
│  │ Injector │───▶│ Advisor  │───▶│ Breeder  │───▶│ Resolver │   │
│  └──────────┘    └──────────┘    └──────────┘    └──────────┘   │
│       │                │                                         │
└───────┼────────────────┼─────────────────────────────────────────┘
        │                │
        ▼                ▼
   ┌─────────┐     ┌──────────────┐
   │ Inject  │     │ Pre-Tool     │
   │ Context │     │ Warnings     │
   └─────────┘     └──────────────┘
        │                │
        ▼                ▼
┌─────────────────────────────────────────────────────────────────┐
│                        TOOL EXECUTION                            │
│    (Bash, Read, Edit, Write, Grep, Glob, etc.)                   │
└─────────────────────────────────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────────────────────────────────┐
│                      OBSERVE (hooks/observe.py)                  │
│                                                                   │
│  Captures: tool_name, input, output, success, error, timing      │
│  Latency: < 50ms (non-blocking)                                  │
└─────────────────────────────────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────────────────────────────────────┐
│                      EVENT QUEUE (~/.spark/queue/)               │
│                                                                   │
│  File: events.jsonl                                              │
│  Format: One JSON event per line                                 │
│  Write time: < 10ms                                              │
└─────────────────────────────────────────────────────────────────┘
        │
        │ (Background processor.py)
        ▼
┌─────────────────────────────────────────────────────────────────┐
│                      LEARNING PIPELINE                           │
│                                                                   │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐       │
│  │ SparkLearner │───▶│PromptEvolver │───▶│ MetaLearner  │       │
│  │              │    │              │    │              │       │
│  │ - Extract    │    │ - Trace      │    │ - Meta-      │       │
│  │   patterns   │    │   prompts    │    │   patterns   │       │
│  │ - Track      │    │ - Evolve     │    │ - Cross-     │       │
│  │   tools      │    │   strategies │    │   domain     │       │
│  │ - Categorize │    │              │    │              │       │
│  │   errors     │    │              │    │              │       │
│  └──────────────┘    └──────────────┘    └──────────────┘       │
│         │                   │                   │                │
│         └───────────────────┴───────────────────┘                │
│                             │                                    │
└─────────────────────────────┼────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      VIBESHIP MIND                               │
│                      (localhost:8080)                            │
│                                                                   │
│  Stores:                                                         │
│  - Events (temporal_level=2)                                     │
│  - Patterns (temporal_level=3)                                   │
│  - Learnings (temporal_level=4)                                  │
│  - Meta-insights (temporal_level=4)                              │
└─────────────────────────────────────────────────────────────────┘
        │
        │ (Next session)
        ▼
   SESSION START (repeat)
```

---

## Component Data Flow

### 1. Session Start → Context Injection

```
session_start.py
       │
       ▼
┌─────────────────┐     ┌─────────────────┐
│ ContextInjector │────▶│    Mind API     │
│                 │     │   /retrieve     │
└─────────────────┘     └─────────────────┘
       │
       ▼
  Returns context:
  - Recent learnings
  - Project patterns
  - Tool recommendations
```

### 2. Tool Use → Observation

```
PreToolUse/PostToolUse Hook
       │
       ▼
┌─────────────────┐
│   observe.py    │
│                 │
│ Creates event:  │
│ - event_type    │
│ - tool_name     │
│ - tool_input    │
│ - tool_output   │
│ - success       │
│ - error_type    │
│ - latency_ms    │
│ - session_id    │
│ - project_path  │
└─────────────────┘
       │
       ▼
┌─────────────────┐
│   SparkQueue    │
│                 │
│ Appends to:     │
│ events.jsonl    │
└─────────────────┘
```

### 3. Background Processing → Learning

```
processor.py (daemon mode)
       │
       ▼
┌─────────────────────────────────────────────────────────────┐
│                    PROCESSING PIPELINE                       │
│                                                              │
│  1. SparkLearner.process_events()                           │
│     - Track tool success/failure rates                      │
│     - Categorize errors                                     │
│     - Extract tool sequences                                │
│                                                              │
│  2. PromptEvolver.analyze_traces()                          │
│     - Identify prompt patterns                              │
│     - Track approach effectiveness                          │
│     - Evolve successful strategies                          │
│                                                              │
│  3. MetaLearner.extract_meta_patterns()                     │
│     - Cross-domain patterns                                 │
│     - Learning velocity                                     │
│     - Improvement areas                                     │
│                                                              │
│  4. InjectionTracker.track_outcomes()                       │
│     - Did Claude follow recommendations?                    │
│     - Was the outcome better?                               │
│                                                              │
│  5. ExperimentManager.evaluate()                            │
│     - A/B test results                                      │
│     - Statistical significance                              │
│                                                              │
│  6. ConflictResolver.resolve()                              │
│     - Handle conflicting learnings                          │
│     - Apply decay to outdated patterns                      │
└─────────────────────────────────────────────────────────────┘
       │
       ▼
┌─────────────────┐
│   Mind API      │
│   /memories/    │
│                 │
│ Stores as:      │
│ - LEARNING      │
│ - PATTERN       │
│ - META_INSIGHT  │
└─────────────────┘
```

### 4. Conflict Resolution Flow

```
Multiple learnings for same trigger
       │
       ▼
┌─────────────────────────────────────────────────────────────┐
│                   CONFLICT RESOLVER                          │
│                                                              │
│  Layer 1: SCOPE HIERARCHY                                   │
│  ─────────────────────────                                  │
│  session > project > framework > language > universal       │
│  More specific scope wins                                   │
│                                                              │
│  Layer 2: EFFECTIVE SCORE                                   │
│  ─────────────────────────                                  │
│  score = confidence × recency_factor × sample_weight        │
│  - confidence = success_count / total_uses                  │
│  - recency = 0.5 + 0.5 × exp(-age / decay_half_life)       │
│  - sample_weight = min(1.0, samples / 20)                   │
│                                                              │
│  Layer 3: MERGE (if compatible)                             │
│  ─────────────────────────────                              │
│  Non-overlapping triggers → combined pattern                │
│                                                              │
│  Layer 4: EXPERIMENT (if close call)                        │
│  ────────────────────────────────────                       │
│  Score ratio < 1.5 → A/B test via ExperimentManager         │
│                                                              │
│  Layer 5: RECENCY (tie-breaker)                             │
│  ───────────────────────────────                            │
│  Most recently updated wins                                 │
└─────────────────────────────────────────────────────────────┘
```

---

## Startup Requirements

### What Must Be Running

| Service | Required | Start Command |
|---------|----------|---------------|
| Mind API | Yes | `python src/mind/lite_tier.py` |
| Spark Hooks | Auto | Installed in `~/.claude/settings.json` |
| MCP Server | Auto | Started by Claude Code on demand |
| Processor | Optional | `python processor.py --mode daemon` |

### One-Line Start (Recommended)

```bash
# From the-mind directory:
start_mind_lite.bat

# Or PowerShell:
Start-Process python -ArgumentList 'C:/Users/USER/Desktop/the-mind/vibeship-mind/src/mind/lite_tier.py' -WorkingDirectory 'C:/Users/USER/Desktop/the-mind/vibeship-mind'
```

### Verify Everything Works

```bash
# Check Mind
curl http://localhost:8080/health

# Check Spark
python spark_cli.py health

# Check MCP (via Claude)
# Just use any spark_* tool
```

---

## MCP Tools Available

When Spark MCP server is running, these tools are available to Claude:

| Tool | Description |
|------|-------------|
| `spark_status` | System health, Mind connection, queue size |
| `spark_learnings` | Query stored learnings from Mind |
| `spark_reflect` | Trigger deep reflection and pattern analysis |
| `spark_process` | Process pending events in queue |
| `spark_stats` | Learning statistics and tool effectiveness |
| `spark_clear_queue` | Clear event queue (use with caution) |

---

## Real-Time Advisor Flow

```
Claude about to use a tool
       │
       ▼
┌─────────────────┐
│ RealTimeAdvisor │
│                 │
│ 1. Pre-check    │──────▶ Known failure patterns?
│                 │        Previous errors with this tool?
│                 │        Better alternative available?
│                 │
│ 2. Warnings     │──────▶ Return warning if risk detected
│                 │
│ 3. Suggestions  │──────▶ Task guidance based on category
└─────────────────┘
       │
       ▼
  Tool executes with enhanced awareness
```

---

## Dashboard Views

Access via `python spark_cli.py dashboard`:

| View | Shows |
|------|-------|
| OVERVIEW | System health, patterns, queue |
| PATTERNS | Extracted patterns with scores |
| EXPERIMENTS | A/B tests, significance |
| LEARNINGS | Recent learnings, salience |
| QUEUE | Pending events |
| SESSION | Current session activity |
| CONFLICTS | Detected conflicts, resolutions |
| SETTINGS | Decay rate, thresholds |

---

## File System Layout

```
~/.spark/                    # Spark data directory
├── queue/
│   └── events.jsonl        # Event queue (processed by daemon)
├── learnings/              # Local cache (backup)
└── config.json             # Spark settings

~/.claude/
└── settings.json           # Hook configuration (auto-installed)

~/.mind/
└── lite/
    └── memories.db         # SQLite database (Mind storage)

vibeship-spark/
├── lib/                    # 21 components
├── hooks/                  # 3 hook scripts
├── mcp-server/            # Node.js MCP server
├── tests/                 # 783 tests
├── processor.py           # Background processor
└── spark_cli.py           # CLI interface
```

---

## The Self-Improvement Loop

```
┌─────────────────────────────────────────────────────────────────┐
│                                                                   │
│    OBSERVE ──────▶ DECIDE ──────▶ ACT ──────▶ MEASURE            │
│       ▲                                           │               │
│       │                                           ▼               │
│    IMPROVE ◀────── LEARN ◀───────────────────────┘               │
│                                                                   │
└─────────────────────────────────────────────────────────────────┘

OBSERVE: Capture tool calls, inputs, outputs, errors, timing
DECIDE:  Use past learnings to inform approach (context injection)
ACT:     Execute via tools, skills, agents
MEASURE: Track success/failure, compare to predictions
LEARN:   Extract patterns, update confidence scores
IMPROVE: Evolve prompts, adjust recommendations, breed patterns
```

---

## Temporal Storage Strategy

| Level | What | Retention | Example |
|-------|------|-----------|---------|
| 1 - Immediate | Raw events | 24 hours | Tool call details |
| 2 - Situational | Session context | 7 days | Session patterns |
| 3 - Seasonal | Project patterns | 90 days | Project-specific learnings |
| 4 - Identity | Core learnings | Permanent | "Read always reads files faster than Bash" |

---

## Quick Reference

### Start Everything
```bash
# Mind (required)
start_mind_lite.bat

# Processor (optional, runs learning in background)
python processor.py --mode daemon --interval 30
```

### Check Status
```bash
python spark_cli.py status
python spark_cli.py health
```

### Manual Learning
```bash
python processor.py --mode once    # Process queue once
python processor.py --mode reflect # Deep reflection
```

### View Dashboard
```bash
python spark_cli.py dashboard
```

### Query Learnings
```bash
curl -X POST http://localhost:8080/v1/memories/retrieve \
  -H "Content-Type: application/json" \
  -d '{"query":"LEARNING"}'
```
