"""
Unit tests for lib/learning_transfer.py
"""

import pytest
import time
from unittest.mock import Mock, AsyncMock

from lib.learning_transfer import (
    LearningTransfer, TransferableLearning, LearningScope
)
from lib.project_analyzer import ProjectFingerprint, ProjectType


class TestTransferableLearning:
    """Tests for TransferableLearning dataclass."""

    def test_creation(self):
        """Creates TransferableLearning with required fields."""
        learning = TransferableLearning(
            learning_id="test1",
            content="Use Grep for code search",
            original_project="/project",
            scope=LearningScope.UNIVERSAL
        )

        assert learning.learning_id == "test1"
        assert learning.scope == LearningScope.UNIVERSAL
        assert learning.transfer_confidence == 1.0

    def test_transfer_success_rate_no_transfers(self):
        """Returns 0.5 when no transfers."""
        learning = TransferableLearning(
            learning_id="test1",
            content="Test",
            original_project="/project",
            scope=LearningScope.UNIVERSAL
        )

        assert learning.transfer_success_rate == 0.5

    def test_transfer_success_rate_with_transfers(self):
        """Calculates success rate correctly."""
        learning = TransferableLearning(
            learning_id="test1",
            content="Test",
            original_project="/project",
            scope=LearningScope.UNIVERSAL,
            times_transferred=10,
            success_when_transferred=8
        )

        assert learning.transfer_success_rate == 0.8

    def test_is_high_quality_true(self):
        """Returns True for high quality learning."""
        learning = TransferableLearning(
            learning_id="test1",
            content="Test",
            original_project="/project",
            scope=LearningScope.UNIVERSAL,
            transfer_confidence=0.8,
            times_transferred=5,
            success_when_transferred=4
        )

        assert learning.is_high_quality is True

    def test_is_high_quality_low_confidence(self):
        """Returns False for low confidence."""
        learning = TransferableLearning(
            learning_id="test1",
            content="Test",
            original_project="/project",
            scope=LearningScope.UNIVERSAL,
            transfer_confidence=0.5
        )

        assert learning.is_high_quality is False

    def test_is_high_quality_low_success_rate(self):
        """Returns False for low transfer success rate."""
        learning = TransferableLearning(
            learning_id="test1",
            content="Test",
            original_project="/project",
            scope=LearningScope.UNIVERSAL,
            transfer_confidence=0.8,
            times_transferred=10,
            success_when_transferred=3  # 30% success
        )

        assert learning.is_high_quality is False

    def test_to_dict(self):
        """Converts to dictionary."""
        learning = TransferableLearning(
            learning_id="test1",
            content="Test content",
            original_project="/project",
            scope=LearningScope.LANGUAGE,
            applicable_languages=["python"]
        )

        data = learning.to_dict()

        assert data["learning_id"] == "test1"
        assert data["scope"] == "language"
        assert data["applicable_languages"] == ["python"]

    def test_from_dict(self):
        """Creates from dictionary."""
        data = {
            "learning_id": "test1",
            "content": "Test content",
            "original_project": "/project",
            "scope": "framework",
            "applicable_frameworks": ["FastAPI"],
            "transfer_confidence": 0.9
        }

        learning = TransferableLearning.from_dict(data)

        assert learning.learning_id == "test1"
        assert learning.scope == LearningScope.FRAMEWORK
        assert learning.applicable_frameworks == ["FastAPI"]
        assert learning.transfer_confidence == 0.9

    def test_roundtrip(self):
        """Round-trip through dict preserves data."""
        original = TransferableLearning(
            learning_id="test1",
            content="Test content",
            original_project="/project",
            scope=LearningScope.PROJECT_TYPE,
            applicable_project_types=["api_service"],
            transfer_confidence=0.85,
            times_transferred=5,
            success_when_transferred=4,
            metadata={"pattern_type": "tool_effectiveness"}
        )

        data = original.to_dict()
        restored = TransferableLearning.from_dict(data)

        assert restored.learning_id == original.learning_id
        assert restored.scope == original.scope
        assert restored.transfer_confidence == original.transfer_confidence
        assert restored.times_transferred == original.times_transferred


