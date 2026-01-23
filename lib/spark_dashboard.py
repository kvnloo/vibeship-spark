"""
Spark Dashboard: Terminal UI for system state visualization.

Provides real-time views of:
- Learning statistics and trends
- Pattern effectiveness rankings
- Active experiments status
- Queue health and throughput
- Session activity
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any, Callable
from datetime import datetime, timedelta
from enum import Enum
import asyncio

from .mind_client import MindClient
from .learner import SparkLearner
from .prompt_evolver import PromptEvolver, PromptPattern
from .meta_learner import MetaLearner
from .suggester import Suggester
from .experiment_manager import ExperimentManager
from .queue import SparkQueue


class DashboardView(Enum):
    """Available dashboard views."""
    OVERVIEW = "overview"
    PATTERNS = "patterns"
    EXPERIMENTS = "experiments"
    LEARNINGS = "learnings"
    QUEUE = "queue"
    SESSION = "session"


@dataclass
class ViewData:
    """Data for a dashboard view."""
    title: str
    updated_at: datetime
    content: Dict[str, Any]
    warnings: List[str] = field(default_factory=list)
    highlights: List[str] = field(default_factory=list)


@dataclass
class DashboardState:
    """Current dashboard state."""
    current_view: DashboardView
    views: Dict[DashboardView, ViewData]
    refresh_interval: int  # seconds
    last_refresh: Optional[datetime] = None
    is_live: bool = False


class SparkDashboard:
    """
    Terminal UI for Spark system state.

    Provides multiple views for monitoring and understanding
    the self-evolving intelligence system.
    """

    VERSION = "1.0.0"

    # Terminal formatting
    TERM_WIDTH = 80
    BOX_CHARS = {
        "tl": "+", "tr": "+", "bl": "+", "br": "+",
        "h": "-", "v": "|",
        "lt": "+", "rt": "+", "tt": "+", "bt": "+"
    }

    def __init__(
        self,
        mind_client: Optional[MindClient] = None,
        learner: Optional[SparkLearner] = None,
        evolver: Optional[PromptEvolver] = None,
        meta_learner: Optional[MetaLearner] = None,
        suggester: Optional[Suggester] = None,
        experiment_manager: Optional[ExperimentManager] = None,
        queue: Optional[SparkQueue] = None
    ):
        self.mind = mind_client
        self.learner = learner
        self.evolver = evolver
        self.meta_learner = meta_learner
        self.suggester = suggester
        self.experiment_manager = experiment_manager
        self.queue = queue or SparkQueue()

        self.state = DashboardState(
            current_view=DashboardView.OVERVIEW,
            views={},
            refresh_interval=30
        )

        self._view_renderers: Dict[DashboardView, Callable] = {
            DashboardView.OVERVIEW: self._render_overview,
            DashboardView.PATTERNS: self._render_patterns,
            DashboardView.EXPERIMENTS: self._render_experiments,
            DashboardView.LEARNINGS: self._render_learnings,
            DashboardView.QUEUE: self._render_queue,
            DashboardView.SESSION: self._render_session,
        }

    async def refresh(self, view: Optional[DashboardView] = None) -> ViewData:
        """
        Refresh dashboard data for a view.

        Args:
            view: View to refresh (current if None)

        Returns:
            Updated ViewData
        """
        target_view = view or self.state.current_view

        # Collect data based on view
        if target_view == DashboardView.OVERVIEW:
            data = await self._collect_overview_data()
        elif target_view == DashboardView.PATTERNS:
            data = await self._collect_patterns_data()
        elif target_view == DashboardView.EXPERIMENTS:
            data = await self._collect_experiments_data()
        elif target_view == DashboardView.LEARNINGS:
            data = await self._collect_learnings_data()
        elif target_view == DashboardView.QUEUE:
            data = await self._collect_queue_data()
        elif target_view == DashboardView.SESSION:
            data = await self._collect_session_data()
        else:
            data = {"error": "Unknown view"}

        view_data = ViewData(
            title=target_view.value.upper(),
            updated_at=datetime.now(),
            content=data,
            warnings=data.get("_warnings", []),
            highlights=data.get("_highlights", [])
        )

        self.state.views[target_view] = view_data
        self.state.last_refresh = datetime.now()

        return view_data

    async def _collect_overview_data(self) -> Dict[str, Any]:
        """Collect overview data from all components."""
        data = {
            "components": {},
            "stats": {},
            "_warnings": [],
            "_highlights": []
        }

        # Mind status
        if self.mind:
            try:
                mind_ok = await self.mind.is_available()
                data["components"]["mind"] = "connected" if mind_ok else "offline"
                if not mind_ok:
                    data["_warnings"].append("Mind is offline - learning limited")
            except Exception:
                data["components"]["mind"] = "error"
        else:
            data["components"]["mind"] = "not configured"

        # Queue status
        queue_size = self.queue.size()
        data["components"]["queue"] = f"{queue_size} events"
        if queue_size > 100:
            data["_warnings"].append(f"Queue backlog: {queue_size} events")

        # Learner stats
        if self.learner:
            stats = self.learner.get_stats()
            data["stats"]["tool_rankings"] = stats.get("tool_rankings", [])[:5]
            data["stats"]["total_events"] = stats.get("total_events", 0)

        # Pattern count
        if self.evolver:
            pattern_count = len(self.evolver.patterns)
            data["stats"]["patterns"] = pattern_count
            if pattern_count == 0:
                data["_warnings"].append("No patterns evolved yet")

        # Meta learner
        if self.meta_learner:
            meta_stats = self.meta_learner.get_meta_stats()
            data["stats"]["meta"] = {
                "total_learnings": meta_stats.get("total_learnings", 0),
                "avg_confidence": meta_stats.get("avg_confidence", 0)
            }
            if meta_stats.get("avg_confidence", 0) > 0.8:
                data["_highlights"].append("High learning confidence")

        # Active experiments
        if self.experiment_manager:
            active = self.experiment_manager.get_active_experiments()
            data["stats"]["active_experiments"] = len(active)

        return data

    async def _collect_patterns_data(self) -> Dict[str, Any]:
        """Collect pattern data."""
        data = {
            "patterns": [],
            "by_type": {},
            "top_performers": [],
            "_warnings": [],
            "_highlights": []
        }

        if not self.evolver:
            data["_warnings"].append("Evolver not configured")
            return data

        patterns = list(self.evolver.patterns.values())
        data["total"] = len(patterns)

        # Group by type
        for pattern in patterns:
            ptype = pattern.pattern_type
            if ptype not in data["by_type"]:
                data["by_type"][ptype] = 0
            data["by_type"][ptype] += 1

        # Top performers by success rate
        sorted_patterns = sorted(
            [p for p in patterns if p.total_uses >= 5],
            key=lambda p: p.success_rate,
            reverse=True
        )

        data["top_performers"] = [
            {
                "id": p.pattern_id[:20],
                "type": p.pattern_type,
                "success_rate": f"{p.success_rate:.0%}",
                "uses": p.total_uses
            }
            for p in sorted_patterns[:10]
        ]

        # Highlights
        if sorted_patterns and sorted_patterns[0].success_rate > 0.9:
            data["_highlights"].append(
                f"Top pattern has {sorted_patterns[0].success_rate:.0%} success rate"
            )

        return data

    async def _collect_experiments_data(self) -> Dict[str, Any]:
        """Collect experiment data."""
        data = {
            "active": [],
            "completed": [],
            "stats": {},
            "_warnings": [],
            "_highlights": []
        }

        if not self.experiment_manager:
            data["_warnings"].append("Experiment manager not configured")
            return data

        # Active experiments
        active = self.experiment_manager.get_active_experiments()
        data["active"] = [
            {
                "id": e.experiment_id[:15],
                "name": e.name[:30],
                "samples": f"{e.control_samples + e.treatment_samples}/{e.min_samples * 2}",
                "status": e.status.value
            }
            for e in active
        ]

        # All experiments
        all_exps = list(self.experiment_manager.experiments.values())
        completed = [e for e in all_exps if e.status.value == "completed"]

        data["stats"]["total"] = len(all_exps)
        data["stats"]["active"] = len(active)
        data["stats"]["completed"] = len(completed)

        # Check for ready experiments
        for exp in active:
            if self.experiment_manager._has_sufficient_samples(exp):
                data["_highlights"].append(f"Experiment '{exp.name[:20]}' ready for analysis")

        return data

    async def _collect_learnings_data(self) -> Dict[str, Any]:
        """Collect learnings data from Mind."""
        data = {
            "recent": [],
            "by_category": {},
            "total": 0,
            "_warnings": [],
            "_highlights": []
        }

        if not self.mind:
            data["_warnings"].append("Mind not configured")
            return data

        try:
            learnings = await self.mind.retrieve("LEARNING", limit=50)
            data["total"] = len(learnings)

            # Recent learnings
            data["recent"] = [
                {
                    "content": l.get("content", "")[:60] + "...",
                    "salience": l.get("salience", 0),
                    "temporal_level": l.get("temporal_level", 0)
                }
                for l in learnings[:10]
            ]

            # Categorize
            for learning in learnings:
                content = learning.get("content", "")
                if "TOOL_EFFECTIVENESS" in content:
                    cat = "tool_effectiveness"
                elif "ERROR_PATTERN" in content:
                    cat = "error_pattern"
                elif "SEQUENCE" in content:
                    cat = "sequence"
                else:
                    cat = "other"

                if cat not in data["by_category"]:
                    data["by_category"][cat] = 0
                data["by_category"][cat] += 1

            if data["total"] > 0:
                data["_highlights"].append(f"{data['total']} learnings in Mind")

        except Exception as e:
            data["_warnings"].append(f"Error fetching learnings: {str(e)[:30]}")

        return data

    async def _collect_queue_data(self) -> Dict[str, Any]:
        """Collect queue health data."""
        data = {
            "size": 0,
            "oldest_event": None,
            "event_types": {},
            "throughput": {},
            "_warnings": [],
            "_highlights": []
        }

        data["size"] = self.queue.size()

        # Peek at events without consuming
        events = self.queue.peek(min(100, data["size"]))

        if events:
            # Oldest event age
            oldest = min(e.timestamp for e in events)
            age_seconds = datetime.now().timestamp() - oldest
            data["oldest_event"] = {
                "age_seconds": age_seconds,
                "age_human": self._humanize_seconds(age_seconds)
            }

            if age_seconds > 3600:
                data["_warnings"].append("Events older than 1 hour in queue")

            # Event types
            for event in events:
                etype = event.event_type.value
                if etype not in data["event_types"]:
                    data["event_types"][etype] = 0
                data["event_types"][etype] += 1

        if data["size"] == 0:
            data["_highlights"].append("Queue is empty (all caught up)")

        return data

    async def _collect_session_data(self) -> Dict[str, Any]:
        """Collect current session data."""
        data = {
            "session_id": None,
            "tools_used": [],
            "suggestions_shown": 0,
            "warnings_issued": 0,
            "_warnings": [],
            "_highlights": []
        }

        if self.suggester:
            ctx = self.suggester.context
            if ctx:
                data["session_id"] = ctx.session_id
                data["tools_used"] = list(ctx.recent_tools)[-10:]
                data["suggestions_shown"] = len(self.suggester._shown_suggestions)

        return data

    def _humanize_seconds(self, seconds: float) -> str:
        """Convert seconds to human-readable string."""
        if seconds < 60:
            return f"{int(seconds)}s"
        elif seconds < 3600:
            return f"{int(seconds / 60)}m"
        elif seconds < 86400:
            return f"{int(seconds / 3600)}h"
        else:
            return f"{int(seconds / 86400)}d"

    def render(self, view: Optional[DashboardView] = None) -> str:
        """
        Render a view to terminal string.

        Args:
            view: View to render (current if None)

        Returns:
            Formatted terminal string
        """
        target_view = view or self.state.current_view
        view_data = self.state.views.get(target_view)

        if not view_data:
            return self._render_empty(target_view)

        renderer = self._view_renderers.get(target_view, self._render_generic)
        return renderer(view_data)

    def _render_empty(self, view: DashboardView) -> str:
        """Render empty view message."""
        lines = [
            self._box_top(f" {view.value.upper()} "),
            self._box_line(""),
            self._box_line("  No data available. Run refresh() first."),
            self._box_line(""),
            self._box_bottom()
        ]
        return "\n".join(lines)

    def _render_overview(self, data: ViewData) -> str:
        """Render overview view."""
        lines = [
            self._box_top(" SPARK OVERVIEW "),
            self._box_line(""),
        ]

        # Components status
        lines.append(self._box_line("  COMPONENTS"))
        lines.append(self._box_line("  " + "-" * 40))

        for comp, status in data.content.get("components", {}).items():
            status_str = f"[OK]" if status in ["connected", "0 events"] or "events" in str(status) else "[--]"
            lines.append(self._box_line(f"  {comp:20} {status_str} {status}"))

        lines.append(self._box_line(""))

        # Stats
        stats = data.content.get("stats", {})
        if stats:
            lines.append(self._box_line("  STATISTICS"))
            lines.append(self._box_line("  " + "-" * 40))

            if "patterns" in stats:
                lines.append(self._box_line(f"  Patterns evolved:    {stats['patterns']}"))
            if "active_experiments" in stats:
                lines.append(self._box_line(f"  Active experiments:  {stats['active_experiments']}"))
            if "meta" in stats:
                meta = stats["meta"]
                lines.append(self._box_line(f"  Total learnings:     {meta.get('total_learnings', 0)}"))
                lines.append(self._box_line(f"  Avg confidence:      {meta.get('avg_confidence', 0):.0%}"))

            # Top tools
            if stats.get("tool_rankings"):
                lines.append(self._box_line(""))
                lines.append(self._box_line("  TOP TOOLS"))
                lines.append(self._box_line("  " + "-" * 40))
                for tool, score in stats["tool_rankings"][:5]:
                    bar = "█" * int(score * 20)
                    lines.append(self._box_line(f"  {tool:15} {bar} {score:.2f}"))

        # Warnings and highlights
        lines.extend(self._render_alerts(data))

        lines.append(self._box_line(""))
        lines.append(self._box_line(f"  Updated: {data.updated_at.strftime('%H:%M:%S')}"))
        lines.append(self._box_bottom())

        return "\n".join(lines)

    def _render_patterns(self, data: ViewData) -> str:
        """Render patterns view."""
        lines = [
            self._box_top(" PATTERNS "),
            self._box_line(""),
        ]

        content = data.content
        lines.append(self._box_line(f"  Total patterns: {content.get('total', 0)}"))
        lines.append(self._box_line(""))

        # By type
        by_type = content.get("by_type", {})
        if by_type:
            lines.append(self._box_line("  BY TYPE"))
            lines.append(self._box_line("  " + "-" * 40))
            for ptype, count in sorted(by_type.items(), key=lambda x: -x[1]):
                lines.append(self._box_line(f"  {ptype:25} {count:5}"))
            lines.append(self._box_line(""))

        # Top performers
        top = content.get("top_performers", [])
        if top:
            lines.append(self._box_line("  TOP PERFORMERS (5+ uses)"))
            lines.append(self._box_line("  " + "-" * 40))
            for p in top[:10]:
                lines.append(self._box_line(
                    f"  {p['id']:20} {p['success_rate']:>6} ({p['uses']} uses)"
                ))

        lines.extend(self._render_alerts(data))
        lines.append(self._box_bottom())

        return "\n".join(lines)

    def _render_experiments(self, data: ViewData) -> str:
        """Render experiments view."""
        lines = [
            self._box_top(" EXPERIMENTS "),
            self._box_line(""),
        ]

        content = data.content
        stats = content.get("stats", {})

        lines.append(self._box_line(f"  Total: {stats.get('total', 0)}  Active: {stats.get('active', 0)}  Completed: {stats.get('completed', 0)}"))
        lines.append(self._box_line(""))

        # Active experiments
        active = content.get("active", [])
        if active:
            lines.append(self._box_line("  ACTIVE EXPERIMENTS"))
            lines.append(self._box_line("  " + "-" * 50))
            for exp in active:
                lines.append(self._box_line(
                    f"  {exp['name']:30} {exp['samples']:>10} {exp['status']}"
                ))
        else:
            lines.append(self._box_line("  No active experiments"))

        lines.extend(self._render_alerts(data))
        lines.append(self._box_bottom())

        return "\n".join(lines)

    def _render_learnings(self, data: ViewData) -> str:
        """Render learnings view."""
        lines = [
            self._box_top(" LEARNINGS "),
            self._box_line(""),
        ]

        content = data.content
        lines.append(self._box_line(f"  Total in Mind: {content.get('total', 0)}"))
        lines.append(self._box_line(""))

        # By category
        by_cat = content.get("by_category", {})
        if by_cat:
            lines.append(self._box_line("  BY CATEGORY"))
            lines.append(self._box_line("  " + "-" * 40))
            for cat, count in sorted(by_cat.items(), key=lambda x: -x[1]):
                lines.append(self._box_line(f"  {cat:25} {count:5}"))
            lines.append(self._box_line(""))

        # Recent
        recent = content.get("recent", [])
        if recent:
            lines.append(self._box_line("  RECENT LEARNINGS"))
            lines.append(self._box_line("  " + "-" * 50))
            for l in recent[:5]:
                lines.append(self._box_line(f"  {l['content']}"))

        lines.extend(self._render_alerts(data))
        lines.append(self._box_bottom())

        return "\n".join(lines)

    def _render_queue(self, data: ViewData) -> str:
        """Render queue view."""
        lines = [
            self._box_top(" QUEUE "),
            self._box_line(""),
        ]

        content = data.content
        lines.append(self._box_line(f"  Queue size: {content.get('size', 0)} events"))

        oldest = content.get("oldest_event")
        if oldest:
            lines.append(self._box_line(f"  Oldest event: {oldest['age_human']} ago"))

        lines.append(self._box_line(""))

        # Event types
        event_types = content.get("event_types", {})
        if event_types:
            lines.append(self._box_line("  EVENT TYPES"))
            lines.append(self._box_line("  " + "-" * 40))
            for etype, count in sorted(event_types.items(), key=lambda x: -x[1]):
                lines.append(self._box_line(f"  {etype:25} {count:5}"))

        lines.extend(self._render_alerts(data))
        lines.append(self._box_bottom())

        return "\n".join(lines)

    def _render_session(self, data: ViewData) -> str:
        """Render session view."""
        lines = [
            self._box_top(" SESSION "),
            self._box_line(""),
        ]

        content = data.content
        sid = content.get("session_id")

        if sid:
            lines.append(self._box_line(f"  Session ID: {sid[:30]}..."))
        else:
            lines.append(self._box_line("  No active session"))

        lines.append(self._box_line(f"  Suggestions shown: {content.get('suggestions_shown', 0)}"))
        lines.append(self._box_line(f"  Warnings issued: {content.get('warnings_issued', 0)}"))

        tools = content.get("tools_used", [])
        if tools:
            lines.append(self._box_line(""))
            lines.append(self._box_line("  RECENT TOOLS"))
            lines.append(self._box_line("  " + "-" * 40))
            lines.append(self._box_line(f"  {' -> '.join(tools[-5:])}"))

        lines.extend(self._render_alerts(data))
        lines.append(self._box_bottom())

        return "\n".join(lines)

    def _render_generic(self, data: ViewData) -> str:
        """Render generic view."""
        lines = [
            self._box_top(f" {data.title} "),
            self._box_line(""),
            self._box_line(f"  Data: {len(data.content)} items"),
            self._box_line(""),
            self._box_bottom()
        ]
        return "\n".join(lines)

    def _render_alerts(self, data: ViewData) -> List[str]:
        """Render warnings and highlights."""
        lines = []

        if data.warnings:
            lines.append(self._box_line(""))
            lines.append(self._box_line("  WARNINGS"))
            for w in data.warnings:
                lines.append(self._box_line(f"  [!] {w}"))

        if data.highlights:
            lines.append(self._box_line(""))
            lines.append(self._box_line("  HIGHLIGHTS"))
            for h in data.highlights:
                lines.append(self._box_line(f"  [*] {h}"))

        return lines

    def _box_top(self, title: str = "") -> str:
        """Create box top line."""
        c = self.BOX_CHARS
        if title:
            padding = self.TERM_WIDTH - len(title) - 2
            left = padding // 2
            right = padding - left
            return f"{c['tl']}{c['h'] * left}{title}{c['h'] * right}{c['tr']}"
        return f"{c['tl']}{c['h'] * (self.TERM_WIDTH - 2)}{c['tr']}"

    def _box_bottom(self) -> str:
        """Create box bottom line."""
        c = self.BOX_CHARS
        return f"{c['bl']}{c['h'] * (self.TERM_WIDTH - 2)}{c['br']}"

    def _box_line(self, content: str) -> str:
        """Create box content line."""
        c = self.BOX_CHARS
        padding = self.TERM_WIDTH - len(content) - 2
        return f"{c['v']}{content}{' ' * max(0, padding)}{c['v']}"

    def set_view(self, view: DashboardView):
        """Set current view."""
        self.state.current_view = view

    def get_available_views(self) -> List[DashboardView]:
        """Get list of available views."""
        return list(DashboardView)

    async def start_live(self, interval: int = 30):
        """Start live refresh mode."""
        self.state.is_live = True
        self.state.refresh_interval = interval

        while self.state.is_live:
            await self.refresh()
            print("\033[2J\033[H")  # Clear screen
            print(self.render())
            await asyncio.sleep(interval)

    def stop_live(self):
        """Stop live refresh mode."""
        self.state.is_live = False

    def get_stats(self) -> Dict[str, Any]:
        """Get dashboard statistics."""
        return {
            "current_view": self.state.current_view.value,
            "views_cached": len(self.state.views),
            "last_refresh": self.state.last_refresh.isoformat() if self.state.last_refresh else None,
            "is_live": self.state.is_live,
            "refresh_interval": self.state.refresh_interval
        }
