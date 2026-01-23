# Spark Architecture

## System Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           CLAUDE CODE SESSION                                │
│                                                                             │
│  ┌───────────────────────────────────────────────────────────────────────┐ │
│  │                         SPARK LAYER                                    │ │
│  │              (Ambient Self-Evolving Intelligence)                      │ │
│  │                                                                        │ │
│  │   ╔═══════════════════════════════════════════════════════════════╗   │ │
│  │   ║  ALWAYS RUNNING - NO COMMANDS NEEDED - CONSTANT EVOLUTION     ║   │ │
│  │   ╚═══════════════════════════════════════════════════════════════╝   │ │
│  │                                                                        │ │
│  │   ┌────────────┐   ┌────────────┐   ┌────────────┐   ┌────────────┐  │ │
│  │   │  OBSERVE   │──▶│   DECIDE   │──▶│    ACT     │──▶│  MEASURE   │  │ │
│  │   └────────────┘   └────────────┘   └────────────┘   └────────────┘  │ │
│  │         ▲                                                   │         │ │
│  │         │              ┌────────────┐                       │         │ │
│  │         │              │   LEARN    │◀──────────────────────┘         │ │
│  │         │              └─────┬──────┘                                 │ │
│  │         │              ┌─────▼──────┐                                 │ │
│  │         └──────────────│  IMPROVE   │                                 │ │
│  │                        └────────────┘                                 │ │
│  └───────────────────────────────────────────────────────────────────────┘ │
│                                    │                                        │
│                                    ▼                                        │
│  ┌───────────────────────────────────────────────────────────────────────┐ │
│  │                         VIBESHIP MIND                                  │ │
│  │                    (Persistent Memory Core)                            │ │
│  └───────────────────────────────────────────────────────────────────────┘ │
│                                    │                                        │
│                                    ▼                                        │
│  ┌───────────────────────────────────────────────────────────────────────┐ │
│  │                        EXECUTION LAYER                                 │ │
│  │   Tools │ Spawner Skills │ Agents │ LLMs │ Everything                 │ │
│  └───────────────────────────────────────────────────────────────────────┘ │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Component Architecture

### 1. Hook Layer (lib/hooks/)

**Purpose**: Capture events with zero interference

```
┌─────────────────────────────────────────────────────────────────┐
│                      HOOK LAYER (< 50ms)                         │
│                                                                  │
│   Claude Code          Spark Hook           Queue File           │
│   ┌─────────┐         ┌─────────┐         ┌─────────┐          │
│   │  Tool   │────────▶│ Capture │────────▶│ Append  │          │
│   │  Call   │         │  Event  │         │  JSONL  │          │
│   └─────────┘         └────┬────┘         └─────────┘          │
│                            │                                    │
│                            ▼                                    │
│                      Exit 0 (Fast)                              │
│                      Claude Continues                           │
└─────────────────────────────────────────────────────────────────┘
```

**Files**:
- `hooks/observe.py` - Captures PreToolUse, PostToolUse, PostToolUseFailure, Stop
- `hooks/session_start.py` - Loads context from Mind at session start
- `hooks/session_end.py` - Triggers background processor

**Key Constraints**:
- Must complete in < 50ms
- Must never block Claude
- Must never fail (exit 0 always)
- No network calls in hot path

### 2. Queue Layer (lib/queue.py)

**Purpose**: Ultra-fast event buffering

```
┌─────────────────────────────────────────────────────────────────┐
│                        QUEUE LAYER                               │
│                                                                  │
│   events.jsonl (append-only)        processed.jsonl (archive)   │
│   ┌─────────────────────┐          ┌─────────────────────┐     │
│   │ {"event": "post_tool"│          │ {"event": ...}      │     │
│   │  "tool": "Bash"     │  ──────▶ │                     │     │
│   │  "success": true}   │  process │                     │     │
│   └─────────────────────┘          └─────────────────────┘     │
│                                                                  │
│   Write: O(1) append                Read: O(n) batch            │
│   Target: < 10ms                    Target: async               │
└─────────────────────────────────────────────────────────────────┘
```

**Data Structure** (SparkEvent):
```python
@dataclass
class SparkEvent:
    event_type: EventType      # pre_tool, post_tool, etc.
    timestamp: float           # Unix timestamp
    session_id: str            # Claude session ID
    data: Dict[str, Any]       # Hook context
    tool_name: Optional[str]   # Tool that was called
    tool_input: Optional[Dict] # Tool parameters
    error: Optional[str]       # Error message if failed
    duration_ms: Optional[float]
```

### 3. Learning Layer (lib/learner.py)

**Purpose**: Extract patterns from events

```
┌─────────────────────────────────────────────────────────────────┐
│                      LEARNING LAYER                              │
│                                                                  │
│   Events                Patterns              Learnings          │
│   ┌─────────┐          ┌─────────┐          ┌─────────┐        │
│   │ Batch   │────────▶ │ Extract │────────▶ │ Filter  │        │
│   │ Events  │          │ Patterns│          │ by conf │        │
│   └─────────┘          └─────────┘          └────┬────┘        │
│                                                   │              │
│   Pattern Types:                                  ▼              │
│   - tool_effectiveness      ┌──────────────────────────┐       │
│   - error_avoidance         │  Store in Mind           │       │
│   - tool_sequence           │  (temporal_level: 4)     │       │
│                             └──────────────────────────┘       │
└─────────────────────────────────────────────────────────────────┘
```

**Pattern Types**:

1. **Tool Effectiveness**
   - Success rate per tool
   - Average duration
   - Error distribution

2. **Error Avoidance**
   - Common error types per tool
   - Avoidance strategies
   - Pre-conditions to check