class TestLearningTransferClassifyScope:
    """Tests for classify_scope method."""

    def test_universal_tool_effectiveness(self):
        """Classifies tool effectiveness as universal."""
        transfer = LearningTransfer()

        scope = transfer.classify_scope(
            "TOOL_EFFECTIVENESS: Grep has 90% success rate",
            {"pattern_type": "tool_effectiveness"}
        )

        assert scope == LearningScope.UNIVERSAL

    def test_universal_error_avoidance(self):
        """Classifies error avoidance as universal."""
        transfer = LearningTransfer()

        scope = transfer.classify_scope(
            "ERROR_AVOIDANCE: Avoid timeout errors by using shorter commands",
            {"pattern_type": "error_avoidance"}
        )

        assert scope == LearningScope.UNIVERSAL

    def test_universal_performance(self):
        """Classifies performance patterns as universal."""
        transfer = LearningTransfer()

        scope = transfer.classify_scope(
            "Performance tip: Use parallel execution for faster results",
            {}
        )

        assert scope == LearningScope.UNIVERSAL

    def test_language_python(self):
        """Classifies Python-specific learning."""
        transfer = LearningTransfer()

        scope = transfer.classify_scope(
            "Use pytest fixtures for test setup in Python projects",
            {}
        )

        assert scope == LearningScope.LANGUAGE

    def test_language_javascript(self):
        """Classifies JavaScript-specific learning."""
        transfer = LearningTransfer()

        scope = transfer.classify_scope(
            "Run npm install before building node_modules",
            {}
        )

        assert scope == LearningScope.LANGUAGE

    def test_framework_fastapi(self):
        """Classifies FastAPI-specific learning."""
        transfer = LearningTransfer()

        scope = transfer.classify_scope(
            "Use Depends() for dependency injection in FastAPI routes",
            {}
        )

        assert scope == LearningScope.FRAMEWORK

    def test_framework_react(self):
        """Classifies React-specific learning."""
        transfer = LearningTransfer()

        scope = transfer.classify_scope(
            "Use useState and useEffect hooks in React components",
            {}
        )

        assert scope == LearningScope.FRAMEWORK

    def test_project_type_api(self):
        """Classifies API-specific learning."""
        transfer = LearningTransfer()

        scope = transfer.classify_scope(
            "Define REST endpoints in the routes handler",
            {}
        )

        assert scope == LearningScope.PROJECT_TYPE

    def test_defaults_to_project(self):
        """Defaults to project scope for unrecognized content."""
        transfer = LearningTransfer()

        scope = transfer.classify_scope(
            "This specific codebase has unusual file naming conventions",
            {}
        )

        assert scope == LearningScope.PROJECT


