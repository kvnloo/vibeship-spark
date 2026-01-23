"""
Unit tests for lib/spark_dashboard.py
"""

import pytest
from unittest.mock import MagicMock, AsyncMock
from datetime import datetime

from lib.spark_dashboard import (
    SparkDashboard, DashboardView, ViewData, DashboardState
)
from lib.queue import SparkQueue, SparkEvent, EventType


@pytest.fixture
def mock_mind_client():
    """Create a mock Mind client."""
    client = MagicMock()
    client.is_available = AsyncMock(return_value=True)
    client.retrieve = AsyncMock(return_value=[])
    return client


@pytest.fixture
def mock_evolver():
    """Create a mock evolver."""
    evolver = MagicMock()
    evolver.patterns = {}
    return evolver


@pytest.fixture
def mock_learner():
    """Create a mock learner."""
    learner = MagicMock()
    learner.get_stats.return_value = {
        "tool_rankings": [("Grep", 0.9), ("Read", 0.8)],
        "total_events": 100
    }
    return learner


@pytest.fixture
def mock_meta_learner():
    """Create a mock meta learner."""
    ml = MagicMock()
    ml.get_meta_stats.return_value = {
        "total_learnings": 50,
        "avg_confidence": 0.75
    }
    return ml


@pytest.fixture
def dashboard(mock_mind_client, mock_evolver, mock_learner, mock_meta_learner):
    """Create a dashboard with mocks."""
    return SparkDashboard(
        mind_client=mock_mind_client,
        evolver=mock_evolver,
        learner=mock_learner,
        meta_learner=mock_meta_learner
    )


class TestSparkDashboardInit:
    """Tests for SparkDashboard initialization."""

    def test_init_default(self):
        """Initializes with defaults."""
        dashboard = SparkDashboard()

        assert dashboard.state.current_view == DashboardView.OVERVIEW
        assert dashboard.state.refresh_interval == 30
        assert dashboard.state.is_live is False

    def test_init_with_dependencies(self, mock_mind_client, mock_evolver):
        """Accepts injected dependencies."""
        dashboard = SparkDashboard(
            mind_client=mock_mind_client,
            evolver=mock_evolver
        )

        assert dashboard.mind == mock_mind_client
        assert dashboard.evolver == mock_evolver


class TestDashboardViews:
    """Tests for dashboard views."""

    def test_get_available_views(self, dashboard):
        """Returns all available views."""
        views = dashboard.get_available_views()

        assert DashboardView.OVERVIEW in views
        assert DashboardView.PATTERNS in views
        assert DashboardView.EXPERIMENTS in views
        assert DashboardView.LEARNINGS in views
        assert DashboardView.QUEUE in views
        assert DashboardView.SESSION in views

    def test_set_view(self, dashboard):
        """Sets current view."""
        dashboard.set_view(DashboardView.PATTERNS)

        assert dashboard.state.current_view == DashboardView.PATTERNS


class TestRefresh:
    """Tests for refresh method."""

    @pytest.mark.asyncio
    async def test_refresh_overview(self, dashboard):
        """Refreshes overview data."""
        view_data = await dashboard.refresh(DashboardView.OVERVIEW)

        assert view_data.title == "OVERVIEW"
        assert view_data.updated_at is not None
        assert "components" in view_data.content

    @pytest.mark.asyncio
    async def test_refresh_patterns(self, dashboard):
        """Refreshes patterns data."""
        view_data = await dashboard.refresh(DashboardView.PATTERNS)

        assert view_data.title == "PATTERNS"
        assert "total" in view_data.content

    @pytest.mark.asyncio
    async def test_refresh_queue(self, dashboard):
        """Refreshes queue data."""
        view_data = await dashboard.refresh(DashboardView.QUEUE)

        assert view_data.title == "QUEUE"
        assert "size" in view_data.content

    @pytest.mark.asyncio
    async def test_refresh_updates_last_refresh(self, dashboard):
        """Refresh updates last_refresh timestamp."""
        await dashboard.refresh()

        assert dashboard.state.last_refresh is not None

    @pytest.mark.asyncio
    async def test_refresh_caches_view_data(self, dashboard):
        """Refresh caches view data."""
        await dashboard.refresh(DashboardView.OVERVIEW)

        assert DashboardView.OVERVIEW in dashboard.state.views


class TestCollectOverviewData:
    """Tests for overview data collection."""

    @pytest.mark.asyncio
    async def test_includes_mind_status(self, dashboard, mock_mind_client):
        """Overview includes Mind status."""
        data = await dashboard._collect_overview_data()

        assert "mind" in data["components"]
        assert data["components"]["mind"] == "connected"

    @pytest.mark.asyncio
    async def test_includes_queue_status(self, dashboard):
        """Overview includes queue status."""
        data = await dashboard._collect_overview_data()

        assert "queue" in data["components"]

    @pytest.mark.asyncio
    async def test_includes_tool_rankings(self, dashboard):
        """Overview includes tool rankings."""
        data = await dashboard._collect_overview_data()

        assert "tool_rankings" in data["stats"]

    @pytest.mark.asyncio
    async def test_warns_on_offline_mind(self, mock_evolver, mock_learner):
        """Warns when Mind is offline."""
        offline_mind = MagicMock()
        offline_mind.is_available = AsyncMock(return_value=False)

        dashboard = SparkDashboard(
            mind_client=offline_mind,
            evolver=mock_evolver,
            learner=mock_learner
        )

        data = await dashboard._collect_overview_data()

        assert "Mind is offline" in " ".join(data["_warnings"])