3. **Tool Sequences**
   - 2-3 tool sequences that work well
   - Success rate by sequence
   - Context where sequence applies

### 4. Mind Integration (lib/mind_client.py)

**Purpose**: Persistent storage of learnings

```
┌─────────────────────────────────────────────────────────────────┐
│                    MIND INTEGRATION                              │
│                                                                  │
│   Spark                     Mind API                            │
│   ┌─────────┐              ┌─────────┐                         │
│   │ Async   │──────────────│ POST    │                         │
│   │ Client  │   memories/  │ /v1/    │                         │
│   └─────────┘              └─────────┘                         │
│                                                                  │
│   Memory Types:                                                 │
│   ┌─────────────────────────────────────────────────────┐      │
│   │ temporal_level │ content_type │ what                 │      │
│   │───────────────────────────────────────────────────────│      │
│   │ 2 (situational)│ event       │ Tool calls, results   │      │
│   │ 3 (seasonal)   │ observation │ Extracted patterns    │      │
│   │ 4 (identity)   │ reflection  │ High-conf learnings   │      │
│   └─────────────────────────────────────────────────────┘      │
└─────────────────────────────────────────────────────────────────┘
```

### 5. Processor (processor.py)

**Purpose**: Background learning orchestration

```
┌─────────────────────────────────────────────────────────────────┐
│                      PROCESSOR                                   │
│                                                                  │
│   Modes:                                                        │
│   ┌─────────────────────────────────────────────────────┐      │
│   │ once     │ Process queue once and exit              │      │
│   │ daemon   │ Continuous processing at interval        │      │
│   │ reflect  │ Deep analysis of all learnings           │      │
│   │ status   │ Show current system state                │      │
│   └─────────────────────────────────────────────────────┘      │
│                                                                  │
│   Flow:                                                         │
│   1. Initialize (load existing learnings from Mind)            │
│   2. Pop batch from queue                                       │
│   3. Update tool statistics                                     │
│   4. Extract patterns when threshold met                        │
│   5. Store high-confidence patterns in Mind                     │
│   6. Repeat (daemon) or exit (once)                            │
└─────────────────────────────────────────────────────────────────┘
```

## Data Flow

### Event Capture Flow

```
User Action
    │
    ▼
Claude Code Tool Call
    │
    ▼
┌───────────────────┐
│ PreToolUse Hook   │──▶ Queue event (pre_tool)
└───────────────────┘
    │
    ▼
Tool Execution
    │
    ▼
┌───────────────────┐
│ PostToolUse Hook  │──▶ Queue event (post_tool or post_tool_failure)
└───────────────────┘
    │
    ▼
Response to User
```

### Learning Flow

```
Queue (events.jsonl)
    │
    ▼
┌───────────────────┐
│ Processor         │
│ (background)      │
└───────────────────┘
    │
    ├──▶ Update ToolStats
    │
    ├──▶ Extract Patterns (when threshold met)
    │
    └──▶ Store in Mind (if confidence > 0.7)
```

### Context Injection Flow (TODO)

```
Session Start
    │
    ▼
┌───────────────────┐
│ session_start.py  │
└───────────────────┘
    │
    ▼
Query Mind for relevant learnings
    │
    ▼
Inject as additionalContext
    │
    ▼
Claude sees learnings at start
```

## File Structure

```
vibeship-spark/
├── lib/
│   ├── __init__.py         # Package exports
│   ├── queue.py            # SparkQueue, SparkEvent, quick_capture()
│   ├── mind_client.py      # MindClient, Memory, async operations
│   └── learner.py          # SparkLearner, Pattern, ToolStats
│
├── hooks/
│   ├── observe.py          # Main observation hook (all tool events)
│   ├── session_start.py    # Context injection at session start
│   └── session_end.py      # Trigger processor at session end
│
├── mcp-server/             # MCP server (TODO)
│   ├── src/
│   │   └── index.ts        # MCP tool definitions
│   └── package.json
│
├── tests/                  # Unit tests (TODO)
│   ├── test_queue.py
│   ├── test_learner.py
│   ├── test_mind_client.py
│   └── test_integration.py
│
├── docs/
│   ├── PRD.md              # Product requirements
│   ├── ARCHITECTURE.md     # This file
│   ├── IMPLEMENTATION.md   # Implementation status
│   └── TESTING.md          # Test strategy
│
├── processor.py            # Background learning processor
├── setup.py                # Installation and management
├── spark-hooks.json        # Hook configuration template
├── CLAUDE.md               # Instructions for Claude Code
└── README.md               # User documentation
```

## Integration Points

### Claude Code Hooks

Configuration in `~/.claude/settings.json`:
```json
{
  "hooks": {
    "SessionStart": [...],
    "PreToolUse": [...],
    "PostToolUse": [...],
    "PostToolUseFailure": [...],
    "Stop": [...],
    "SessionEnd": [...]
  }
}
```

### Vibeship Mind

- **Endpoint**: http://localhost:8080
- **Store**: POST /v1/memories/
- **Retrieve**: POST /v1/memories/retrieve
- **Health**: GET /health

### Spawner (Future)

- Track skill usage via tool events
- Evolve skills based on effectiveness
- Orchestrate agents based on learned patterns

## Security Considerations

1. **Local-only storage**: All data stays on user's machine
2. **No external API calls**: Except to local Mind instance
3. **No sensitive data in logs**: Hooks don't log tool content
4. **Queue file permissions**: User-only access

## Performance Budget

| Component | Target | Actual |
|-----------|--------|--------|
| Hook execution | < 50ms | ~10ms |
| Queue write | < 10ms | ~5ms |
| Mind store | < 100ms | ~50ms |
| Batch processing | Background | N/A |