class TestLearningTransferAnnotate:
    """Tests for annotate_learning method."""

    def test_annotates_with_scope(self):
        """Annotates learning with correct scope."""
        transfer = LearningTransfer()
        fingerprint = ProjectFingerprint(
            project_path="/project",
            project_type=ProjectType.API_SERVICE,
            primary_language="python",
            frameworks=["FastAPI"]
        )

        learning = transfer.annotate_learning(
            learning_id="test1",
            content="TOOL_EFFECTIVENESS: Grep works well",
            source_fingerprint=fingerprint,
            metadata={"pattern_type": "tool_effectiveness"}
        )

        assert learning.scope == LearningScope.UNIVERSAL
        assert learning.learning_id == "test1"

    def test_stores_learning(self):
        """Stores learning in transferable_learnings."""
        transfer = LearningTransfer()
        fingerprint = ProjectFingerprint(
            project_path="/project",
            project_type=ProjectType.WEB_APP,
            primary_language="javascript"
        )

        learning = transfer.annotate_learning(
            learning_id="test1",
            content="Use npm for packages",
            source_fingerprint=fingerprint,
            metadata={}
        )

        assert "test1" in transfer.transferable_learnings
        assert transfer.transferable_learnings["test1"] == learning

    def test_sets_applicable_languages(self):
        """Sets applicable languages for language-scoped learning."""
        transfer = LearningTransfer()
        fingerprint = ProjectFingerprint(
            project_path="/project",
            project_type=ProjectType.API_SERVICE,
            primary_language="python"
        )

        learning = transfer.annotate_learning(
            learning_id="test1",
            content="Use pytest fixtures for Python tests",
            source_fingerprint=fingerprint,
            metadata={}
        )

        assert learning.scope == LearningScope.LANGUAGE
        assert "python" in learning.applicable_languages

    def test_sets_applicable_frameworks(self):
        """Sets applicable frameworks for framework-scoped learning."""
        transfer = LearningTransfer()
        fingerprint = ProjectFingerprint(
            project_path="/project",
            project_type=ProjectType.API_SERVICE,
            primary_language="python",
            frameworks=["FastAPI"]
        )

        learning = transfer.annotate_learning(
            learning_id="test1",
            content="Use Depends() for FastAPI dependency injection",
            source_fingerprint=fingerprint,
            metadata={}
        )

        assert learning.scope == LearningScope.FRAMEWORK
        assert "FastAPI" in learning.applicable_frameworks


class TestLearningTransferGetApplicable:
    """Tests for get_applicable_learnings method."""

    def test_returns_universal_learnings(self):
        """Returns universal learnings for any project."""
        transfer = LearningTransfer()
        transfer.transferable_learnings["test1"] = TransferableLearning(
            learning_id="test1",
            content="Universal tip",
            original_project="/other",
            scope=LearningScope.UNIVERSAL,
            transfer_confidence=0.9
        )

        target = ProjectFingerprint(
            project_path="/target",
            project_type=ProjectType.CLI_TOOL,
            primary_language="go"
        )

        applicable = transfer.get_applicable_learnings(target)

        assert len(applicable) == 1
        assert applicable[0].learning_id == "test1"

    def test_returns_matching_language_learnings(self):
        """Returns language-matching learnings."""
        transfer = LearningTransfer()
        transfer.transferable_learnings["test1"] = TransferableLearning(
            learning_id="test1",
            content="Python tip",
            original_project="/other",
            scope=LearningScope.LANGUAGE,
            applicable_languages=["python"],
            transfer_confidence=0.9
        )

        target = ProjectFingerprint(
            project_path="/target",
            project_type=ProjectType.API_SERVICE,
            primary_language="python"
        )

        applicable = transfer.get_applicable_learnings(target)

        assert len(applicable) == 1

    def test_excludes_non_matching_language(self):
        """Excludes learnings for different languages."""
        transfer = LearningTransfer()
        transfer.transferable_learnings["test1"] = TransferableLearning(
            learning_id="test1",
            content="Python tip",
            original_project="/other",
            scope=LearningScope.LANGUAGE,
            applicable_languages=["python"],
            transfer_confidence=0.9
        )

        target = ProjectFingerprint(
            project_path="/target",
            project_type=ProjectType.WEB_APP,
            primary_language="javascript"
        )

        applicable = transfer.get_applicable_learnings(target)

        assert len(applicable) == 0

    def test_excludes_low_confidence(self):
        """Excludes learnings below min_confidence."""
        transfer = LearningTransfer()
        transfer.transferable_learnings["test1"] = TransferableLearning(
            learning_id="test1",
            content="Universal tip",
            original_project="/other",
            scope=LearningScope.UNIVERSAL,
            transfer_confidence=0.3
        )

        target = ProjectFingerprint(
            project_path="/target",
            project_type=ProjectType.WEB_APP,
            primary_language="python"
        )

        applicable = transfer.get_applicable_learnings(target, min_confidence=0.5)

        assert len(applicable) == 0

    def test_excludes_project_scoped(self):
        """Excludes project-specific learnings."""
        transfer = LearningTransfer()
        transfer.transferable_learnings["test1"] = TransferableLearning(
            learning_id="test1",
            content="Project-specific tip",
            original_project="/other",
            scope=LearningScope.PROJECT,
            transfer_confidence=0.9
        )

        target = ProjectFingerprint(
            project_path="/target",
            project_type=ProjectType.WEB_APP,
            primary_language="python"
        )

        applicable = transfer.get_applicable_learnings(target)

        assert len(applicable) == 0

    def test_sorts_by_relevance(self):
        """Sorts learnings by relevance."""
        transfer = LearningTransfer()
        transfer.transferable_learnings["low"] = TransferableLearning(
            learning_id="low",
            content="Language tip",
            original_project="/other",
            scope=LearningScope.LANGUAGE,
            applicable_languages=["python"],
            transfer_confidence=0.6
        )
        transfer.transferable_learnings["high"] = TransferableLearning(
            learning_id="high",
            content="Universal tip",
            original_project="/other",
            scope=LearningScope.UNIVERSAL,
            transfer_confidence=0.9
        )

        target = ProjectFingerprint(
            project_path="/target",
            project_type=ProjectType.API_SERVICE,
            primary_language="python"
        )

        applicable = transfer.get_applicable_learnings(target)

        # Universal with high confidence should be first
        assert applicable[0].learning_id == "high"