class TestCollectPatternsData:
    """Tests for patterns data collection."""

    @pytest.mark.asyncio
    async def test_counts_patterns(self, dashboard, mock_evolver):
        """Counts total patterns."""
        from lib.prompt_evolver import PromptPattern

        mock_evolver.patterns["p1"] = PromptPattern(
            pattern_id="p1",
            pattern_type="tool_sequence",
            description="Test",
            trigger_conditions={},
            approach="Test approach",
            total_uses=10,
            success_count=8,
            failure_count=2
        )

        data = await dashboard._collect_patterns_data()

        assert data["total"] == 1

    @pytest.mark.asyncio
    async def test_groups_by_type(self, dashboard, mock_evolver):
        """Groups patterns by type."""
        from lib.prompt_evolver import PromptPattern

        mock_evolver.patterns["p1"] = PromptPattern(
            pattern_id="p1",
            pattern_type="tool_sequence",
            description="Test",
            trigger_conditions={},
            approach="Test",
            total_uses=10,
            success_count=8,
            failure_count=2
        )

        data = await dashboard._collect_patterns_data()

        assert "tool_sequence" in data["by_type"]


class TestCollectQueueData:
    """Tests for queue data collection."""

    @pytest.mark.asyncio
    async def test_reports_queue_size(self, dashboard):
        """Reports queue size."""
        data = await dashboard._collect_queue_data()

        assert "size" in data
        assert isinstance(data["size"], int)

    @pytest.mark.asyncio
    async def test_highlights_empty_queue(self, dashboard):
        """Highlights when queue is empty."""
        data = await dashboard._collect_queue_data()

        if data["size"] == 0:
            assert any("empty" in h.lower() for h in data["_highlights"])


class TestRender:
    """Tests for rendering views."""

    @pytest.mark.asyncio
    async def test_render_overview(self, dashboard):
        """Renders overview view."""
        await dashboard.refresh(DashboardView.OVERVIEW)
        output = dashboard.render(DashboardView.OVERVIEW)

        assert "SPARK OVERVIEW" in output
        assert "COMPONENTS" in output

    @pytest.mark.asyncio
    async def test_render_patterns(self, dashboard):
        """Renders patterns view."""
        await dashboard.refresh(DashboardView.PATTERNS)
        output = dashboard.render(DashboardView.PATTERNS)

        assert "PATTERNS" in output

    @pytest.mark.asyncio
    async def test_render_queue(self, dashboard):
        """Renders queue view."""
        await dashboard.refresh(DashboardView.QUEUE)
        output = dashboard.render(DashboardView.QUEUE)

        assert "QUEUE" in output

    def test_render_empty_view(self, dashboard):
        """Renders empty view message."""
        output = dashboard.render(DashboardView.EXPERIMENTS)

        assert "No data available" in output

    @pytest.mark.asyncio
    async def test_render_includes_timestamp(self, dashboard):
        """Render includes update timestamp."""
        await dashboard.refresh(DashboardView.OVERVIEW)
        output = dashboard.render(DashboardView.OVERVIEW)

        assert "Updated:" in output


class TestBoxRendering:
    """Tests for terminal box rendering."""

    def test_box_top(self, dashboard):
        """Creates box top line."""
        top = dashboard._box_top(" TEST ")

        assert top.startswith("+")
        assert top.endswith("+")
        assert "TEST" in top

    def test_box_bottom(self, dashboard):
        """Creates box bottom line."""
        bottom = dashboard._box_bottom()

        assert bottom.startswith("+")
        assert bottom.endswith("+")

    def test_box_line(self, dashboard):
        """Creates box content line."""
        line = dashboard._box_line("Test content")

        assert line.startswith("|")
        assert line.endswith("|")
        assert "Test content" in line


class TestHumanizeSeconds:
    """Tests for time humanization."""

    def test_seconds(self, dashboard):
        """Humanizes seconds."""
        assert dashboard._humanize_seconds(30) == "30s"

    def test_minutes(self, dashboard):
        """Humanizes minutes."""
        assert dashboard._humanize_seconds(120) == "2m"

    def test_hours(self, dashboard):
        """Humanizes hours."""
        assert dashboard._humanize_seconds(7200) == "2h"

    def test_days(self, dashboard):
        """Humanizes days."""
        assert dashboard._humanize_seconds(172800) == "2d"


class TestLiveMode:
    """Tests for live refresh mode."""

    def test_stop_live(self, dashboard):
        """Stops live mode."""
        dashboard.state.is_live = True
        dashboard.stop_live()

        assert dashboard.state.is_live is False


class TestGetStats:
    """Tests for get_stats method."""

    def test_returns_stats(self, dashboard):
        """Returns dashboard statistics."""
        stats = dashboard.get_stats()

        assert "current_view" in stats
        assert "views_cached" in stats
        assert "is_live" in stats
        assert "refresh_interval" in stats


class TestViewDataDataclass:
    """Tests for ViewData dataclass."""

    def test_creation(self):
        """ViewData creates with required fields."""
        view_data = ViewData(
            title="Test",
            updated_at=datetime.now(),
            content={"key": "value"}
        )

        assert view_data.title == "Test"
        assert len(view_data.warnings) == 0
        assert len(view_data.highlights) == 0


class TestDashboardStateDataclass:
    """Tests for DashboardState dataclass."""

    def test_creation(self):
        """DashboardState creates with required fields."""
        state = DashboardState(
            current_view=DashboardView.OVERVIEW,
            views={},
            refresh_interval=30
        )

        assert state.current_view == DashboardView.OVERVIEW
        assert state.is_live is False
        assert state.last_refresh is None
