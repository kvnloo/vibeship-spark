# CLAUDE.md - Spark Development Instructions

## Project Overview

**Spark** is an ambient self-evolving intelligence layer for Claude Code. It's not a tool you invoke—it IS the intelligence that wraps around everything Claude does, observing, measuring, learning, and improving continuously.

## Quick Context

Spark is part of the **Vibeship Ecosystem**:
- **Vibeship Mind** - Persistent memory and learning storage
- **Vibeship Spark** - Self-improving orchestration intelligence (this project)
- **Vibeship Spawner** - Skills and agent orchestration

## Current Status (January 2025)

### What's Working
- [x] Hook system installed at user level (`~/.claude/settings.json`)
- [x] Event capture via queue (< 50ms, non-blocking)
- [x] Mind integration for persistent learning
- [x] Pattern extraction (tool effectiveness, error avoidance)
- [x] Background processor for learning
- [x] Basic tests passing

### What's Remaining
- [ ] MCP server for direct Spark invocation
- [ ] Unit tests for all components
- [ ] Skill evolution system
- [ ] Prompt evolution system
- [ ] Agent orchestration learning
- [ ] Session context injection (learnings → Claude)
- [ ] Meta-learning (learning about learning)

## Architecture

```
vibeship-spark/
├── lib/                    # Core library
│   ├── queue.py           # Ultra-fast event capture
│   ├── mind_client.py     # Async Mind integration
│   └── learner.py         # Pattern extraction engine
├── hooks/                  # Claude Code hooks
│   ├── observe.py         # Captures tool events
│   ├── session_start.py   # Loads context from Mind
│   └── session_end.py     # Triggers learning
├── mcp-server/            # MCP server (TODO)
│   └── src/
├── tests/                 # Unit tests (TODO)
├── docs/                  # Documentation
│   ├── PRD.md            # Product requirements
│   ├── ARCHITECTURE.md   # System design
│   ├── IMPLEMENTATION.md # Implementation plan
│   └── TESTING.md        # Test strategy
├── processor.py           # Background learning processor
├── setup.py              # Installation/management
└── spark-hooks.json      # Hook configuration
```

## Development Commands

### Check Status
```bash
python setup.py status
```

### Run Tests
```bash
python setup.py test

# Unit tests (when implemented)
pytest tests/ -v
```

### Process Queue Manually
```bash
python processor.py --mode once
```

### Run Learning Daemon
```bash
python processor.py --mode daemon --interval 30
```

### Run Deep Reflection
```bash
python processor.py --mode reflect
```

## Key Design Principles

### 1. Zero Interference
Hooks complete in < 50ms. All heavy processing is background.

### 2. Graceful Degradation
If Mind is unavailable, events queue locally. Learning happens when Mind returns.

### 3. Continuous Evolution
Every action improves the next. No commands needed—Spark is always learning.

### 4. Mind is the Core
All learnings persist in Vibeship Mind at temporal_level 4 (identity/permanent).

## The Self-Improvement Loop

```
OBSERVE → DECIDE → ACT → MEASURE → LEARN → IMPROVE → (repeat)
```

1. **OBSERVE**: Capture every tool call and result
2. **DECIDE**: Use learnings to inform decisions (TODO: implement)
3. **ACT**: Execute via tools, skills, agents
4. **MEASURE**: Track success/failure, timing, errors
5. **LEARN**: Extract patterns from accumulated data
6. **IMPROVE**: Update behavior weights, evolve prompts/skills

## Mind Memory Types

| Type | Temporal Level | What's Stored |
|------|----------------|---------------|
| Events | 2 (Situational) | Tool calls, results |
| Patterns | 3 (Seasonal) | Extracted patterns |
| Learnings | 4 (Identity) | High-confidence insights |
| Meta | 4 (Identity) | Statistics, rankings |

## Environment Requirements

- Python 3.11+
- Vibeship Mind running at http://localhost:8080
- aiohttp for async HTTP

## Starting Mind

```bash
cd C:\Users\USER\Desktop\the-mind\vibeship-mind
python src\mind\lite_tier.py
```

Or use:
```bash
powershell -Command "Start-Process python -ArgumentList 'C:/Users/USER/Desktop/the-mind/vibeship-mind/src/mind/lite_tier.py' -WorkingDirectory 'C:/Users/USER/Desktop/the-mind/vibeship-mind'"
```

## Key Files to Know

| File | Purpose |
|------|---------|
| `lib/queue.py` | Event capture, must be < 10ms |
| `lib/learner.py` | Pattern extraction logic |
| `lib/mind_client.py` | Mind API wrapper |
| `hooks/observe.py` | Main observation hook |
| `processor.py` | Background learning engine |

## Current Learnings in Mind

Query with:
```bash
curl -s -X POST http://localhost:8080/v1/memories/retrieve \
  -H "Content-Type: application/json" \
  -d '{"query":"LEARNING"}' | python -m json.tool
```

## Continuation Prompt

When starting a new session, use this context:

> "I'm continuing development of Spark, the ambient self-evolving intelligence layer.
> Check docs/IMPLEMENTATION.md for current status and next steps.
> Run `python setup.py status` to verify the system state.
> Key priorities: MCP server, unit tests, skill evolution, meta-learning."

## Important Notes

1. **Hooks load at session start** - Changes require Claude Code restart
2. **Mind must be running** - For persistent learning storage
3. **Queue is file-based** - At `~/.spark/queue/events.jsonl`
4. **User-level install** - Works across all projects

## Related Documentation

- `docs/PRD.md` - Full product requirements
- `docs/ARCHITECTURE.md` - Detailed system design
- `docs/IMPLEMENTATION.md` - Implementation status and plan
- `docs/TESTING.md` - Test strategy and coverage
