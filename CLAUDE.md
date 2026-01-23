# CLAUDE.md - Spark Development Instructions

## Project Overview

**Spark** is an ambient self-evolving intelligence layer for Claude Code. It's not a tool you invoke—it IS the intelligence that wraps around everything Claude does, observing, measuring, learning, and improving continuously.

## System Status: COMPLETE

**Spark is feature-complete for single-user operation (January 2025)**

| Metric | Value |
|--------|-------|
| Milestones | M1-M11 Complete |
| Components | 21 |
| Tests | 783 passing |
| Health Check | 21/21 healthy |

## Quick Context

Spark is part of the **Vibeship Ecosystem**:
- **Vibeship Mind** - Persistent memory and learning storage (required)
- **Vibeship Spark** - Self-improving orchestration intelligence (this project)
- **Vibeship Spawner** - Skills and agent orchestration

---

## Quick Start

### 1. Start Mind (Required)

```bash
# From the-mind directory
start_mind_lite.bat

# Or manually:
cd C:\Users\USER\Desktop\the-mind\vibeship-mind
python src\mind\lite_tier.py
```

### 2. Verify Spark

```bash
cd C:\Users\USER\Desktop\vibeship-spark
python spark_cli.py health
```

Expected output: `21/21 components healthy`

### 3. That's It!

Spark hooks are already installed. They observe every tool call automatically.

---

## Architecture Overview

See `docs/FLOW.md` for the complete data flow diagram.

```
vibeship-spark/
├── lib/                          # 21 Core components
│   ├── queue.py                  # M1: Event queue (<10ms writes)
│   ├── mind_client.py            # M2: Mind integration
│   ├── learner.py                # M3: Pattern learning
│   ├── prompt_evolver.py         # M4: Prompt evolution
│   ├── meta_learner.py           # M4: Meta-learning
│   ├── suggester.py              # M4: Suggestions
│   ├── injection_tracker.py      # M5: Injection tracking
│   ├── experiment_manager.py     # M5: A/B testing
│   ├── project_analyzer.py       # M6: Project detection
│   ├── learning_transfer.py      # M6: Cross-project learning
│   ├── pattern_breeder.py        # M7: Genetic evolution
│   ├── realtime_advisor.py       # M8: Real-time warnings
│   ├── spark_mcp_server.py       # M8: MCP tools
│   ├── skill_evolver.py          # M9: Skill tracking
│   ├── context_injector.py       # M9: Context injection
│   ├── orchestrator.py           # M9: Agent orchestration
│   ├── spark_dashboard.py        # M10: Terminal UI
│   ├── spark_debugger.py         # M10: Debug/trace
│   ├── spark_backup.py           # M10: Backup/restore
│   └── conflict_resolver.py      # M11: Conflict resolution
├── hooks/                        # Claude Code hooks
│   ├── observe.py                # Capture tool events
│   ├── session_start.py          # Load context
│   └── session_end.py            # Trigger learning
├── mcp-server/                   # Node.js MCP server (built)
├── tests/                        # 783 tests
├── docs/                         # Documentation
│   ├── FLOW.md                   # Data flow diagrams
│   ├── IMPLEMENTATION.md         # Complete status
│   ├── PRD.md                    # Requirements
│   └── ARCHITECTURE.md           # System design
├── processor.py                  # Background processor
└── spark_cli.py                  # CLI interface
```

---

## Development Commands

### Health Check
```bash
python spark_cli.py health
```

### Run Tests
```bash
python -m pytest tests/ -v

# Specific component
python -m pytest tests/test_conflict_resolver.py -v
```

### Process Queue
```bash
# Single pass
python processor.py --mode once

# Background daemon
python processor.py --mode daemon --interval 30

# Deep reflection
python processor.py --mode reflect
```

### Dashboard
```bash
python spark_cli.py dashboard
```

---

## MCP Tools

When the Spark MCP server is loaded, these tools are available:

| Tool | Description |
|------|-------------|
| `spark_status` | System health, Mind connection |
| `spark_learnings` | Query stored learnings |
| `spark_reflect` | Trigger deep reflection |
| `spark_process` | Process pending events |
| `spark_stats` | Learning statistics |
| `spark_clear_queue` | Clear event queue |

---

## Key Design Principles

### 1. Zero Interference
Hooks complete in < 50ms. All heavy processing is background.

### 2. Graceful Degradation
If Mind is unavailable, events queue locally. Learning happens when Mind returns.

### 3. Continuous Evolution
Every action improves the next. No commands needed—Spark is always learning.

### 4. Conflict Resolution
When learnings conflict: scope > score > experiment > recency

---

## The Self-Improvement Loop

```
OBSERVE → DECIDE → ACT → MEASURE → LEARN → IMPROVE → (repeat)
```

1. **OBSERVE**: Capture every tool call and result
2. **DECIDE**: Use learnings to inform approach (context injection)
3. **ACT**: Execute via tools, skills, agents
4. **MEASURE**: Track success/failure, timing, errors
5. **LEARN**: Extract patterns from accumulated data
6. **IMPROVE**: Update behavior weights, evolve prompts/skills

---

## Mind Memory Types

| Type | Temporal Level | What's Stored |
|------|----------------|---------------|
| Events | 2 (Situational) | Tool calls, results |
| Patterns | 3 (Seasonal) | Extracted patterns |
| Learnings | 4 (Identity) | High-confidence insights |
| Meta | 4 (Identity) | Statistics, rankings |

---

## Startup Requirements

| Service | Required | How |
|---------|----------|-----|
| Mind API | Yes | `start_mind_lite.bat` |
| Spark Hooks | Auto | Already in `~/.claude/settings.json` |
| MCP Server | Auto | Started by Claude Code |
| Processor | Optional | `python processor.py --mode daemon` |

---

## Query Learnings

```bash
curl -s -X POST http://localhost:8080/v1/memories/retrieve \
  -H "Content-Type: application/json" \
  -d '{"query":"LEARNING"}' | python -m json.tool
```

---

## Continuation Prompt

When starting a new session:

> "I'm continuing development of Spark. Run `python spark_cli.py health` to verify all 21 components are healthy. Check `docs/IMPLEMENTATION.md` for complete status and `docs/FLOW.md` for system flow."

---

## Important Notes

1. **Hooks load at session start** - Changes require Claude Code restart
2. **Mind must be running** - For persistent learning storage
3. **Queue is file-based** - At `~/.spark/queue/events.jsonl`
4. **User-level install** - Works across all projects

---

## Documentation

| Doc | Purpose |
|-----|---------|
| `docs/FLOW.md` | Complete data flow diagrams |
| `docs/IMPLEMENTATION.md` | M1-M11 status, component details |
| `docs/PRD.md` | Product requirements |
| `docs/ARCHITECTURE.md` | System design |
| `docs/TESTING.md` | Test strategy |

---

## Deferred Features

| Feature | Reason |
|---------|--------|
| Cross-user learning sharing | Requires team infrastructure |
| TypeScript MCP server | Python server works |
| Periodic reflection scheduling | Can be added to processor |
