"""
Spark Debugger: Trace inspection and replay for debugging.

Provides:
- Event trace capture and inspection
- Replay of event sequences
- Pattern debugging
- Learning path analysis
- Session reconstruction
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any, Tuple
from datetime import datetime
from enum import Enum
import json
from pathlib import Path

from .queue import SparkEvent, EventType
from .prompt_evolver import PromptPattern


class DebugLevel(Enum):
    """Debug output levels."""
    MINIMAL = "minimal"
    NORMAL = "normal"
    VERBOSE = "verbose"
    TRACE = "trace"


@dataclass
class TraceStep:
    """A single step in a trace."""
    step_number: int
    timestamp: datetime
    event_type: str
    tool_name: Optional[str]
    duration_ms: Optional[float]
    success: Optional[bool]
    data_summary: str
    raw_data: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DebugSession:
    """A captured debug session."""
    session_id: str
    started_at: datetime
    ended_at: Optional[datetime]
    steps: List[TraceStep]
    patterns_triggered: List[str]
    learnings_generated: List[str]
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ReplayResult:
    """Result of replaying a session."""
    session_id: str
    steps_replayed: int
    patterns_matched: List[str]
    learnings_would_generate: List[str]
    differences: List[str]
    success: bool


class SparkDebugger:
    """
    Debugger for Spark learning system.

    Provides tools to inspect, trace, and replay
    the learning and evolution process.
    """

    VERSION = "1.0.0"

    # Storage location
    DEBUG_DIR = Path.home() / ".spark" / "debug"

    def __init__(
        self,
        level: DebugLevel = DebugLevel.NORMAL,
        max_sessions: int = 50,
        auto_capture: bool = True
    ):
        self.level = level
        self.max_sessions = max_sessions
        self.auto_capture = auto_capture

        self.sessions: Dict[str, DebugSession] = {}
        self.current_session: Optional[DebugSession] = None
        self._event_buffer: List[SparkEvent] = []
        self._pattern_triggers: List[Tuple[str, str, datetime]] = []

        # Ensure debug directory exists
        self.DEBUG_DIR.mkdir(parents=True, exist_ok=True)

    def start_session(self, session_id: str, metadata: Optional[Dict[str, Any]] = None) -> DebugSession:
        """
        Start a new debug session.

        Args:
            session_id: Session identifier
            metadata: Additional metadata

        Returns:
            New DebugSession
        """
        session = DebugSession(
            session_id=session_id,
            started_at=datetime.now(),
            ended_at=None,
            steps=[],
            patterns_triggered=[],
            learnings_generated=[],
            metadata=metadata or {}
        )

        self.sessions[session_id] = session
        self.current_session = session

        self._log(f"Debug session started: {session_id}", DebugLevel.NORMAL)

        return session

    def end_session(self, session_id: Optional[str] = None) -> Optional[DebugSession]:
        """
        End a debug session.

        Args:
            session_id: Session to end (current if None)

        Returns:
            Ended session
        """
        target_id = session_id or (self.current_session.session_id if self.current_session else None)

        if not target_id or target_id not in self.sessions:
            return None

        session = self.sessions[target_id]
        session.ended_at = datetime.now()

        if self.auto_capture:
            self._save_session(session)

        if self.current_session and self.current_session.session_id == target_id:
            self.current_session = None

        self._log(f"Debug session ended: {target_id} ({len(session.steps)} steps)", DebugLevel.NORMAL)

        # Cleanup old sessions
        self._cleanup_old_sessions()

        return session

    def capture_event(self, event: SparkEvent) -> TraceStep:
        """
        Capture an event as a trace step.

        Args:
            event: Event to capture

        Returns:
            Created TraceStep
        """
        if not self.current_session:
            # Auto-start session if needed
            self.start_session(event.session_id or f"auto_{datetime.now().timestamp()}")

        # Derive success from error field (no error = success)
        success = event.error is None if hasattr(event, 'error') else None

        step = TraceStep(
            step_number=len(self.current_session.steps) + 1,
            timestamp=datetime.fromtimestamp(event.timestamp),
            event_type=event.event_type.value,
            tool_name=event.tool_name,
            duration_ms=event.duration_ms,
            success=success,
            data_summary=self._summarize_data(event.data),
            raw_data=event.data if self.level in [DebugLevel.VERBOSE, DebugLevel.TRACE] else {}
        )

        self.current_session.steps.append(step)
        self._event_buffer.append(event)

        self._log(
            f"Step {step.step_number}: {step.event_type} {step.tool_name or ''} "
            f"({step.duration_ms:.0f}ms)" if step.duration_ms else "",
            DebugLevel.VERBOSE
        )

        return step

    def capture_pattern_trigger(self, pattern_id: str, reason: str):
        """
        Record when a pattern is triggered.

        Args:
            pattern_id: Pattern that was triggered
            reason: Why it was triggered
        """
        self._pattern_triggers.append((pattern_id, reason, datetime.now()))

        if self.current_session:
            self.current_session.patterns_triggered.append(pattern_id)

        self._log(f"Pattern triggered: {pattern_id} - {reason}", DebugLevel.NORMAL)

    def capture_learning(self, learning_id: str, content_summary: str):
        """
        Record when a learning is generated.

        Args:
            learning_id: Learning identifier
            content_summary: Brief description
        """
        if self.current_session:
            self.current_session.learnings_generated.append(learning_id)

        self._log(f"Learning generated: {learning_id} - {content_summary[:50]}", DebugLevel.NORMAL)

    def _summarize_data(self, data: Dict[str, Any]) -> str:
        """Create a brief summary of event data."""
        if not data:
            return "(empty)"

        keys = list(data.keys())[:3]
        summary_parts = []

        for key in keys:
            value = data[key]
            if isinstance(value, str):
                summary_parts.append(f"{key}={value[:20]}...")
            elif isinstance(value, (int, float, bool)):
                summary_parts.append(f"{key}={value}")
            else:
                summary_parts.append(f"{key}=<{type(value).__name__}>")

        return ", ".join(summary_parts)

    def get_session(self, session_id: str) -> Optional[DebugSession]:
        """Get a session by ID."""
        return self.sessions.get(session_id)

    def get_session_trace(self, session_id: str) -> List[TraceStep]:
        """Get all trace steps for a session."""
        session = self.sessions.get(session_id)
        return session.steps if session else []

    def get_recent_steps(self, count: int = 10) -> List[TraceStep]:
        """Get most recent trace steps from current session."""
        if not self.current_session:
            return []
        return self.current_session.steps[-count:]

    def find_steps_by_tool(self, tool_name: str, session_id: Optional[str] = None) -> List[TraceStep]:
        """
        Find all steps that used a specific tool.

        Args:
            tool_name: Tool to search for
            session_id: Session to search (current if None)

        Returns:
            Matching steps
        """
        target_session = (
            self.sessions.get(session_id) if session_id
            else self.current_session
        )

        if not target_session:
            return []

        return [s for s in target_session.steps if s.tool_name == tool_name]

    def find_slow_steps(self, threshold_ms: float = 1000, session_id: Optional[str] = None) -> List[TraceStep]:
        """
        Find steps that took longer than threshold.

        Args:
            threshold_ms: Duration threshold
            session_id: Session to search

        Returns:
            Slow steps
        """
        target_session = (
            self.sessions.get(session_id) if session_id
            else self.current_session
        )

        if not target_session:
            return []

        return [
            s for s in target_session.steps
            if s.duration_ms and s.duration_ms > threshold_ms
        ]

    def find_failed_steps(self, session_id: Optional[str] = None) -> List[TraceStep]:
        """Find all failed steps in a session."""
        target_session = (
            self.sessions.get(session_id) if session_id
            else self.current_session
        )

        if not target_session:
            return []

        return [s for s in target_session.steps if s.success is False]

    def analyze_session(self, session_id: str) -> Dict[str, Any]:
        """
        Analyze a session for patterns and insights.

        Args:
            session_id: Session to analyze

        Returns:
            Analysis results
        """
        session = self.sessions.get(session_id)
        if not session:
            return {"error": "Session not found"}

        steps = session.steps
        if not steps:
            return {"error": "No steps in session"}

        # Calculate metrics
        total_duration = sum(s.duration_ms or 0 for s in steps)
        success_count = sum(1 for s in steps if s.success is True)
        failure_count = sum(1 for s in steps if s.success is False)

        # Tool usage
        tool_counts: Dict[str, int] = {}
        tool_durations: Dict[str, float] = {}
        for step in steps:
            if step.tool_name:
                tool_counts[step.tool_name] = tool_counts.get(step.tool_name, 0) + 1
                tool_durations[step.tool_name] = (
                    tool_durations.get(step.tool_name, 0) + (step.duration_ms or 0)
                )

        # Find sequences
        sequences = self._find_tool_sequences(steps)

        return {
            "session_id": session_id,
            "duration_seconds": (session.ended_at - session.started_at).total_seconds() if session.ended_at else None,
            "total_steps": len(steps),
            "total_duration_ms": total_duration,
            "success_count": success_count,
            "failure_count": failure_count,
            "success_rate": success_count / len(steps) if steps else 0,
            "tool_usage": tool_counts,
            "tool_time": tool_durations,
            "patterns_triggered": session.patterns_triggered,
            "learnings_generated": session.learnings_generated,
            "common_sequences": sequences[:5],
            "slowest_steps": [
                {"step": s.step_number, "tool": s.tool_name, "duration_ms": s.duration_ms}
                for s in sorted(steps, key=lambda x: x.duration_ms or 0, reverse=True)[:5]
            ]
        }

    def _find_tool_sequences(self, steps: List[TraceStep], length: int = 3) -> List[Tuple[str, int]]:
        """Find common tool sequences."""
        sequences: Dict[str, int] = {}

        tool_sequence = [s.tool_name for s in steps if s.tool_name]

        for i in range(len(tool_sequence) - length + 1):
            seq = " -> ".join(tool_sequence[i:i + length])
            sequences[seq] = sequences.get(seq, 0) + 1

        return sorted(sequences.items(), key=lambda x: -x[1])

    def replay_session(
        self,
        session_id: str,
        pattern_matcher: Optional[Any] = None
    ) -> ReplayResult:
        """
        Replay a session to see what patterns would match.

        Args:
            session_id: Session to replay
            pattern_matcher: Optional pattern matching function

        Returns:
            ReplayResult
        """
        session = self.sessions.get(session_id)
        if not session:
            return ReplayResult(
                session_id=session_id,
                steps_replayed=0,
                patterns_matched=[],
                learnings_would_generate=[],
                differences=[],
                success=False
            )

        patterns_matched = []
        learnings = []
        differences = []

        # Replay each step
        for step in session.steps:
            # Check if patterns would match
            if pattern_matcher:
                matched = pattern_matcher(step)
                if matched:
                    patterns_matched.extend(matched)

            # Compare to original
            if step.step_number <= len(session.patterns_triggered):
                original_pattern = session.patterns_triggered[step.step_number - 1] if session.patterns_triggered else None
                if original_pattern and original_pattern not in patterns_matched:
                    differences.append(
                        f"Step {step.step_number}: Original had {original_pattern}, replay didn't"
                    )

        return ReplayResult(
            session_id=session_id,
            steps_replayed=len(session.steps),
            patterns_matched=patterns_matched,
            learnings_would_generate=learnings,
            differences=differences,
            success=len(differences) == 0
        )

    def compare_sessions(self, session_id_1: str, session_id_2: str) -> Dict[str, Any]:
        """
        Compare two sessions.

        Args:
            session_id_1: First session
            session_id_2: Second session

        Returns:
            Comparison results
        """
        s1 = self.sessions.get(session_id_1)
        s2 = self.sessions.get(session_id_2)

        if not s1 or not s2:
            return {"error": "One or both sessions not found"}

        analysis_1 = self.analyze_session(session_id_1)
        analysis_2 = self.analyze_session(session_id_2)

        return {
            "session_1": session_id_1,
            "session_2": session_id_2,
            "steps_difference": len(s1.steps) - len(s2.steps),
            "duration_difference_ms": (analysis_1.get("total_duration_ms", 0) -
                                       analysis_2.get("total_duration_ms", 0)),
            "success_rate_1": analysis_1.get("success_rate", 0),
            "success_rate_2": analysis_2.get("success_rate", 0),
            "tools_only_in_1": set(analysis_1.get("tool_usage", {}).keys()) -
                              set(analysis_2.get("tool_usage", {}).keys()),
            "tools_only_in_2": set(analysis_2.get("tool_usage", {}).keys()) -
                              set(analysis_1.get("tool_usage", {}).keys()),
            "patterns_1": len(s1.patterns_triggered),
            "patterns_2": len(s2.patterns_triggered),
        }

    def export_session(self, session_id: str, format: str = "json") -> str:
        """
        Export a session for external analysis.

        Args:
            session_id: Session to export
            format: Export format (json, text)

        Returns:
            Exported content
        """
        session = self.sessions.get(session_id)
        if not session:
            return ""

        if format == "json":
            return json.dumps({
                "session_id": session.session_id,
                "started_at": session.started_at.isoformat(),
                "ended_at": session.ended_at.isoformat() if session.ended_at else None,
                "steps": [
                    {
                        "step": s.step_number,
                        "timestamp": s.timestamp.isoformat(),
                        "event_type": s.event_type,
                        "tool_name": s.tool_name,
                        "duration_ms": s.duration_ms,
                        "success": s.success,
                        "data_summary": s.data_summary
                    }
                    for s in session.steps
                ],
                "patterns_triggered": session.patterns_triggered,
                "learnings_generated": session.learnings_generated,
                "metadata": session.metadata
            }, indent=2)

        else:  # text format
            lines = [
                f"Session: {session.session_id}",
                f"Started: {session.started_at}",
                f"Ended: {session.ended_at}",
                "",
                "Steps:",
                "-" * 50
            ]

            for step in session.steps:
                lines.append(
                    f"{step.step_number:4d}. [{step.event_type:10}] {step.tool_name or 'N/A':15} "
                    f"{step.duration_ms or 0:8.0f}ms {'OK' if step.success else 'FAIL' if step.success is False else '??'}"
                )

            lines.extend([
                "",
                f"Patterns triggered: {len(session.patterns_triggered)}",
                f"Learnings generated: {len(session.learnings_generated)}"
            ])

            return "\n".join(lines)

    def _save_session(self, session: DebugSession):
        """Save session to disk."""
        filepath = self.DEBUG_DIR / f"{session.session_id}.json"
        content = self.export_session(session.session_id, "json")
        filepath.write_text(content)
        self._log(f"Session saved: {filepath}", DebugLevel.VERBOSE)

    def load_session(self, session_id: str) -> Optional[DebugSession]:
        """
        Load a session from disk.

        Args:
            session_id: Session to load

        Returns:
            Loaded session or None
        """
        filepath = self.DEBUG_DIR / f"{session_id}.json"
        if not filepath.exists():
            return None

        try:
            data = json.loads(filepath.read_text())
            session = DebugSession(
                session_id=data["session_id"],
                started_at=datetime.fromisoformat(data["started_at"]),
                ended_at=datetime.fromisoformat(data["ended_at"]) if data.get("ended_at") else None,
                steps=[
                    TraceStep(
                        step_number=s["step"],
                        timestamp=datetime.fromisoformat(s["timestamp"]),
                        event_type=s["event_type"],
                        tool_name=s.get("tool_name"),
                        duration_ms=s.get("duration_ms"),
                        success=s.get("success"),
                        data_summary=s.get("data_summary", "")
                    )
                    for s in data.get("steps", [])
                ],
                patterns_triggered=data.get("patterns_triggered", []),
                learnings_generated=data.get("learnings_generated", []),
                metadata=data.get("metadata", {})
            )
            self.sessions[session_id] = session
            return session

        except Exception as e:
            self._log(f"Error loading session: {e}", DebugLevel.MINIMAL)
            return None

    def list_saved_sessions(self) -> List[str]:
        """List all saved session IDs."""
        return [f.stem for f in self.DEBUG_DIR.glob("*.json")]

    def _cleanup_old_sessions(self):
        """Remove oldest sessions if over limit."""
        if len(self.sessions) > self.max_sessions:
            sorted_sessions = sorted(
                self.sessions.values(),
                key=lambda s: s.started_at
            )
            for session in sorted_sessions[:len(self.sessions) - self.max_sessions]:
                del self.sessions[session.session_id]

    def _log(self, message: str, level: DebugLevel):
        """Log a debug message if level permits."""
        levels = list(DebugLevel)
        if levels.index(level) <= levels.index(self.level):
            timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
            print(f"[DEBUG {timestamp}] {message}")

    def set_level(self, level: DebugLevel):
        """Set debug output level."""
        self.level = level

    def get_stats(self) -> Dict[str, Any]:
        """Get debugger statistics."""
        return {
            "level": self.level.value,
            "sessions_in_memory": len(self.sessions),
            "sessions_on_disk": len(self.list_saved_sessions()),
            "current_session": self.current_session.session_id if self.current_session else None,
            "current_session_steps": len(self.current_session.steps) if self.current_session else 0,
            "pattern_triggers_captured": len(self._pattern_triggers),
            "auto_capture": self.auto_capture
        }

    def clear(self):
        """Clear all debug data."""
        self.sessions.clear()
        self.current_session = None
        self._event_buffer.clear()
        self._pattern_triggers.clear()
