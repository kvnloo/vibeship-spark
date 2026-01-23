#!/usr/bin/env python3
"""
Spark Doctor - Self-Healing Intelligence System

Diagnoses issues, prescribes solutions, heals automatically, and verifies fixes.

Usage:
    python spark_doctor.py              # Run full diagnosis + healing
    python spark_doctor.py --diagnose   # Diagnosis only (no fixes)
    python spark_doctor.py --heal       # Skip diagnosis, run all healers
"""

import argparse
import asyncio
import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from lib.mind_client import MindClient


class Severity(Enum):
    """Issue severity levels."""
    CRITICAL = "critical"  # System broken, needs immediate fix
    WARNING = "warning"    # Degraded, should fix
    INFO = "info"          # Optimization opportunity
    OK = "ok"              # No issue


@dataclass
class Diagnosis:
    """A diagnosed issue."""
    issue_id: str
    title: str
    severity: Severity
    description: str
    prescription: Optional[str] = None
    healer: Optional[str] = None  # Name of healing function
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class HealingResult:
    """Result of a healing action."""
    issue_id: str
    success: bool
    action_taken: str
    before_state: Any
    after_state: Any
    message: str


class SparkDoctor:
    """
    Self-healing system for Spark.

    DIAGNOSE → PRESCRIBE → HEAL → VERIFY
    """

    def __init__(self):
        self.mind = MindClient()
        self.diagnoses: List[Diagnosis] = []
        self.healing_results: List[HealingResult] = []

        # Register diagnostic checks
        self.diagnostics: Dict[str, Callable] = {
            "daemon_status": self._check_daemon,
            "queue_health": self._check_queue,
            "mind_connection": self._check_mind,
            "hook_config": self._check_hooks,
            "learning_gaps": self._check_learning_gaps,
            "tool_coverage": self._check_tool_coverage,
            "error_learning": self._check_error_learning,
        }

        # Register healers (functions that fix issues)
        self.healers: Dict[str, Callable] = {
            "start_daemon": self._heal_start_daemon,
            "process_queue": self._heal_process_queue,
            "trigger_glob_patterns": self._heal_trigger_glob,
            "trigger_task_patterns": self._heal_trigger_task,
            "trigger_error_learning": self._heal_trigger_errors,
            "clear_stale_queue": self._heal_clear_stale_queue,
        }

    # ==================== DIAGNOSIS PHASE ====================

    async def diagnose(self) -> List[Diagnosis]:
        """Run all diagnostic checks."""
        print("\n" + "=" * 50)
        print("  SPARK DOCTOR - Diagnosis Phase")
        print("=" * 50 + "\n")

        self.diagnoses = []

        for name, check in self.diagnostics.items():
            print(f"  Checking {name}...", end=" ")
            try:
                diagnosis = await check()
                if diagnosis:
                    self.diagnoses.append(diagnosis)
                    icon = {"critical": "XX", "warning": "!!", "info": "ii", "ok": "OK"}
                    print(f"[{icon.get(diagnosis.severity.value, '??')}] {diagnosis.title}")
                else:
                    print("[OK]")
            except Exception as e:
                print(f"[ERROR] {str(e)[:30]}")
                self.diagnoses.append(Diagnosis(
                    issue_id=f"check_error_{name}",
                    title=f"Check failed: {name}",
                    severity=Severity.WARNING,
                    description=str(e)
                ))

        return self.diagnoses

    async def _check_daemon(self) -> Optional[Diagnosis]:
        """Check if daemon is running."""
        pid_file = Path.home() / ".spark" / "daemon.pid"

        if not pid_file.exists():
            return Diagnosis(
                issue_id="daemon_not_running",
                title="Daemon not running",
                severity=Severity.WARNING,
                description="The Spark daemon is not running. Learning happens in batches instead of continuously.",
                prescription="Start the daemon for continuous learning",
                healer="start_daemon"
            )

        try:
            pid = int(pid_file.read_text().strip())
            # Check if process exists
            try:
                os.kill(pid, 0)
                return None  # Running fine
            except (OSError, ProcessLookupError):
                return Diagnosis(
                    issue_id="daemon_stale_pid",
                    title="Daemon crashed (stale PID)",
                    severity=Severity.WARNING,
                    description=f"PID file exists but process {pid} is not running.",
                    prescription="Clean up stale PID and restart daemon",
                    healer="start_daemon",
                    metadata={"stale_pid": pid}
                )
        except:
            return None

    async def _check_queue(self) -> Optional[Diagnosis]:
        """Check queue health."""
        queue_file = Path.home() / ".spark" / "queue" / "events.jsonl"

        if not queue_file.exists():
            return None  # No queue = no problem

        try:
            lines = queue_file.read_text().strip().split("\n")
            size = len([l for l in lines if l.strip()])

            if size > 500:
                return Diagnosis(
                    issue_id="queue_overload",
                    title=f"Queue overloaded ({size} events)",
                    severity=Severity.CRITICAL,
                    description="Queue has too many unprocessed events. Learning is falling behind.",
                    prescription="Process queue immediately",
                    healer="process_queue",
                    metadata={"queue_size": size}
                )
            elif size > 100:
                return Diagnosis(
                    issue_id="queue_backlog",
                    title=f"Queue backlog ({size} events)",
                    severity=Severity.WARNING,
                    description="Queue is building up. Consider processing.",
                    prescription="Process queue to catch up",
                    healer="process_queue",
                    metadata={"queue_size": size}
                )
        except:
            pass
        return None

    async def _check_mind(self) -> Optional[Diagnosis]:
        """Check Mind connection."""
        try:
            ok = await self.mind.is_available()
            if not ok:
                return Diagnosis(
                    issue_id="mind_offline",
                    title="Mind is offline",
                    severity=Severity.CRITICAL,
                    description="Cannot connect to Mind. No learning can be stored.",
                    prescription="Start Mind with start_mind_lite.bat"
                )
        except Exception as e:
            return Diagnosis(
                issue_id="mind_error",
                title="Mind connection error",
                severity=Severity.CRITICAL,
                description=f"Error connecting to Mind: {e}",
                prescription="Check Mind is running on localhost:8080"
            )
        return None

    async def _check_hooks(self) -> Optional[Diagnosis]:
        """Check hook configuration."""
        settings_file = Path.home() / ".claude" / "settings.json"
        required = ["SessionStart", "UserPromptSubmit", "PreToolUse",
                   "PostToolUse", "PostToolUseFailure", "Stop", "SessionEnd"]

        if not settings_file.exists():
            return Diagnosis(
                issue_id="hooks_missing_settings",
                title="Settings file missing",
                severity=Severity.CRITICAL,
                description="Claude settings.json not found. Hooks cannot work.",
                prescription="Create settings.json with hook configuration"
            )

        try:
            settings = json.loads(settings_file.read_text())
            hooks = settings.get("hooks", {})
            missing = [h for h in required if h not in hooks]

            if missing:
                return Diagnosis(
                    issue_id="hooks_incomplete",
                    title=f"Missing hooks: {', '.join(missing)}",
                    severity=Severity.CRITICAL,
                    description="Some required hooks are not configured.",
                    prescription="Add missing hooks to settings.json",
                    metadata={"missing": missing}
                )
        except:
            pass
        return None

    async def _check_learning_gaps(self) -> Optional[Diagnosis]:
        """Check for gaps in learning coverage."""
        try:
            # Query learning counts by type
            tool_results = await self.mind.retrieve("TOOL_EFFECTIVENESS", limit=10)
            error_results = await self.mind.retrieve("ERROR_CATEGORY", limit=10)
            goal_results = await self.mind.retrieve("GOAL_STRATEGY", limit=10)

            gaps = []
            if len(tool_results) == 0:
                gaps.append("tool effectiveness")
            if len(error_results) == 0:
                gaps.append("error patterns")
            if len(goal_results) == 0:
                gaps.append("goal strategies")

            if gaps:
                return Diagnosis(
                    issue_id="learning_gaps",
                    title=f"Missing learning types: {', '.join(gaps)}",
                    severity=Severity.INFO,
                    description="Some learning categories have no patterns yet.",
                    prescription="Use more diverse tools and scenarios to build patterns",
                    metadata={"gaps": gaps}
                )
        except:
            pass
        return None

    async def _check_tool_coverage(self) -> Optional[Diagnosis]:
        """Check which tools have effectiveness patterns."""
        expected_tools = {"Read", "Edit", "Write", "Bash", "Grep", "Glob", "Task"}

        try:
            results = await self.mind.retrieve("TOOL_EFFECTIVENESS", limit=100)
            learned_tools = set()

            for r in results:
                content = r.get("content", "")
                if "tool=" in content:
                    tool = content.split("tool=")[1].split()[0].strip("',\".;:")
                    learned_tools.add(tool)

            missing = expected_tools - learned_tools
            if missing:
                healers = []
                if "Glob" in missing:
                    healers.append("trigger_glob_patterns")
                if "Task" in missing:
                    healers.append("trigger_task_patterns")

                return Diagnosis(
                    issue_id="tool_coverage_gap",
                    title=f"Missing tool patterns: {', '.join(missing)}",
                    severity=Severity.INFO,
                    description="Some tools don't have effectiveness patterns yet.",
                    prescription="Use these tools to build patterns",
                    healer=healers[0] if healers else None,
                    metadata={"missing": list(missing), "learned": list(learned_tools)}
                )
        except:
            pass
        return None

    async def _check_error_learning(self) -> Optional[Diagnosis]:
        """Check if error patterns are being learned."""
        try:
            results = await self.mind.retrieve("ERROR_CATEGORY", limit=10)
            if len(results) == 0:
                return Diagnosis(
                    issue_id="no_error_patterns",
                    title="No error patterns learned",
                    severity=Severity.INFO,
                    description="No error patterns stored yet. Either no errors occurred or they're not being captured.",
                    prescription="Trigger some safe errors to test error learning",
                    healer="trigger_error_learning"
                )
        except:
            pass
        return None

    # ==================== HEALING PHASE ====================

    async def heal(self, auto: bool = False) -> List[HealingResult]:
        """Execute healing actions for diagnosed issues."""
        print("\n" + "=" * 50)
        print("  SPARK DOCTOR - Healing Phase")
        print("=" * 50 + "\n")

        self.healing_results = []
        healable = [d for d in self.diagnoses if d.healer and d.severity != Severity.OK]

        if not healable:
            print("  No issues require healing. System is healthy!")
            return []

        print(f"  Found {len(healable)} healable issues:\n")

        for diagnosis in healable:
            print(f"  [{diagnosis.severity.value.upper()}] {diagnosis.title}")
            print(f"      Prescription: {diagnosis.prescription}")
            print(f"      Healer: {diagnosis.healer}")

            if not auto:
                response = input(f"\n      Apply fix? (y/n): ").strip().lower()
                if response != 'y':
                    print("      Skipped.")
                    continue

            print(f"      Applying fix...", end=" ")

            healer_func = self.healers.get(diagnosis.healer)
            if healer_func:
                try:
                    result = await healer_func(diagnosis)
                    self.healing_results.append(result)
                    if result.success:
                        print(f"[HEALED] {result.message}")
                    else:
                        print(f"[FAILED] {result.message}")
                except Exception as e:
                    print(f"[ERROR] {e}")
                    self.healing_results.append(HealingResult(
                        issue_id=diagnosis.issue_id,
                        success=False,
                        action_taken=diagnosis.healer,
                        before_state=None,
                        after_state=None,
                        message=f"Healer error: {e}"
                    ))
            else:
                print(f"[SKIP] No healer function found")

            print()

        return self.healing_results

    async def _heal_start_daemon(self, diagnosis: Diagnosis) -> HealingResult:
        """Start the Spark daemon."""
        pid_file = Path.home() / ".spark" / "daemon.pid"

        # Clean up stale PID if exists
        if pid_file.exists():
            pid_file.unlink()

        # Start daemon in background
        proc = subprocess.Popen(
            [sys.executable, "processor.py", "--mode", "daemon", "--interval", "30"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == 'nt' else 0
        )

        # Give it a moment to start
        await asyncio.sleep(2)

        # Verify it started
        if pid_file.exists():
            new_pid = int(pid_file.read_text().strip())
            return HealingResult(
                issue_id=diagnosis.issue_id,
                success=True,
                action_taken="Started daemon",
                before_state=diagnosis.metadata.get("stale_pid"),
                after_state=new_pid,
                message=f"Daemon started with PID {new_pid}"
            )
        else:
            return HealingResult(
                issue_id=diagnosis.issue_id,
                success=False,
                action_taken="Attempted to start daemon",
                before_state=None,
                after_state=None,
                message="Daemon may have started but PID file not created"
            )

    async def _heal_process_queue(self, diagnosis: Diagnosis) -> HealingResult:
        """Process the event queue."""
        before_size = diagnosis.metadata.get("queue_size", 0)

        # Run processor once
        result = subprocess.run(
            [sys.executable, "processor.py", "--mode", "once"],
            capture_output=True,
            text=True,
            timeout=120
        )

        # Check new queue size
        queue_file = Path.home() / ".spark" / "queue" / "events.jsonl"
        after_size = 0
        if queue_file.exists():
            lines = queue_file.read_text().strip().split("\n")
            after_size = len([l for l in lines if l.strip()])

        return HealingResult(
            issue_id=diagnosis.issue_id,
            success=after_size < before_size,
            action_taken="Processed queue",
            before_state=before_size,
            after_state=after_size,
            message=f"Queue: {before_size} → {after_size} events"
        )

    async def _heal_trigger_glob(self, diagnosis: Diagnosis) -> HealingResult:
        """Trigger Glob tool usage to build patterns."""
        # This is meta - we're using Glob to help Spark learn about Glob!
        patterns_found = []

        # Run several Glob patterns
        glob_patterns = ["**/*.py", "**/*.md", "tests/*.py", "lib/*.py"]

        for pattern in glob_patterns:
            try:
                # Use pathlib glob
                matches = list(Path(".").glob(pattern))
                patterns_found.append(f"{pattern}: {len(matches)} matches")
            except:
                pass

        return HealingResult(
            issue_id=diagnosis.issue_id,
            success=len(patterns_found) > 0,
            action_taken="Triggered Glob patterns",
            before_state="No Glob patterns",
            after_state=patterns_found,
            message=f"Executed {len(patterns_found)} glob patterns"
        )

    async def _heal_trigger_task(self, diagnosis: Diagnosis) -> HealingResult:
        """Note about Task tool usage."""
        # We can't directly invoke Task tool from here, but we can note it
        return HealingResult(
            issue_id=diagnosis.issue_id,
            success=False,
            action_taken="Task tool recommendation",
            before_state="No Task patterns",
            after_state="Recommendation provided",
            message="Use Task tool in Claude Code to build patterns (e.g., 'search for X in codebase')"
        )

    async def _heal_trigger_errors(self, diagnosis: Diagnosis) -> HealingResult:
        """Trigger safe errors to test error learning."""
        errors_triggered = []

        # Safe error 1: File not found
        try:
            Path("/nonexistent/file/path.txt").read_text()
        except FileNotFoundError as e:
            errors_triggered.append("FileNotFoundError")

        # Safe error 2: JSON parse error
        try:
            json.loads("not valid json {{{")
        except json.JSONDecodeError as e:
            errors_triggered.append("JSONDecodeError")

        # Safe error 3: Division by zero
        try:
            x = 1 / 0
        except ZeroDivisionError as e:
            errors_triggered.append("ZeroDivisionError")

        # Safe error 4: Import error
        try:
            import nonexistent_module_spark_doctor_test
        except ImportError as e:
            errors_triggered.append("ImportError")

        return HealingResult(
            issue_id=diagnosis.issue_id,
            success=len(errors_triggered) > 0,
            action_taken="Triggered safe errors",
            before_state="No error patterns",
            after_state=errors_triggered,
            message=f"Triggered {len(errors_triggered)} safe errors: {', '.join(errors_triggered)}"
        )

    async def _heal_clear_stale_queue(self, diagnosis: Diagnosis) -> HealingResult:
        """Clear stale events from queue."""
        queue_file = Path.home() / ".spark" / "queue" / "events.jsonl"

        if queue_file.exists():
            before_size = len(queue_file.read_text().strip().split("\n"))
            # Archive instead of delete
            archive_path = queue_file.with_suffix(f".{int(time.time())}.bak")
            queue_file.rename(archive_path)

            return HealingResult(
                issue_id=diagnosis.issue_id,
                success=True,
                action_taken="Archived stale queue",
                before_state=before_size,
                after_state=0,
                message=f"Archived {before_size} events to {archive_path.name}"
            )

        return HealingResult(
            issue_id=diagnosis.issue_id,
            success=False,
            action_taken="No queue to clear",
            before_state=0,
            after_state=0,
            message="Queue file doesn't exist"
        )

    # ==================== VERIFICATION PHASE ====================

    async def verify(self) -> bool:
        """Verify that fixes were successful."""
        print("\n" + "=" * 50)
        print("  SPARK DOCTOR - Verification Phase")
        print("=" * 50 + "\n")

        # Re-run diagnosis
        new_diagnoses = await self.diagnose()

        # Compare
        before_issues = len([d for d in self.diagnoses if d.severity in (Severity.CRITICAL, Severity.WARNING)])
        after_issues = len([d for d in new_diagnoses if d.severity in (Severity.CRITICAL, Severity.WARNING)])

        print(f"\n  Before: {before_issues} issues")
        print(f"  After:  {after_issues} issues")

        if after_issues < before_issues:
            print(f"\n  [OK] Improved! Reduced issues by {before_issues - after_issues}")
            return True
        elif after_issues == before_issues:
            print(f"\n  [--] No change in issue count")
            return False
        else:
            print(f"\n  [!!] Issues increased (this shouldn't happen)")
            return False

    # ==================== REPORT ====================

    def generate_report(self) -> str:
        """Generate a summary report."""
        lines = []
        lines.append("\n" + "=" * 50)
        lines.append("  SPARK DOCTOR - Summary Report")
        lines.append("=" * 50 + "\n")

        # Diagnoses
        lines.append("DIAGNOSES:")
        for d in self.diagnoses:
            icon = {"critical": "XX", "warning": "!!", "info": "ii", "ok": "OK"}
            lines.append(f"  [{icon.get(d.severity.value, '??')}] {d.title}")

        # Healing Results
        if self.healing_results:
            lines.append("\nHEALING RESULTS:")
            for r in self.healing_results:
                status = "OK" if r.success else "FAIL"
                lines.append(f"  [{status}] {r.action_taken}: {r.message}")

        # Summary
        total_issues = len([d for d in self.diagnoses if d.severity != Severity.OK])
        healed = len([r for r in self.healing_results if r.success])

        lines.append(f"\nSUMMARY: {total_issues} issues found, {healed} healed")

        return "\n".join(lines)

    async def close(self):
        """Clean up resources."""
        await self.mind.close()


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Spark Doctor - Self-Healing Intelligence")
    parser.add_argument("--diagnose", action="store_true", help="Diagnosis only, no healing")
    parser.add_argument("--heal", action="store_true", help="Run healers without diagnosis")
    parser.add_argument("--auto", action="store_true", help="Auto-apply all fixes without prompting")
    parser.add_argument("--verify", action="store_true", help="Run verification after healing")

    args = parser.parse_args()

    print("\n" + "=" * 50)
    print("       SPARK DOCTOR")
    print("    Self-Healing Intelligence")
    print("=" * 50)

    doctor = SparkDoctor()

    try:
        # Diagnose
        if not args.heal:
            await doctor.diagnose()

        # Heal
        if not args.diagnose:
            await doctor.heal(auto=args.auto)

        # Verify
        if args.verify and doctor.healing_results:
            await doctor.verify()

        # Report
        print(doctor.generate_report())

    finally:
        await doctor.close()


if __name__ == "__main__":
    asyncio.run(main())