class TestLearningTransferConfidence:
    """Tests for calculate_transfer_confidence method."""

    def test_high_similarity_high_confidence(self):
        """High similarity projects have high transfer confidence."""
        transfer = LearningTransfer()
        learning = TransferableLearning(
            learning_id="test1",
            content="Tip",
            original_project="/source",
            scope=LearningScope.UNIVERSAL,
            transfer_confidence=0.9
        )

        source = ProjectFingerprint(
            project_path="/source",
            project_type=ProjectType.API_SERVICE,
            primary_language="python",
            frameworks=["FastAPI"],
            file_count=100
        )
        target = ProjectFingerprint(
            project_path="/target",
            project_type=ProjectType.API_SERVICE,
            primary_language="python",
            frameworks=["FastAPI"],
            file_count=100
        )

        confidence = transfer.calculate_transfer_confidence(learning, source, target)

        # High similarity should result in reasonable confidence
        assert confidence > 0.65

    def test_low_similarity_reduces_confidence(self):
        """Low similarity projects have lower transfer confidence."""
        transfer = LearningTransfer()
        learning = TransferableLearning(
            learning_id="test1",
            content="Tip",
            original_project="/source",
            scope=LearningScope.UNIVERSAL,
            transfer_confidence=0.9
        )

        source = ProjectFingerprint(
            project_path="/source",
            project_type=ProjectType.API_SERVICE,
            primary_language="python",
            file_count=100
        )
        target = ProjectFingerprint(
            project_path="/target",
            project_type=ProjectType.CLI_TOOL,
            primary_language="go",
            file_count=10
        )

        confidence = transfer.calculate_transfer_confidence(learning, source, target)

        assert confidence < 0.7

    def test_successful_history_boosts_confidence(self):
        """Learnings with successful transfer history have higher confidence."""
        transfer = LearningTransfer()
        learning = TransferableLearning(
            learning_id="test1",
            content="Tip",
            original_project="/source",
            scope=LearningScope.UNIVERSAL,
            transfer_confidence=0.9,
            times_transferred=10,
            success_when_transferred=9
        )

        source = ProjectFingerprint(
            project_path="/source",
            project_type=ProjectType.WEB_APP,
            primary_language="python",
            file_count=100
        )
        target = ProjectFingerprint(
            project_path="/target",
            project_type=ProjectType.WEB_APP,
            primary_language="python",
            file_count=100
        )

        confidence = transfer.calculate_transfer_confidence(learning, source, target)

        # Successful history should result in reasonable confidence
        assert confidence > 0.65

    def test_respects_min_confidence(self):
        """Never returns below MIN_TRANSFER_CONFIDENCE."""
        transfer = LearningTransfer()
        learning = TransferableLearning(
            learning_id="test1",
            content="Tip",
            original_project="/source",
            scope=LearningScope.PROJECT,  # Lowest scope factor
            transfer_confidence=0.3,
            times_transferred=10,
            success_when_transferred=1  # Low success rate
        )

        source = ProjectFingerprint(
            project_path="/source",
            project_type=ProjectType.WEB_APP,
            primary_language="python"
        )
        target = ProjectFingerprint(
            project_path="/target",
            project_type=ProjectType.CLI_TOOL,
            primary_language="go"
        )

        confidence = transfer.calculate_transfer_confidence(learning, source, target)

        assert confidence >= transfer.MIN_TRANSFER_CONFIDENCE


