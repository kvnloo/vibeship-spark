# Spark Continuation Prompt

Use this prompt when starting a new Claude Code session to continue Spark development.

---

## Quick Start Prompt

Copy and paste this at the start of a new session:

```
I'm continuing development of Spark, the ambient self-evolving intelligence layer for Claude Code.

## Current State
- Spark hooks are installed at user level (~/.claude/settings.json)
- Core library (queue, learner, mind_client) is complete
- Event capture and pattern extraction are working
- Mind integration is functional

## Immediate Priorities (M2)
1. Create unit tests in tests/ directory
2. Build and test the MCP server in mcp-server/
3. Enhance context injection in session_start.py

## Commands to Verify State
- `python setup.py status` - Check system health
- `python setup.py test` - Run basic tests
- `python processor.py --mode once` - Process pending events

## Key Documentation
- CLAUDE.md - Development instructions
- docs/PRD.md - Full requirements
- docs/ARCHITECTURE.md - System design
- docs/IMPLEMENTATION.md - Status and plan
- docs/TESTING.md - Test strategy

Please check IMPLEMENTATION.md for detailed status and next steps.
```

---

## Detailed Context

### What Spark Does

Spark wraps around Claude Code as an ambient intelligence layer:
- **Observes** every tool call via hooks
- **Measures** success/failure of actions
- **Learns** patterns from accumulated data
- **Improves** future decisions based on learnings

### Architecture Overview

```
Claude Code
    │
    ▼
┌─────────────────────────────────────┐
│          SPARK LAYER                │
│                                     │
│  OBSERVE → DECIDE → ACT → MEASURE  │
│     ▲                      │        │
│     └── LEARN ← IMPROVE ←──┘        │
└─────────────────────────────────────┘
    │
    ▼
Vibeship Mind (Persistent Memory)
```

### Files to Know

| File | Purpose |
|------|---------|
| `lib/queue.py` | Ultra-fast event capture |
| `lib/learner.py` | Pattern extraction |
| `lib/mind_client.py` | Mind API client |
| `hooks/observe.py` | Main observation hook |
| `processor.py` | Background learning engine |
| `setup.py` | Installation management |

### What's Working

- [x] Hook system (PreToolUse, PostToolUse, etc.)
- [x] Event queue (< 10ms writes)
- [x] Pattern extraction (tool_effectiveness, error_avoidance)
- [x] Mind storage (temporal_level 4 for learnings)
- [x] Basic context injection

### What's Remaining

- [ ] Unit tests (see docs/TESTING.md)
- [ ] MCP server (see mcp-server/)
- [ ] Enhanced context filtering
- [ ] Skill evolution system
- [ ] Prompt evolution system
- [ ] Meta-learning

---

## Development Workflow

### 1. Check System State
```bash
cd C:\Users\USER\Desktop\vibeship-spark
python setup.py status
```

### 2. Start Mind (if needed)
```bash
cd C:\Users\USER\Desktop\the-mind\vibeship-mind
python src\mind\lite_tier.py
```

### 3. Run Tests
```bash
python setup.py test
pytest tests/ -v  # When tests are created
```

### 4. Process Events
```bash
python processor.py --mode once
```

### 5. Check Learnings
```bash
curl -s -X POST http://localhost:8080/v1/memories/retrieve \
  -H "Content-Type: application/json" \
  -d '{"query":"LEARNING"}' | python -m json.tool
```

---

## Current Learnings in Mind

The system has already learned:
- Tool effectiveness patterns (e.g., "Bash has 87% success rate")
- Stored at temporal_level 4 (identity/permanent)

---

## Key Design Decisions

1. **Hooks must be < 50ms** - Never block Claude
2. **Queue is file-based** - Simple, reliable, survives crashes
3. **Mind is the source of truth** - All learnings persist there
4. **Confidence threshold 0.7** - Only high-confidence patterns are stored
5. **Graceful degradation** - Works without Mind (events queue locally)

---

## Questions to Consider

When continuing development:

1. **For Tests**: What edge cases need coverage?
2. **For MCP**: What tools would be most useful?
3. **For Evolution**: How should skills/prompts evolve?
4. **For Meta-Learning**: How do we know if learnings are helping?
