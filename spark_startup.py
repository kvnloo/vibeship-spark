#!/usr/bin/env python3
"""
Spark Startup - Session Initialization Validator

Run this at the START of every new session to ensure:
1. All systems are healthy
2. Learning continuity is maintained
3. No gaps or issues from previous sessions

Usage:
    python spark_startup.py          # Full startup check
    python spark_startup.py --quick  # Quick health only
    python spark_startup.py --fix    # Auto-fix any issues found
"""

import argparse
import asyncio
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Tuple

from lib.mind_client import MindClient


class StartupValidator:
    """Validates Spark is ready for a new session."""

    def __init__(self):
        self.checks: List[Tuple[str, bool, str]] = []  # (name, passed, message)
        self.warnings: List[str] = []
        self.critical: List[str] = []

    async def run_all_checks(self) -> bool:
        """Run all startup validation checks."""
        print("\n" + "=" * 60)
        print("  SPARK STARTUP - Session Initialization")
        print("=" * 60)
        print(f"  Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 60 + "\n")

        # Core checks
        await self._check_mind_connection()
        self._check_hooks_configured()
        self._check_daemon_status()
        self._check_queue_health()

        # Learning continuity checks
        await self._check_recent_activity()
        await self._check_learning_coverage()
        await self._check_error_capture()

        # Report
        self._print_report()

        return len(self.critical) == 0

    async def _check_mind_connection(self):
        """Check Mind is running and accessible."""
        print("  [1/7] Checking Mind connection...", end=" ")
        try:
            mind = MindClient()
            ok = await mind.is_available()
            await mind.close()

            if ok:
                self.checks.append(("Mind Connection", True, "Connected"))
                print("OK")
            else:
                self.checks.append(("Mind Connection", False, "Not responding"))
                self.critical.append("Mind is not running! Start with: start_mind_lite.bat")
                print("FAIL")
        except Exception as e:
            self.checks.append(("Mind Connection", False, str(e)[:30]))
            self.critical.append(f"Mind connection error: {e}")
            print("ERROR")

    def _check_hooks_configured(self):
        """Check all required hooks are in place."""
        print("  [2/7] Checking hooks...", end=" ")
        settings_file = Path.home() / ".claude" / "settings.json"
        required = ["SessionStart", "UserPromptSubmit", "PreToolUse",
                   "PostToolUse", "PostToolUseFailure", "Stop", "SessionEnd"]

        if not settings_file.exists():
            self.checks.append(("Hooks", False, "Settings file missing"))
            self.critical.append("Claude settings.json not found!")
            print("FAIL")
            return

        try:
            settings = json.loads(settings_file.read_text())
            hooks = settings.get("hooks", {})
            missing = [h for h in required if h not in hooks]

            if missing:
                self.checks.append(("Hooks", False, f"Missing: {', '.join(missing)}"))
                self.critical.append(f"Missing hooks: {', '.join(missing)}")
                print("FAIL")
            else:
                self.checks.append(("Hooks", True, f"All {len(required)} configured"))
                print("OK")
        except Exception as e:
            self.checks.append(("Hooks", False, str(e)[:30]))
            print("ERROR")

    def _check_daemon_status(self):
        """Check if daemon is running."""
        print("  [3/7] Checking daemon...", end=" ")
        pid_file = Path.home() / ".spark" / "daemon.pid"

        if not pid_file.exists():
            self.checks.append(("Daemon", False, "Not running"))
            self.warnings.append("Daemon not running - learning happens on-demand only")
            print("WARN")
            return

        try:
            import os
            pid = int(pid_file.read_text().strip())
            try:
                os.kill(pid, 0)
                self.checks.append(("Daemon", True, f"Running (PID {pid})"))
                print("OK")
            except (OSError, ProcessLookupError):
                self.checks.append(("Daemon", False, "Stale PID"))
                self.warnings.append("Daemon has stale PID - consider restarting")
                print("WARN")
        except:
            self.checks.append(("Daemon", False, "Cannot check"))
            print("WARN")

    def _check_queue_health(self):
        """Check queue isn't backed up."""
        print("  [4/7] Checking queue...", end=" ")
        queue_file = Path.home() / ".spark" / "queue" / "events.jsonl"

        if not queue_file.exists():
            self.checks.append(("Queue", True, "Empty (no file)"))
            print("OK")
            return

        try:
            lines = queue_file.read_text().strip().split("\n")
            size = len([l for l in lines if l.strip()])

            if size > 100:
                self.checks.append(("Queue", False, f"{size} events backed up"))
                self.warnings.append(f"Queue has {size} unprocessed events - run: python spark_cli.py learn")
                print("WARN")
            else:
                self.checks.append(("Queue", True, f"{size} events pending"))
                print("OK")
        except:
            self.checks.append(("Queue", True, "Cannot read"))
            print("OK")

    async def _check_recent_activity(self):
        """Check if there's been recent learning activity."""
        print("  [5/7] Checking recent activity...", end=" ")
        try:
            mind = MindClient()
            results = await mind.retrieve("LEARNING", limit=10)
            await mind.close()

            if not results:
                self.checks.append(("Recent Activity", False, "No learnings found"))
                self.warnings.append("No learnings in Mind - system may be new or Mind was reset")
                print("WARN")
                return

            # Check if any learnings are recent (last 24h)
            recent = 0
            day_ago = datetime.now() - timedelta(days=1)

            for r in results:
                created = r.get("created_at", "")
                if created:
                    try:
                        created_dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
                        created_dt = created_dt.replace(tzinfo=None)
                        if created_dt > day_ago:
                            recent += 1
                    except:
                        pass

            if recent > 0:
                self.checks.append(("Recent Activity", True, f"{recent} learnings in 24h"))
                print("OK")
            else:
                self.checks.append(("Recent Activity", True, f"{len(results)} total, none in 24h"))
                print("OK")

        except Exception as e:
            self.checks.append(("Recent Activity", False, str(e)[:30]))
            print("WARN")

    async def _check_learning_coverage(self):
        """Check learning coverage across types."""
        print("  [6/7] Checking learning coverage...", end=" ")
        try:
            mind = MindClient()

            # Check different pattern types
            types = {
                "Tools": await mind.retrieve("TOOL_EFFECTIVENESS", limit=5),
                "Sequences": await mind.retrieve("TOOL_SEQUENCE", limit=5),
                "Goals": await mind.retrieve("GOAL_STRATEGY", limit=5),
                "Errors": await mind.retrieve("ERROR_CATEGORY", limit=5),
            }
            await mind.close()

            coverage = []
            gaps = []
            for name, results in types.items():
                if results:
                    coverage.append(name)
                else:
                    gaps.append(name)

            if gaps:
                self.checks.append(("Learning Coverage", True, f"Gaps: {', '.join(gaps)}"))
                if "Errors" in gaps:
                    self.warnings.append("No error patterns yet - trigger some errors to test")
                print("OK" if len(gaps) <= 1 else "WARN")
            else:
                self.checks.append(("Learning Coverage", True, "Full coverage"))
                print("OK")

        except Exception as e:
            self.checks.append(("Learning Coverage", False, str(e)[:30]))
            print("WARN")

    async def _check_error_capture(self):
        """Verify error capture is working."""
        print("  [7/7] Checking error capture...", end=" ")

        # Check if PostToolUseFailure events are in processed queue
        processed_file = Path.home() / ".spark" / "queue" / "processed.jsonl"

        if not processed_file.exists():
            self.checks.append(("Error Capture", True, "No processed events yet"))
            print("OK")
            return

        try:
            content = processed_file.read_text()
            lines = content.strip().split("\n")[-100:]  # Last 100

            failures = 0
            for line in lines:
                if line.strip():
                    try:
                        event = json.loads(line)
                        if event.get("event_type") == "post_tool_failure":
                            failures += 1
                    except:
                        pass

            if failures > 0:
                self.checks.append(("Error Capture", True, f"{failures} failures captured"))
                print("OK")
            else:
                self.checks.append(("Error Capture", True, "No recent failures"))
                print("OK")

        except:
            self.checks.append(("Error Capture", True, "Cannot check"))
            print("OK")

    def _print_report(self):
        """Print the validation report."""
        print("\n" + "-" * 60)
        print("  VALIDATION RESULTS")
        print("-" * 60)

        # Summary table
        passed = sum(1 for _, ok, _ in self.checks if ok)
        total = len(self.checks)

        for name, ok, msg in self.checks:
            status = "OK" if ok else "!!"
            print(f"  [{status}] {name}: {msg}")

        # Warnings
        if self.warnings:
            print("\n  WARNINGS:")
            for w in self.warnings:
                print(f"    - {w}")

        # Critical
        if self.critical:
            print("\n  CRITICAL ISSUES:")
            for c in self.critical:
                print(f"    !! {c}")

        # Final status
        print("\n" + "=" * 60)
        if self.critical:
            print("  STATUS: BLOCKED - Fix critical issues before proceeding")
        elif self.warnings:
            print(f"  STATUS: READY ({passed}/{total} checks passed, {len(self.warnings)} warnings)")
        else:
            print(f"  STATUS: ALL SYSTEMS GO ({passed}/{total} checks passed)")
        print("=" * 60 + "\n")


async def run_doctor_if_needed(auto_fix: bool):
    """Run Spark Doctor if issues found."""
    if auto_fix:
        print("\n  Running Spark Doctor to fix issues...")
        from spark_doctor import SparkDoctor
        doctor = SparkDoctor()
        await doctor.diagnose()
        await doctor.heal(auto=True)
        print(doctor.generate_report())
        await doctor.close()


async def main():
    parser = argparse.ArgumentParser(description="Spark Startup - Session Validator")
    parser.add_argument("--quick", action="store_true", help="Quick check only")
    parser.add_argument("--fix", action="store_true", help="Auto-fix issues found")

    args = parser.parse_args()

    validator = StartupValidator()
    ok = await validator.run_all_checks()

    if not ok and args.fix:
        await run_doctor_if_needed(auto_fix=True)

    # Exit code
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    asyncio.run(main())
