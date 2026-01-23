"""
Spark Witness: Unified Self-Evolving Observer.

The Witness is not 20 separate diagnostic tools - it's ONE intelligent
observer that watches everything and grows as Spark grows.

Design Principles:
1. Systems register themselves with the Witness
2. Witness learns what to watch based on what breaks
3. Single "what's happening?" gives holistic view
4. Auto-discovers new systems when they're added

Usage:
    witness = SparkWitness()
    witness.observe()  # Snapshot of everything
    witness.explain()  # Human-readable "what's going on"
"""

import json
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set
from enum import Enum


class SystemHealth(Enum):
    """Health states for observed systems."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class SystemObservation:
    """Observation of a single system."""
    system_name: str
    health: SystemHealth
    metrics: Dict[str, Any]
    message: str
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {
            "system": self.system_name,
            "health": self.health.value,
            "metrics": self.metrics,
            "message": self.message,
            "timestamp": self.timestamp
        }


@dataclass
class WitnessSnapshot:
    """Complete snapshot of system state."""
    timestamp: float
    overall_health: SystemHealth
    systems: Dict[str, SystemObservation]
    active_goal: Optional[dict]
    recent_events: int
    learnings_count: int
    anomalies: List[str]

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "overall_health": self.overall_health.value,
            "systems": {k: v.to_dict() for k, v in self.systems.items()},
            "active_goal": self.active_goal,
            "recent_events": self.recent_events,
            "learnings_count": self.learnings_count,
            "anomalies": self.anomalies
        }


class SparkWitness:
    """
    Unified observer that watches all Spark systems.

    Instead of 20 separate health checks, the Witness:
    1. Maintains a registry of systems to watch
    2. Observes them holistically
    3. Explains what's happening in plain language
    4. Evolves as new systems are added
    """

    # State file for persistence
    STATE_FILE = Path.home() / ".spark" / "witness_state.json"

    def __init__(self):
        self.systems: Dict[str, Callable[[], SystemObservation]] = {}
        self.observation_history: List[WitnessSnapshot] = []
        self.anomaly_patterns: Dict[str, int] = {}  # pattern -> count

        # Auto-register core systems
        self._register_core_systems()

        # Load historical state
        self._load_state()

    def _register_core_systems(self):
        """Register the core Spark systems to watch."""

        # Queue System
        self.register_system("queue", self._observe_queue)

        # Mind Connection
        self.register_system("mind", self._observe_mind)

        # Goals
        self.register_system("goals", self._observe_goals)

        # Hooks
        self.register_system("hooks", self._observe_hooks)

        # Predictions
        self.register_system("predictions", self._observe_predictions)

        # Injections (advice)
        self.register_system("injections", self._observe_injections)

        # Daemon
        self.register_system("daemon", self._observe_daemon)

        # Tool Statistics (NEW)
        self.register_system("tool_stats", self._observe_tool_stats)

        # Learnings (NEW)
        self.register_system("learnings", self._observe_learnings)

        # Error Patterns (NEW)
        self.register_system("error_patterns", self._observe_error_patterns)

        # Processing Stats (NEW)
        self.register_system("processing", self._observe_processing)

    def register_system(self, name: str, observer: Callable[[], SystemObservation]):
        """
        Register a new system to watch.

        This is how Witness grows - new systems call this to add themselves.
        """
        self.systems[name] = observer

    def observe(self) -> WitnessSnapshot:
        """
        Take a complete snapshot of all systems.

        This is the main entry point - call this to know what's happening.
        """
        timestamp = time.time()
        observations = {}
        anomalies = []

        # Observe each registered system
        for name, observer in self.systems.items():
            try:
                obs = observer()
                observations[name] = obs

                # Track anomalies
                if obs.health == SystemHealth.UNHEALTHY:
                    anomalies.append(f"{name}: {obs.message}")
                    self._record_anomaly(f"{name}:unhealthy")
                elif obs.health == SystemHealth.DEGRADED:
                    self._record_anomaly(f"{name}:degraded")

            except Exception as e:
                observations[name] = SystemObservation(
                    system_name=name,
                    health=SystemHealth.UNKNOWN,
                    metrics={},
                    message=f"Observation failed: {str(e)[:50]}"
                )
                anomalies.append(f"{name}: observation failed")

        # Determine overall health
        healths = [obs.health for obs in observations.values()]
        if SystemHealth.UNHEALTHY in healths:
            overall = SystemHealth.UNHEALTHY
        elif SystemHealth.DEGRADED in healths:
            overall = SystemHealth.DEGRADED
        elif SystemHealth.UNKNOWN in healths:
            overall = SystemHealth.DEGRADED
        else:
            overall = SystemHealth.HEALTHY

        # Get active goal
        active_goal = self._get_active_goal()

        # Get recent event count
        recent_events = self._count_recent_events()

        # Get learnings count
        learnings_count = self._count_learnings()

        snapshot = WitnessSnapshot(
            timestamp=timestamp,
            overall_health=overall,
            systems=observations,
            active_goal=active_goal,
            recent_events=recent_events,
            learnings_count=learnings_count,
            anomalies=anomalies
        )

        # Store in history
        self.observation_history.append(snapshot)
        if len(self.observation_history) > 100:
            self.observation_history = self.observation_history[-100:]

        # Save state
        self._save_state()

        return snapshot

    def explain(self, verbose: bool = False) -> str:
        """
        Explain what's happening in plain language.

        This is the "what's really going on?" answer.
        """
        snapshot = self.observe()

        lines = []

        # Header (ASCII-safe for Windows)
        health_emoji = {
            SystemHealth.HEALTHY: "OK",
            SystemHealth.DEGRADED: "~~",
            SystemHealth.UNHEALTHY: "XX",
            SystemHealth.UNKNOWN: "??"
        }
        lines.append(f"\n[{health_emoji[snapshot.overall_health]}] Spark Status: {snapshot.overall_health.value.upper()}")
        lines.append("-" * 50)

        # Active goal
        if snapshot.active_goal:
            goal_type = snapshot.active_goal.get("goal_type", "unknown")
            desc = snapshot.active_goal.get("description", "")[:40]
            actions = len(snapshot.active_goal.get("actions", []))
            lines.append(f"Goal: [{goal_type}] {desc}... ({actions} actions)")
        else:
            lines.append("Goal: None active")

        # Quick stats
        lines.append(f"Events: {snapshot.recent_events} pending | Learnings: {snapshot.learnings_count} stored")

        # System summary
        lines.append("")
        healthy = sum(1 for o in snapshot.systems.values() if o.health == SystemHealth.HEALTHY)
        total = len(snapshot.systems)
        lines.append(f"Systems: {healthy}/{total} healthy")

        if verbose:
            for name, obs in snapshot.systems.items():
                emoji = health_emoji[obs.health]
                lines.append(f"  [{emoji}] {name}: {obs.message}")

        # Anomalies
        if snapshot.anomalies:
            lines.append("")
            lines.append("Issues:")
            for anomaly in snapshot.anomalies:
                lines.append(f"  ! {anomaly}")

        # Recurring patterns (learned from history)
        recurring = self._get_recurring_anomalies()
        if recurring:
            lines.append("")
            lines.append("Recurring issues (needs attention):")
            for pattern, count in recurring[:3]:
                lines.append(f"  [{count}x] {pattern}")

        return "\n".join(lines)

    def _record_anomaly(self, pattern: str):
        """Record an anomaly pattern for learning."""
        self.anomaly_patterns[pattern] = self.anomaly_patterns.get(pattern, 0) + 1

    def _get_recurring_anomalies(self) -> List[tuple]:
        """Get anomalies that keep happening."""
        return sorted(
            [(k, v) for k, v in self.anomaly_patterns.items() if v >= 2],
            key=lambda x: x[1],
            reverse=True
        )

    # ===== System Observers =====

    def _observe_queue(self) -> SystemObservation:
        """Observe the event queue."""
        queue_file = Path.home() / ".spark" / "queue" / "events.jsonl"

        if not queue_file.exists():
            return SystemObservation(
                system_name="queue",
                health=SystemHealth.HEALTHY,
                metrics={"size": 0},
                message="Empty queue (file not created)"
            )

        try:
            lines = queue_file.read_text().strip().split("\n")
            size = len([l for l in lines if l.strip()])

            health = SystemHealth.HEALTHY
            if size > 100:
                health = SystemHealth.DEGRADED
            elif size > 500:
                health = SystemHealth.UNHEALTHY

            return SystemObservation(
                system_name="queue",
                health=health,
                metrics={"size": size},
                message=f"{size} events pending"
            )
        except Exception as e:
            return SystemObservation(
                system_name="queue",
                health=SystemHealth.UNKNOWN,
                metrics={},
                message=f"Read error: {str(e)[:30]}"
            )

    def _observe_mind(self) -> SystemObservation:
        """Observe Mind connection."""
        import asyncio

        async def check_mind():
            from .mind_client import MindClient
            client = MindClient()
            ok = await client.is_available()
            await client.close()
            return ok

        try:
            # Run async check
            loop = asyncio.new_event_loop()
            ok = loop.run_until_complete(check_mind())
            loop.close()

            if ok:
                return SystemObservation(
                    system_name="mind",
                    health=SystemHealth.HEALTHY,
                    metrics={"connected": True},
                    message="Connected to Mind"
                )
            else:
                return SystemObservation(
                    system_name="mind",
                    health=SystemHealth.UNHEALTHY,
                    metrics={"connected": False},
                    message="Mind offline"
                )
        except Exception as e:
            return SystemObservation(
                system_name="mind",
                health=SystemHealth.UNKNOWN,
                metrics={},
                message=f"Check failed: {str(e)[:30]}"
            )

    def _observe_goals(self) -> SystemObservation:
        """Observe goal tracking."""
        goals_file = Path.home() / ".spark" / "active_goals.json"

        if not goals_file.exists():
            return SystemObservation(
                system_name="goals",
                health=SystemHealth.HEALTHY,
                metrics={"active": 0, "completed": 0},
                message="No goals tracked yet"
            )

        try:
            goals = json.loads(goals_file.read_text())
            active = sum(1 for g in goals.values() if g.get("status") == "active")
            completed = sum(1 for g in goals.values() if g.get("status") == "completed")

            return SystemObservation(
                system_name="goals",
                health=SystemHealth.HEALTHY,
                metrics={"active": active, "completed": completed, "total": len(goals)},
                message=f"{active} active, {completed} completed"
            )
        except Exception as e:
            return SystemObservation(
                system_name="goals",
                health=SystemHealth.DEGRADED,
                metrics={},
                message=f"Parse error: {str(e)[:30]}"
            )

    def _observe_hooks(self) -> SystemObservation:
        """Observe hook configuration."""
        settings_file = Path.home() / ".claude" / "settings.json"

        REQUIRED = ["SessionStart", "UserPromptSubmit", "PreToolUse",
                   "PostToolUse", "PostToolUseFailure", "Stop", "SessionEnd"]

        if not settings_file.exists():
            return SystemObservation(
                system_name="hooks",
                health=SystemHealth.UNHEALTHY,
                metrics={"configured": 0, "required": len(REQUIRED)},
                message="Settings file missing"
            )

        try:
            settings = json.loads(settings_file.read_text())
            hooks = settings.get("hooks", {})
            configured = [h for h in REQUIRED if h in hooks]
            missing = [h for h in REQUIRED if h not in hooks]

            if missing:
                return SystemObservation(
                    system_name="hooks",
                    health=SystemHealth.UNHEALTHY,
                    metrics={"configured": len(configured), "missing": missing},
                    message=f"Missing: {', '.join(missing)}"
                )

            return SystemObservation(
                system_name="hooks",
                health=SystemHealth.HEALTHY,
                metrics={"configured": len(configured)},
                message=f"All {len(REQUIRED)} hooks configured"
            )
        except Exception as e:
            return SystemObservation(
                system_name="hooks",
                health=SystemHealth.UNKNOWN,
                metrics={},
                message=f"Parse error: {str(e)[:30]}"
            )

    def _observe_predictions(self) -> SystemObservation:
        """Observe prediction system."""
        pred_file = Path.home() / ".spark" / "predictions.json"

        if not pred_file.exists():
            return SystemObservation(
                system_name="predictions",
                health=SystemHealth.HEALTHY,
                metrics={"active": 0},
                message="No active predictions"
            )

        try:
            predictions = json.loads(pred_file.read_text())
            count = len(predictions)

            return SystemObservation(
                system_name="predictions",
                health=SystemHealth.HEALTHY,
                metrics={"active": count},
                message=f"{count} active predictions"
            )
        except:
            return SystemObservation(
                system_name="predictions",
                health=SystemHealth.HEALTHY,
                metrics={"active": 0},
                message="No predictions"
            )

    def _observe_injections(self) -> SystemObservation:
        """Observe advice injection tracking."""
        inj_file = Path.home() / ".spark" / "active_injections.json"

        if not inj_file.exists():
            return SystemObservation(
                system_name="injections",
                health=SystemHealth.HEALTHY,
                metrics={"active": 0},
                message="No active injections"
            )

        try:
            injections = json.loads(inj_file.read_text())
            count = len(injections)
            followed = sum(1 for i in injections.values() if i.get("followed"))

            return SystemObservation(
                system_name="injections",
                health=SystemHealth.HEALTHY,
                metrics={"active": count, "followed": followed},
                message=f"{count} tracked, {followed} followed"
            )
        except:
            return SystemObservation(
                system_name="injections",
                health=SystemHealth.HEALTHY,
                metrics={},
                message="No injections"
            )

    def _observe_daemon(self) -> SystemObservation:
        """Observe background processor daemon."""
        pid_file = Path.home() / ".spark" / "daemon.pid"

        if not pid_file.exists():
            return SystemObservation(
                system_name="daemon",
                health=SystemHealth.DEGRADED,
                metrics={"running": False},
                message="Daemon not running"
            )

        try:
            pid = int(pid_file.read_text().strip())
            # Check if process exists (platform-specific)
            import os
            try:
                os.kill(pid, 0)  # Signal 0 = check if exists
                running = True
            except (OSError, ProcessLookupError):
                running = False

            if running:
                return SystemObservation(
                    system_name="daemon",
                    health=SystemHealth.HEALTHY,
                    metrics={"running": True, "pid": pid},
                    message=f"Running (PID {pid})"
                )
            else:
                return SystemObservation(
                    system_name="daemon",
                    health=SystemHealth.DEGRADED,
                    metrics={"running": False, "stale_pid": pid},
                    message="Stale PID file (daemon stopped)"
                )
        except:
            return SystemObservation(
                system_name="daemon",
                health=SystemHealth.DEGRADED,
                metrics={},
                message="Cannot check daemon status"
            )

    def _observe_tool_stats(self) -> SystemObservation:
        """Observe tool effectiveness patterns from Mind."""
        import asyncio

        async def get_tool_stats():
            from .mind_client import MindClient
            client = MindClient()
            try:
                # Query for tool effectiveness learnings
                results = await client.retrieve("tool_effectiveness LEARNING", limit=50)
                await client.close()
                return results
            except Exception as e:
                await client.close()
                return []

        try:
            loop = asyncio.new_event_loop()
            results = loop.run_until_complete(get_tool_stats())
            loop.close()

            if not results:
                return SystemObservation(
                    system_name="tool_stats",
                    health=SystemHealth.HEALTHY,
                    metrics={"patterns": 0},
                    message="No tool patterns yet (still learning)"
                )

            # Parse tool stats from learnings
            tools = {}
            for r in results:
                content = r.get("content", "")
                if "tool_effectiveness" in content.lower():
                    # Extract tool name from content
                    if "tool=" in content:
                        tool = content.split("tool=")[1].split()[0].strip("',\"")
                        tools[tool] = tools.get(tool, 0) + 1

            if tools:
                top_tools = sorted(tools.items(), key=lambda x: x[1], reverse=True)[:3]
                tool_str = ", ".join(f"{t}({c})" for t, c in top_tools)
                return SystemObservation(
                    system_name="tool_stats",
                    health=SystemHealth.HEALTHY,
                    metrics={"patterns": len(results), "tools": tools},
                    message=f"{len(results)} patterns: {tool_str}"
                )

            return SystemObservation(
                system_name="tool_stats",
                health=SystemHealth.HEALTHY,
                metrics={"patterns": len(results)},
                message=f"{len(results)} tool patterns stored"
            )
        except Exception as e:
            return SystemObservation(
                system_name="tool_stats",
                health=SystemHealth.UNKNOWN,
                metrics={},
                message=f"Query failed: {str(e)[:30]}"
            )

    def _observe_learnings(self) -> SystemObservation:
        """Observe overall learnings from Mind."""
        import asyncio

        async def get_learning_stats():
            from .mind_client import MindClient
            client = MindClient()
            try:
                results = await client.retrieve("LEARNING", limit=100)
                await client.close()
                return results
            except:
                await client.close()
                return []

        try:
            loop = asyncio.new_event_loop()
            results = loop.run_until_complete(get_learning_stats())
            loop.close()

            if not results:
                return SystemObservation(
                    system_name="learnings",
                    health=SystemHealth.HEALTHY,
                    metrics={"total": 0},
                    message="No learnings yet"
                )

            # Categorize learnings by type
            types = {}
            for r in results:
                content = r.get("content", "")
                # Try to determine type
                if "tool_effectiveness" in content.lower():
                    types["tool"] = types.get("tool", 0) + 1
                elif "error_category" in content.lower() or "error_recovery" in content.lower():
                    types["error"] = types.get("error", 0) + 1
                elif "goal_strategy" in content.lower():
                    types["goal"] = types.get("goal", 0) + 1
                elif "tool_sequence" in content.lower() or "parallel" in content.lower():
                    types["sequence"] = types.get("sequence", 0) + 1
                else:
                    types["other"] = types.get("other", 0) + 1

            # Format breakdown
            breakdown = ", ".join(f"{k}:{v}" for k, v in sorted(types.items(), key=lambda x: x[1], reverse=True) if v > 0)

            health = SystemHealth.HEALTHY
            if len(results) < 10:
                health = SystemHealth.DEGRADED  # Still learning

            return SystemObservation(
                system_name="learnings",
                health=health,
                metrics={"total": len(results), "types": types},
                message=f"{len(results)} total [{breakdown}]"
            )
        except Exception as e:
            return SystemObservation(
                system_name="learnings",
                health=SystemHealth.UNKNOWN,
                metrics={},
                message=f"Query failed: {str(e)[:30]}"
            )

    def _observe_error_patterns(self) -> SystemObservation:
        """Observe error patterns and recovery strategies."""
        import asyncio

        async def get_error_patterns():
            from .mind_client import MindClient
            client = MindClient()
            try:
                results = await client.retrieve("error_category error_recovery LEARNING", limit=50)
                await client.close()
                return results
            except:
                await client.close()
                return []

        try:
            loop = asyncio.new_event_loop()
            results = loop.run_until_complete(get_error_patterns())
            loop.close()

            if not results:
                return SystemObservation(
                    system_name="error_patterns",
                    health=SystemHealth.HEALTHY,
                    metrics={"patterns": 0, "recoveries": 0},
                    message="No error patterns (good! or still learning)"
                )

            # Count error categories vs recovery strategies
            categories = 0
            recoveries = 0
            for r in results:
                content = r.get("content", "").lower()
                if "error_category" in content:
                    categories += 1
                if "recovery" in content or "fix" in content:
                    recoveries += 1

            return SystemObservation(
                system_name="error_patterns",
                health=SystemHealth.HEALTHY,
                metrics={"patterns": categories, "recoveries": recoveries},
                message=f"{categories} error types, {recoveries} recovery strategies"
            )
        except Exception as e:
            return SystemObservation(
                system_name="error_patterns",
                health=SystemHealth.UNKNOWN,
                metrics={},
                message=f"Query failed: {str(e)[:30]}"
            )

    def _observe_processing(self) -> SystemObservation:
        """Observe processing statistics."""
        stats_file = Path.home() / ".spark" / "processing_stats.json"
        queue_file = Path.home() / ".spark" / "queue" / "events.jsonl"

        try:
            # Count queue events
            queue_size = 0
            if queue_file.exists():
                lines = queue_file.read_text().strip().split("\n")
                queue_size = len([l for l in lines if l.strip()])

            # Check for processing stats
            if stats_file.exists():
                stats = json.loads(stats_file.read_text())
                processed = stats.get("total_processed", 0)
                last_run = stats.get("last_run", "never")

                return SystemObservation(
                    system_name="processing",
                    health=SystemHealth.HEALTHY,
                    metrics={"queue": queue_size, "processed": processed, "last_run": last_run},
                    message=f"Queue: {queue_size}, Processed: {processed}"
                )

            # No stats file yet
            return SystemObservation(
                system_name="processing",
                health=SystemHealth.HEALTHY if queue_size < 50 else SystemHealth.DEGRADED,
                metrics={"queue": queue_size, "processed": 0},
                message=f"Queue: {queue_size}, Processed: 0 (processor not yet run)"
            )
        except Exception as e:
            return SystemObservation(
                system_name="processing",
                health=SystemHealth.UNKNOWN,
                metrics={},
                message=f"Check failed: {str(e)[:30]}"
            )

    # ===== Helpers =====

    def _get_active_goal(self) -> Optional[dict]:
        """Get the current active goal."""
        goals_file = Path.home() / ".spark" / "active_goals.json"
        if not goals_file.exists():
            return None

        try:
            goals = json.loads(goals_file.read_text())
            for g in goals.values():
                if g.get("status") == "active":
                    return g
        except:
            pass
        return None

    def _count_recent_events(self) -> int:
        """Count events in queue."""
        queue_file = Path.home() / ".spark" / "queue" / "events.jsonl"
        if not queue_file.exists():
            return 0
        try:
            return len([l for l in queue_file.read_text().strip().split("\n") if l])
        except:
            return 0

    def _count_learnings(self) -> int:
        """Count learnings (from last witness state)."""
        if self.STATE_FILE.exists():
            try:
                state = json.loads(self.STATE_FILE.read_text())
                return state.get("learning_count", 0)
            except:
                pass
        return 0

    def _load_state(self):
        """Load historical state."""
        if self.STATE_FILE.exists():
            try:
                state = json.loads(self.STATE_FILE.read_text())
                self.anomaly_patterns = state.get("anomaly_patterns", {})
            except:
                pass

    def _save_state(self):
        """Save state for persistence."""
        self.STATE_FILE.parent.mkdir(parents=True, exist_ok=True)

        state = {
            "timestamp": datetime.now().isoformat(),
            "learning_count": self._count_learnings(),
            "anomaly_patterns": self.anomaly_patterns,
            "systems_registered": list(self.systems.keys())
        }

        self.STATE_FILE.write_text(json.dumps(state, indent=2))


# Convenience function
def witness() -> str:
    """Quick access to Witness explanation."""
    w = SparkWitness()
    return w.explain()


def watch(interval: int = 5, verbose: bool = False):
    """
    Live monitoring mode - continuously watch all systems.

    Args:
        interval: Seconds between updates
        verbose: Show detailed system status
    """
    import os
    import sys

    w = SparkWitness()
    iteration = 0

    print(f"[LIVE] Watching Spark (Ctrl+C to stop, interval={interval}s)")
    print("=" * 60)

    try:
        while True:
            iteration += 1

            # Clear screen (platform-specific)
            os.system('cls' if os.name == 'nt' else 'clear')

            # Header
            print(f"[LIVE] Spark Witness | Iteration {iteration} | {datetime.now().strftime('%H:%M:%S')}")
            print("=" * 60)

            # Get current state
            snapshot = w.observe()

            # Show explanation
            print(w.explain(verbose=verbose))

            # Show delta from last observation
            if len(w.observation_history) > 1:
                prev = w.observation_history[-2]
                curr = w.observation_history[-1]

                deltas = []
                if curr.recent_events != prev.recent_events:
                    diff = curr.recent_events - prev.recent_events
                    deltas.append(f"Events: {'+' if diff > 0 else ''}{diff}")
                if curr.learnings_count != prev.learnings_count:
                    diff = curr.learnings_count - prev.learnings_count
                    deltas.append(f"Learnings: {'+' if diff > 0 else ''}{diff}")

                if deltas:
                    print("\n" + "-" * 50)
                    print(f"Delta: {', '.join(deltas)}")

            # Footer
            print("\n" + "=" * 60)
            print(f"[LIVE] Next update in {interval}s... (Ctrl+C to stop)")

            time.sleep(interval)

    except KeyboardInterrupt:
        print("\n\n[LIVE] Stopped watching.")
        sys.exit(0)


if __name__ == "__main__":
    # CLI usage
    import sys

    args = sys.argv[1:]

    if "--live" in args or "-l" in args:
        # Live mode
        verbose = "-v" in args or "--verbose" in args
        interval = 5
        for i, arg in enumerate(args):
            if arg in ("--interval", "-i") and i + 1 < len(args):
                try:
                    interval = int(args[i + 1])
                except ValueError:
                    pass
        watch(interval=interval, verbose=verbose)
    elif "-v" in args or "--verbose" in args:
        w = SparkWitness()
        print(w.explain(verbose=True))
    else:
        w = SparkWitness()
        print(w.explain())
