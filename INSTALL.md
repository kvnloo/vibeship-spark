# Spark Installation Guide

One-click setup for self-evolving intelligence in Claude Code.

## Quick Install

```bash
# Clone Spark
git clone https://github.com/vibeforge1111/vibeship-spark.git
cd vibeship-spark

# Run installer
python spark_install.py
```

That's it! Restart Claude Code and Spark is active.

---

## What Gets Installed

### 1. Configuration File (`~/.spark/config.json`)

```json
{
  "version": "1.0",
  "mind": {
    "api_url": "http://localhost:8080",
    "lite_path": "/path/to/vibeship-mind/src/mind/lite_tier.py",
    "auto_start": true
  },
  "daemon": {
    "auto_start": true,
    "interval_seconds": 15
  }
}
```

### 2. Claude Code Hooks (`~/.claude/settings.json`)

Seven hooks for complete lifecycle coverage:
- `SessionStart` - Auto-start Mind & daemon, inject learnings
- `UserPromptSubmit` - Capture goals
- `PreToolUse` - Store predictions, warn about dangerous commands
- `PostToolUse` - Resolve predictions, track progress
- `PostToolUseFailure` - Capture errors, suggest recovery
- `Stop` - Track session events
- `SessionEnd` - Finalize goals, trigger learning

### 3. MCP Server

Spark tools available in Claude Code:
- `spark_status` - System health
- `spark_learnings` - Query learnings
- `spark_reflect` - Deep reflection
- `spark_process` - Process events
- `spark_stats` - Statistics

---

## Installation Options

### Interactive (Recommended)

```bash
python spark_install.py
```

Prompts for Mind location if not auto-detected.

### Automatic

```bash
python spark_install.py --auto
```

Auto-detects everything, no prompts.

### With Mind Path

```bash
python spark_install.py --mind /path/to/lite_tier.py
```

Specify Mind location explicitly.

### Uninstall

```bash
python spark_install.py --uninstall
```

Removes hooks from Claude settings. Preserves learnings.

---

## Requirements

### Required
- Python 3.10+
- Claude Code CLI

### Optional (Recommended)
- [Vibeship Mind](https://github.com/vibeforge1111/vibeship-mind) - For persistent memory

Without Mind, Spark still works but learnings are session-only.

---

## Configuration

Edit `~/.spark/config.json` to customize:

### Mind Settings

```json
{
  "mind": {
    "api_url": "http://localhost:8080",
    "lite_path": "/your/path/to/lite_tier.py",
    "auto_start": true,
    "start_timeout_seconds": 5
  }
}
```

| Setting | Description | Default |
|---------|-------------|---------|
| `api_url` | Mind API endpoint | `http://localhost:8080` |
| `lite_path` | Path to Mind Lite script | Auto-detected |
| `auto_start` | Start Mind automatically | `true` |
| `start_timeout_seconds` | Max wait for Mind to start | `5` |

### Daemon Settings

```json
{
  "daemon": {
    "auto_start": true,
    "interval_seconds": 15,
    "queue_threshold": 50
  }
}
```

| Setting | Description | Default |
|---------|-------------|---------|
| `auto_start` | Start daemon at session start | `true` |
| `interval_seconds` | Processing interval | `15` |
| `queue_threshold` | Auto-process if queue exceeds | `50` |

### Hook Settings

```json
{
  "hooks": {
    "timeout_seconds": 3,
    "inject_context": true,
    "inject_warnings": true,
    "inject_self_awareness": true
  }
}
```

---

## Verification

After installation, verify everything works:

```bash
# Quick check
python spark_cli.py startup

# Expected output:
# STATUS: READY (7/7 checks passed)
```

### What Gets Checked

1. Mind connection - API responding
2. Hooks - All 7 configured
3. Daemon - Running or auto-started
4. Queue - Not backed up
5. Recent activity - Learning happening
6. Coverage - All pattern types
7. Error capture - Failures being captured

---

## Troubleshooting

### Mind not starting

```bash
# Check Mind path in config
cat ~/.spark/config.json | grep lite_path

# Manually verify path exists
ls /path/from/config/lite_tier.py

# Update config if needed
python -c "
from lib.config import get_config
config = get_config()
config.set('mind.lite_path', '/correct/path/to/lite_tier.py')
config.save()
"
```

### Hooks not working

```bash
# Verify hooks installed
cat ~/.claude/settings.json | grep -A5 "hooks"

# Reinstall hooks
python spark_install.py --auto
```

### Learning not happening

```bash
# Check queue
python spark_cli.py witness --systems processing

# Process queue manually
python spark_cli.py learn

# Check Mind connection
curl http://localhost:8080/health
```

---

## Updating Spark

```bash
cd vibeship-spark
git pull

# Re-run installer to update hooks
python spark_install.py --auto
```

---

## Directory Structure

After installation:

```
~/.spark/
├── config.json          # Your configuration
├── daemon.pid           # Daemon process ID
├── mind.pid             # Mind process ID (if auto-started)
├── queue/
│   ├── events.jsonl     # Pending events
│   └── processed.jsonl  # Processed events
├── active_goals.json    # Current session goals
├── predictions.json     # Tool predictions
└── active_injections.json  # Tracked advice

~/.claude/
└── settings.json        # Claude Code settings (hooks here)
```

---

## What Happens Automatically

### At Session Start
1. Mind starts (if not running)
2. Daemon starts (if not running)
3. Stale PIDs cleaned up
4. Backed-up queue processed
5. Learnings injected into context
6. Self-awareness loaded

### During Session
- Every tool call captured
- Predictions made and resolved
- Goals tracked
- Errors captured with recovery suggestions

### At Session End
- Active goals finalized
- Learning triggered
- Patterns extracted

---

## Support

- Issues: https://github.com/vibeforge1111/vibeship-spark/issues
- Documentation: See `docs/` directory