class TestLearningTransferRecordOutcome:
    """Tests for record_transfer_outcome method."""

    def test_records_success(self):
        """Records successful transfer."""
        transfer = LearningTransfer()
        transfer.transferable_learnings["test1"] = TransferableLearning(
            learning_id="test1",
            content="Tip",
            original_project="/source",
            scope=LearningScope.UNIVERSAL,
            transfer_confidence=0.8
        )

        result = transfer.record_transfer_outcome("test1", True)

        assert result is True
        learning = transfer.transferable_learnings["test1"]
        assert learning.times_transferred == 1
        assert learning.success_when_transferred == 1
        assert learning.transfer_confidence > 0.8

    def test_records_failure(self):
        """Records failed transfer."""
        transfer = LearningTransfer()
        transfer.transferable_learnings["test1"] = TransferableLearning(
            learning_id="test1",
            content="Tip",
            original_project="/source",
            scope=LearningScope.UNIVERSAL,
            transfer_confidence=0.8
        )

        result = transfer.record_transfer_outcome("test1", False)

        assert result is True
        learning = transfer.transferable_learnings["test1"]
        assert learning.times_transferred == 1
        assert learning.success_when_transferred == 0
        assert learning.transfer_confidence < 0.8

    def test_returns_false_unknown_id(self):
        """Returns False for unknown learning ID."""
        transfer = LearningTransfer()

        result = transfer.record_transfer_outcome("nonexistent", True)

        assert result is False

    def test_adds_to_history(self):
        """Adds outcome to transfer history."""
        transfer = LearningTransfer()
        transfer.transferable_learnings["test1"] = TransferableLearning(
            learning_id="test1",
            content="Tip",
            original_project="/source",
            scope=LearningScope.UNIVERSAL
        )

        transfer.record_transfer_outcome("test1", True)

        assert len(transfer.transfer_history) == 1
        assert transfer.transfer_history[0]["learning_id"] == "test1"
        assert transfer.transfer_history[0]["was_successful"] is True

    def test_confidence_capped_at_one(self):
        """Confidence doesn't exceed 1.0."""
        transfer = LearningTransfer()
        transfer.transferable_learnings["test1"] = TransferableLearning(
            learning_id="test1",
            content="Tip",
            original_project="/source",
            scope=LearningScope.UNIVERSAL,
            transfer_confidence=0.98
        )

        # Multiple successes
        for _ in range(5):
            transfer.record_transfer_outcome("test1", True)

        learning = transfer.transferable_learnings["test1"]
        assert learning.transfer_confidence <= 1.0


