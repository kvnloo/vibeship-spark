# Spark PRD - Product Requirements Document

## Executive Summary

**Spark** is an ambient self-evolving intelligence layer that wraps around Claude Code, continuously observing actions, measuring results, extracting patterns, and improving decision-making over time. Unlike traditional tools that require invocation, Spark IS the intelligence—always running, always learning, always improving.

## Vision

> "I don't wait to be invoked. I AM the intelligence layer."

Spark transforms Claude Code from a stateless assistant into a continuously improving system that:
- Remembers what works and what doesn't
- Learns optimal tool selection and usage patterns
- Evolves skills and prompts based on outcomes
- Orchestrates agents more effectively over time

## Problem Statement

### Current State
- Claude Code has no persistent memory of what worked
- Every session starts fresh with no learning
- Tool selection is based on static rules, not experience
- Skills and prompts don't evolve based on outcomes
- No measurement of effectiveness or improvement

### Desired State
- Every action is observed and measured
- Patterns are extracted and stored permanently
- Learnings inform future decisions
- Skills evolve based on effectiveness data
- Continuous improvement without manual intervention

## Target Users

1. **Vibe Coders** - Developers who use Claude Code daily
2. **Power Users** - Those who want Claude to improve over time
3. **Teams** - Groups who want shared learning across sessions

## Core Requirements

### 1. Ambient Observation (P0)

**The system must observe everything without interference.**

| Requirement | Metric | Status |
|-------------|--------|--------|
| Hook into all tool calls | 100% coverage | ✅ Done |
| Capture tool inputs and outputs | Full data | ✅ Done |
| Complete in < 50ms | p99 latency | ✅ Done |
| Never block Claude | 0 blocking events | ✅ Done |
| Queue events reliably | 0 data loss | ✅ Done |

### 2. Pattern Extraction (P0)

**The system must learn from accumulated data.**

| Requirement | Metric | Status |
|-------------|--------|--------|
| Tool effectiveness tracking | Success rate per tool | ✅ Done |
| Error pattern detection | Common errors identified | ✅ Done |
| Sequence analysis | Successful tool sequences | ✅ Done |
| Confidence scoring | Statistical significance | ✅ Done |
| Batch processing | Background, non-blocking | ✅ Done |

### 3. Mind Integration (P0)

**All learnings must persist in Vibeship Mind.**

| Requirement | Metric | Status |
|-------------|--------|--------|
| Async storage | Non-blocking | ✅ Done |
| Appropriate temporal levels | Correct classification | ✅ Done |
| Queryable learnings | Retrievable on demand | ✅ Done |
| Graceful degradation | Works without Mind | ✅ Done |

### 4. Context Injection (P1)

**Learnings should inform Claude's decisions.**

| Requirement | Metric | Status |
|-------------|--------|--------|
| Load learnings at session start | Relevant context | 🔄 Partial |
| Inject recommendations before tool calls | Pre-action guidance | ❌ TODO |
| Surface relevant patterns | Context-aware | ❌ TODO |

### 5. Skill Evolution (P1)

**Skills should improve based on usage data.**

| Requirement | Metric | Status |
|-------------|--------|--------|
| Track skill effectiveness | Success rate per skill | ❌ TODO |
| Identify skill gaps | Missing capabilities | ❌ TODO |
| Propose skill improvements | Actionable suggestions | ❌ TODO |
| Auto-evolve skill content | Iterative improvement | ❌ TODO |

### 6. Agent Orchestration Learning (P1)

**Learn optimal agent routing.**

| Requirement | Metric | Status |
|-------------|--------|--------|
| Track agent effectiveness by task type | Per-task metrics | ❌ TODO |
| Learn when to parallelize | Efficiency patterns | ❌ TODO |
| Optimize handoff patterns | Success rate | ❌ TODO |

### 7. Prompt Evolution (P2)

**Prompts should evolve toward better outcomes.**

| Requirement | Metric | Status |
|-------------|--------|--------|
| Track prompt effectiveness | Quality scores | ❌ TODO |
| A/B test variations | Statistical comparison | ❌ TODO |
| Evolve toward higher success | Iterative improvement | ❌ TODO |

### 8. Meta-Learning (P2)

**Learn about the learning process itself.**

| Requirement | Metric | Status |
|-------------|--------|--------|
| Track learning effectiveness | Are learnings improving outcomes? | ❌ TODO |
| Identify meta-patterns | Patterns in patterns | ❌ TODO |
| Self-assess improvement | Quantified progress | ❌ TODO |

### 9. MCP Server (P1)

**Direct invocation for explicit Spark operations.**

| Requirement | Metric | Status |
|-------------|--------|--------|
| spark_status tool | System health | ❌ TODO |
| spark_learnings tool | Query learnings | ❌ TODO |
| spark_reflect tool | Trigger reflection | ❌ TODO |
| spark_evolve tool | Force evolution cycle | ❌ TODO |

## Non-Functional Requirements

### Performance
- Hook execution: < 50ms p99
- Queue write: < 10ms
- No blocking of Claude Code

### Reliability
- Graceful degradation without Mind
- No data loss in queue
- Crash recovery

### Scalability
- Handle 1000+ events per session
- Efficient batch processing
- Bounded queue size

## Success Metrics

1. **Learning Rate**: Learnings extracted per session
2. **Accuracy**: Prediction accuracy of tool success
3. **Improvement**: Measurable improvement in outcomes over time
4. **Coverage**: % of actions observed and measured

## Milestones

### M1: Foundation (✅ Complete)
- Hook system
- Event queue
- Mind integration
- Basic pattern extraction

### M2: Intelligence (Current)
- Context injection
- MCP server
- Unit tests
- Skill tracking

### M3: Evolution
- Skill evolution
- Prompt evolution
- Agent orchestration learning

### M4: Meta
- Meta-learning
- Self-assessment
- Autonomous improvement

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Hook performance degradation | User experience | Strict < 50ms budget |
| Learning wrong patterns | Bad recommendations | Confidence thresholds |
| Mind unavailability | Lost learnings | Local queue fallback |
| Privacy concerns | Data exposure | Local-only storage |

## Dependencies

- **Vibeship Mind**: Persistent memory storage
- **Claude Code Hooks**: Event capture mechanism
- **Spawner Skills**: Skill definitions to evolve

## Open Questions

1. How to handle conflicting learnings?
2. What's the decay rate for outdated patterns?
3. How to share learnings across users?
4. How to A/B test without disrupting user experience?
