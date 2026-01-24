#!/usr/bin/env python3
"""
Spark Session Start Hook: Inject intelligence into Claude.

This hook runs when a Claude Code session starts.
It pulls learnings from Mind via ContextInjector and feeds
them back to Claude - closing the learning loop.

Also:
- Starts the processor daemon if not running (for continuous learning)
- Uses Suggester for proactive warnings

Target: < 200ms to avoid slowing session start.
"""

import sys
import json
import asyncio
import os
import subprocess
from pathlib import Path
from typing import Optional

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from lib.context_injector import ContextInjector
from lib.suggester import Suggester
from lib.injection_tracker import InjectionTracker

# Daemon management
SPARK_DIR = Path.home() / ".spark"
PID_FILE = SPARK_DIR / "daemon.pid"
INJECTIONS_FILE = SPARK_DIR / "active_injections.json"

# Self-awareness files (defined after SPARK_DIR)
IMPROVEMENT_LOG = SPARK_DIR / "improvement_log.json"
GOALS_FILE = SPARK_DIR / "active_goals.json"


def load_self_awareness() -> Optional[str]:
    """
    Load self-awareness data for injection.

    This tells Claude what Spark is struggling with so it can
    help address those gaps during the session.

    Must be FAST (<50ms) - just file reads, no Mind calls.
    """
    awareness_parts = []

    try:
        # 1. Recent improvement actions
        if IMPROVEMENT_LOG.exists():
            try:
                log = json.loads(IMPROVEMENT_LOG.read_text())
                if log:
                    # Get most recent improvement report
                    recent = log[-1]
                    gaps = recent.get("gaps_found", 0)
                    improvements = recent.get("improvements_made", 0)

                    if gaps > 0:
                        # Get high-severity gaps from actions
                        actions = recent.get("actions_taken", [])
                        high_gaps = [a for a in actions if a.get("gap_type") in ("blind_spot", "missing_pattern")]

                        if high_gaps:
                            gap_summaries = [a.get("description", "")[:60] for a in high_gaps[:2]]
                            awareness_parts.append(
                                f"[SPARK SELF-AWARENESS] Recent gaps identified ({gaps} total, {improvements} addressed):\n" +
                                "\n".join(f"  - {g}" for g in gap_summaries if g)
                            )
            except (json.JSONDecodeError, KeyError):
                pass

        # 2. Goal success patterns
        if GOALS_FILE.exists():
            try:
                goals = json.loads(GOALS_FILE.read_text())
                if goals:
                    from collections import defaultdict
                    by_type = defaultdict(lambda: {"completed": 0, "abandoned": 0, "total": 0})

                    for g in goals.values():
                        gtype = g.get("goal_type", "unknown")
                        status = g.get("status", "")
                        by_type[gtype]["total"] += 1
                        if status == "completed":
                            by_type[gtype]["completed"] += 1
                        elif status == "abandoned":
                            by_type[gtype]["abandoned"] += 1

                    # Find struggling goal types (more abandoned than completed)
                    struggling = []
                    for gtype, stats in by_type.items():
                        if stats["total"] >= 3 and stats["abandoned"] > stats["completed"]:
                            rate = stats["completed"] / stats["total"] if stats["total"] > 0 else 0
                            struggling.append(f"{gtype} ({rate:.0%} success)")

                    if struggling:
                        awareness_parts.append(
                            f"[SPARK SELF-AWARENESS] Goal types that need attention: {', '.join(struggling[:3])}"
                        )
            except (json.JSONDecodeError, KeyError):
                pass

    except Exception:
        pass  # Never fail the hook

    return "\n".join(awareness_parts) if awareness_parts else None