class TestLearningTransferStats:
    """Tests for get_stats method."""

    def test_empty_stats(self):
        """Returns stats for empty transfer system."""
        transfer = LearningTransfer()

        stats = transfer.get_stats()

        assert stats["total_learnings"] == 0
        assert stats["total_transfers"] == 0
        assert stats["transfer_success_rate"] == 0.5

    def test_counts_by_scope(self):
        """Counts learnings by scope."""
        transfer = LearningTransfer()
        transfer.transferable_learnings["u1"] = TransferableLearning(
            learning_id="u1", content="", original_project="/p",
            scope=LearningScope.UNIVERSAL
        )
        transfer.transferable_learnings["u2"] = TransferableLearning(
            learning_id="u2", content="", original_project="/p",
            scope=LearningScope.UNIVERSAL
        )
        transfer.transferable_learnings["l1"] = TransferableLearning(
            learning_id="l1", content="", original_project="/p",
            scope=LearningScope.LANGUAGE
        )

        stats = transfer.get_stats()

        assert stats["total_learnings"] == 3
        assert stats["by_scope"]["universal"] == 2
        assert stats["by_scope"]["language"] == 1

    def test_calculates_transfer_success_rate(self):
        """Calculates overall transfer success rate."""
        transfer = LearningTransfer()
        transfer.transferable_learnings["t1"] = TransferableLearning(
            learning_id="t1", content="", original_project="/p",
            scope=LearningScope.UNIVERSAL,
            times_transferred=10,
            success_when_transferred=8
        )
        transfer.transferable_learnings["t2"] = TransferableLearning(
            learning_id="t2", content="", original_project="/p",
            scope=LearningScope.LANGUAGE,
            times_transferred=10,
            success_when_transferred=6
        )

        stats = transfer.get_stats()

        assert stats["total_transfers"] == 20
        assert stats["successful_transfers"] == 14
        assert stats["transfer_success_rate"] == 0.7

    def test_counts_high_quality(self):
        """Counts high quality learnings."""
        transfer = LearningTransfer()
        transfer.transferable_learnings["high"] = TransferableLearning(
            learning_id="high", content="", original_project="/p",
            scope=LearningScope.UNIVERSAL,
            transfer_confidence=0.9
        )
        transfer.transferable_learnings["low"] = TransferableLearning(
            learning_id="low", content="", original_project="/p",
            scope=LearningScope.UNIVERSAL,
            transfer_confidence=0.5
        )

        stats = transfer.get_stats()

        assert stats["high_quality_count"] == 1


class TestLearningTransferMindIntegration:
    """Tests for Mind integration."""

    @pytest.mark.asyncio
    async def test_sync_from_mind_unavailable(self):
        """Returns 0 when Mind unavailable."""
        mock_mind = Mock()
        mock_mind.is_available = AsyncMock(return_value=False)

        transfer = LearningTransfer(mind_client=mock_mind)
        count = await transfer.sync_learnings_from_mind()

        assert count == 0

    @pytest.mark.asyncio
    async def test_persist_to_mind_unavailable(self):
        """Returns 0 when Mind unavailable."""
        mock_mind = Mock()
        mock_mind.is_available = AsyncMock(return_value=False)

        transfer = LearningTransfer(mind_client=mock_mind)
        count = await transfer.persist_learnings_to_mind()

        assert count == 0

    @pytest.mark.asyncio
    async def test_persist_only_high_quality(self):
        """Only persists high quality learnings."""
        mock_mind = Mock()
        mock_mind.is_available = AsyncMock(return_value=True)
        mock_mind.store = AsyncMock(return_value="mem1")

        transfer = LearningTransfer(mind_client=mock_mind)
        transfer.transferable_learnings["high"] = TransferableLearning(
            learning_id="high", content="Good tip", original_project="/p",
            scope=LearningScope.UNIVERSAL,
            transfer_confidence=0.9
        )
        transfer.transferable_learnings["low"] = TransferableLearning(
            learning_id="low", content="Bad tip", original_project="/p",
            scope=LearningScope.UNIVERSAL,
            transfer_confidence=0.5
        )

        count = await transfer.persist_learnings_to_mind()

        assert count == 1
        assert mock_mind.store.call_count == 1
