# Spark Session Startup Checklist

Run this at the start of every new Claude Code session to ensure Spark is healthy and learning continuity is maintained.

## Quick Start (Copy & Paste)

```
python spark_startup.py
```

This runs all 7 validation checks automatically.

---

## Manual Verification Prompts

If you prefer to check things step by step, use these prompts:

### 1. System Health
```
python spark_cli.py health
```
**Expected:** `21/21 components healthy`

### 2. Mind Connection
```
curl -s http://localhost:8080/health
```
**Expected:** `{"status":"healthy"}`

### 3. Recent Learnings
```
python spark_cli.py witness --systems learnings
```
**Expected:** Shows recent learning activity

### 4. Queue Status
```
python spark_cli.py witness --systems processing
```
**Expected:** Queue size manageable (< 100)

### 5. Error Capture Working
```
python spark_cli.py witness --systems error_patterns
```
**Expected:** Shows captured error patterns

---

## Diagnostic Commands

### Full Diagnostic
```
python spark_doctor.py
```
Runs comprehensive diagnostics with auto-fix suggestions.

### Learning Report
```
python spark_cli.py report
```
Generates detailed learning intelligence report.

### Live Monitoring
```
python spark_cli.py live
```
Real-time view of all Spark systems.

---

## Common Issues & Fixes

| Issue | Fix |
|-------|-----|
| Mind not responding | Run `start_mind_lite.bat` |
| Queue backed up | Run `python processor.py --mode once` |
| No recent learnings | Check hooks in `~/.claude/settings.json` |
| Daemon stale PID | Delete `~/.spark/daemon.pid` |

---

## Session Start Workflow

1. **Run startup check:**
   ```
   python spark_startup.py
   ```

2. **If all green:** Start working - Spark is ready!

3. **If warnings:** Review and decide if action needed

4. **If critical issues:** Fix before proceeding:
   - Mind down? Start Mind first
   - Hooks missing? Check settings.json

---

## What Spark Validates

| Check | What It Verifies |
|-------|------------------|
| Mind Connection | Mind API is running and responsive |
| Hooks | All 7 required hooks are configured |
| Daemon | Background processor is running |
| Queue | Event queue isn't backed up |
| Recent Activity | Learning has happened recently |
| Coverage | All learning types have data |
| Error Capture | Failures are being captured |

---

## Pro Tips

- **First session of the day?** Run `python spark_startup.py --fix` to auto-heal issues
- **After Mind restart?** Queue may have backed up - run processor
- **Strange behavior?** Use `python spark_cli.py live` to watch in real-time
- **Need full picture?** Use `python spark_cli.py report` for detailed analysis