def is_daemon_running() -> bool:
    """Check if processor daemon is already running. Clean up stale PID if not."""
    if not PID_FILE.exists():
        return False

    try:
        pid = int(PID_FILE.read_text().strip())
        # Check if process exists
        if sys.platform == "win32":
            # Windows: use tasklist
            result = subprocess.run(
                ["tasklist", "/FI", f"PID eq {pid}"],
                capture_output=True, text=True
            )
            is_running = str(pid) in result.stdout
        else:
            # Unix: send signal 0
            try:
                os.kill(pid, 0)
                is_running = True
            except OSError:
                is_running = False

        # AUTO-HEAL: Clean up stale PID file if process not running
        if not is_running:
            try:
                PID_FILE.unlink()
            except:
                pass
            return False
        return True
    except (ValueError, OSError, subprocess.SubprocessError):
        # AUTO-HEAL: Remove corrupted PID file
        try:
            PID_FILE.unlink()
        except:
            pass
        return False


def start_daemon():
    """Start the processor daemon in background."""
    processor_path = Path(__file__).parent.parent / "processor.py"
    if not processor_path.exists():
        return

    try:
        SPARK_DIR.mkdir(parents=True, exist_ok=True)

        # Start detached process
        if sys.platform == "win32":
            # Windows: use CREATE_NEW_PROCESS_GROUP
            process = subprocess.Popen(
                [sys.executable, str(processor_path), "--mode", "daemon", "--interval", "15"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS
            )
        else:
            # Unix: use start_new_session
            process = subprocess.Popen(
                [sys.executable, str(processor_path), "--mode", "daemon", "--interval", "15"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True
            )

        # Write PID file
        PID_FILE.write_text(str(process.pid))
    except Exception:
        pass  # Never fail the hook


def ensure_daemon_running():
    """Ensure processor daemon is running."""
    if not is_daemon_running():
        start_daemon()


def auto_heal_queue():
    """
    AUTO-HEAL: Process queue if it's backing up.

    If queue has > 50 events, run processor once in background.
    This prevents queue from growing indefinitely if daemon isn't keeping up.
    """
    queue_file = SPARK_DIR / "queue" / "events.jsonl"

    if not queue_file.exists():
        return

    try:
        content = queue_file.read_text()
        lines = [l for l in content.strip().split("\n") if l.strip()]

        if len(lines) > 50:
            # Queue is backing up - trigger processing
            processor_path = Path(__file__).parent.parent / "processor.py"
            if processor_path.exists():
                subprocess.Popen(
                    [sys.executable, str(processor_path), "--mode", "once"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    start_new_session=True if sys.platform != "win32" else False,
                    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == "win32" else 0
                )
    except Exception:
        pass  # Never fail the hook


def quick_health_check() -> dict:
    """
    Quick health check for session start.

    Returns status dict with any issues found.
    Must complete in < 100ms (no Mind calls).
    """
    issues = []

    # Check queue size
    queue_file = SPARK_DIR / "queue" / "events.jsonl"
    queue_size = 0
    if queue_file.exists():
        try:
            content = queue_file.read_text()
            queue_size = len([l for l in content.strip().split("\n") if l.strip()])
            if queue_size > 100:
                issues.append(f"queue_backed_up:{queue_size}")
        except:
            pass

    # Check daemon
    daemon_ok = is_daemon_running()
    if not daemon_ok:
        issues.append("daemon_starting")

    # Check for recent learnings (just file existence)
    learning_files = list((SPARK_DIR / "queue").glob("processed*.jsonl"))
    if not learning_files:
        issues.append("no_processed_events")

    return {
        "healthy": len(issues) == 0,
        "issues": issues,
        "queue_size": queue_size,
        "daemon_running": daemon_ok
    }


def extract_project_name(cwd: str) -> Optional[str]:
    """Extract project name from working directory."""
    if not cwd:
        return None
    parts = Path(cwd).parts
    # Skip common root paths
    skip = {"Users", "Desktop", "Documents", "Projects", "repos", "code", "home", "USER"}
    for part in reversed(parts):
        if part.lower() not in {s.lower() for s in skip} and part:
            return part
    return None


def save_active_injections(tracker: InjectionTracker, session_id: str):
    """Save active injections to file for observe hook to track."""
    try:
        INJECTIONS_FILE.parent.mkdir(parents=True, exist_ok=True)

        # Load existing injections (from other sessions)
        existing = {}
        if INJECTIONS_FILE.exists():
            try:
                existing = json.loads(INJECTIONS_FILE.read_text())
            except:
                existing = {}

        # Add/update injections from this session
        for tracking_id, injection in tracker.active_injections.items():
            existing[tracking_id] = {
                "tracking_id": tracking_id,
                "session_id": injection.session_id,
                "injection_type": injection.injection_type,
                "content_summary": injection.content_summary,
                "trigger_conditions": injection.trigger_conditions,
                "injected_at": injection.injected_at,
                "outcome": "pending",
                "outcome_events": []
            }

        # Clean up old sessions (> 2 hours)
        import time
        cutoff = time.time() - 7200
        existing = {k: v for k, v in existing.items()
                   if v.get("injected_at", 0) > cutoff}

        INJECTIONS_FILE.write_text(json.dumps(existing))
    except Exception:
        pass  # Never fail the hook


async def load_and_inject(project_name: Optional[str], session_id: Optional[str] = None) -> Optional[str]:
    """Load context from Mind and format for injection."""
    tracker = InjectionTracker()
    injector = ContextInjector(injection_tracker=tracker)
    suggester = Suggester()

    try:
        # Load context with tracking
        if session_id:
            context, tracking_ids = await injector.inject_and_track(session_id, project_name)
        else:
            context = await injector.get_injection_string(project_name)
            tracking_ids = []

        # Load suggestions
        await suggester.load_suggestions_from_mind()

        # Update suggester context
        if session_id:
            suggester.update_context(session_id=session_id, project_name=project_name)

        # Get proactive warnings
        warnings = suggester.get_relevant_suggestions(max_suggestions=2, min_confidence=0.7)

        # Combine context, warnings, and self-awareness
        parts = []
        if context:
            parts.append(context)

        if warnings:
            warning_text = suggester.format_suggestions_for_display(warnings, compact=True)
            if warning_text:
                parts.append(warning_text)

        # Add self-awareness (what Spark is struggling with)
        self_awareness = load_self_awareness()
        if self_awareness:
            parts.append(self_awareness)

        # FEEDBACK LOOP: Save active injections for observe hook to track
        if session_id and tracker.active_injections:
            save_active_injections(tracker, session_id)

        return "\n".join(parts) if parts else None

    finally:
        await injector.close()


def main():
    """Main hook entry point."""
    # AUTO-HEAL #1: Clean up stale PID and ensure daemon is running
    ensure_daemon_running()

    # AUTO-HEAL #2: Process queue if it's backing up
    auto_heal_queue()

    # Quick health check (no Mind calls, fast)
    health = quick_health_check()

    try:
        # Read hook input
        input_data = json.load(sys.stdin)
    except Exception:
        sys.exit(0)

    # Extract context
    cwd = input_data.get("cwd", os.getcwd())
    project_name = extract_project_name(cwd)
    session_id = input_data.get("session_id")

    # Load context with timeout
    try:
        context = asyncio.run(asyncio.wait_for(
            load_and_inject(project_name, session_id),
            timeout=2.0
        ))
    except asyncio.TimeoutError:
        context = None
    except Exception:
        context = None

    # Build output
    output = {"continue": True}

    # Include context if available
    hook_output = {}
    if context:
        hook_output["additionalContext"] = context

    # Include health status (for visibility)
    if not health["healthy"]:
        # Add health warning to context
        health_warning = f"[SPARK AUTO-HEALING] Issues detected: {', '.join(health['issues'])}"
        if hook_output.get("additionalContext"):
            hook_output["additionalContext"] = health_warning + "\n\n" + hook_output["additionalContext"]
        else:
            hook_output["additionalContext"] = health_warning

    if hook_output:
        output["hookSpecificOutput"] = hook_output
        print(json.dumps(output))

    sys.exit(0)


if __name__ == "__main__":
    main()
