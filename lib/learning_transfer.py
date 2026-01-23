"""
Spark Learning Transfer: Share learnings across similar projects.

This component:
1. Classifies learning scope based on content
2. Matches learnings to target projects
3. Adjusts confidence for transferred learnings
4. Tracks transfer success rates

Enables cross-project intelligence sharing.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from enum import Enum
import time
import re

from .project_analyzer import ProjectFingerprint, ProjectType
from .mind_client import MindClient


class LearningScope(Enum):
    """Scope of learning applicability."""
    UNIVERSAL = "universal"         # Applies everywhere
    LANGUAGE = "language"           # Specific to a language
    FRAMEWORK = "framework"         # Specific to a framework
    PROJECT_TYPE = "project_type"   # Specific to project type
    PROJECT = "project"             # Only this project


@dataclass
class TransferableLearning:
    """A learning annotated with transfer scope."""
    learning_id: str
    content: str
    original_project: str
    scope: LearningScope
    applicable_languages: List[str] = field(default_factory=list)
    applicable_frameworks: List[str] = field(default_factory=list)
    applicable_project_types: List[str] = field(default_factory=list)
    transfer_confidence: float = 1.0  # Reduced when transferred
    times_transferred: int = 0
    success_when_transferred: int = 0
    created_at: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def transfer_success_rate(self) -> float:
        """Success rate when transferred to other projects."""
        if self.times_transferred == 0:
            return 0.5  # Default neutral
        return self.success_when_transferred / self.times_transferred

    @property
    def is_high_quality(self) -> bool:
        """Check if this learning has proven valuable."""
        return (
            self.transfer_confidence >= 0.7 and
            (self.times_transferred == 0 or self.transfer_success_rate >= 0.6)
        )

    def to_dict(self) -> Dict:
        """Convert to dictionary for storage."""
        return {
            "learning_id": self.learning_id,
            "content": self.content,
            "original_project": self.original_project,
            "scope": self.scope.value,
            "applicable_languages": self.applicable_languages,
            "applicable_frameworks": self.applicable_frameworks,
            "applicable_project_types": self.applicable_project_types,
            "transfer_confidence": self.transfer_confidence,
            "times_transferred": self.times_transferred,
            "success_when_transferred": self.success_when_transferred,
            "created_at": self.created_at,
            "metadata": self.metadata
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'TransferableLearning':
        """Create from dictionary."""
        return cls(
            learning_id=data.get("learning_id", ""),
            content=data.get("content", ""),
            original_project=data.get("original_project", ""),
            scope=LearningScope(data.get("scope", "project")),
            applicable_languages=data.get("applicable_languages", []),
            applicable_frameworks=data.get("applicable_frameworks", []),
            applicable_project_types=data.get("applicable_project_types", []),
            transfer_confidence=data.get("transfer_confidence", 1.0),
            times_transferred=data.get("times_transferred", 0),
            success_when_transferred=data.get("success_when_transferred", 0),
            created_at=data.get("created_at", time.time()),
            metadata=data.get("metadata", {})
        )


class LearningTransfer:
    """
    Manages transfer of learnings between projects.

    Responsibilities:
    1. Classify learning scope based on content
    2. Match learnings to target projects
    3. Adjust confidence for transferred learnings
    4. Track transfer success rates
    """

    # Indicators for scope classification
    UNIVERSAL_INDICATORS = [
        "tool_effectiveness",
        "error_avoidance",
        "performance",
        "timeout",
        "memory",
        "parallel",
        "sequence",
        "retry",
    ]

    LANGUAGE_INDICATORS = {
        "python": [
            "pytest", "pip", "virtualenv", "__init__", "pyproject",
            "requirements.txt", "import", "def ", "class ", "async def",
            "python", ".py"
        ],
        "javascript": [
            "npm", "yarn", "node_modules", "package.json", "require(",
            "import ", "export ", "const ", "let ", "function", ".js", ".jsx"
        ],
        "typescript": [
            "tsc", "tsconfig", ".ts", ".tsx", "interface ", "type ",
            ": string", ": number", ": boolean"
        ],
        "go": [
            "go mod", "go.sum", "package main", "func ", "go run", "go build",
            ".go"
        ],
        "rust": [
            "cargo", "Cargo.toml", "fn ", "let mut", "impl ", ".rs",
            "rustc", "crate"
        ],
    }

    FRAMEWORK_INDICATORS = {
        "FastAPI": ["fastapi", "uvicorn", "@app.get", "@app.post", "Depends("],
        "Django": ["django", "manage.py", "urls.py", "views.py", "models.py"],
        "Flask": ["flask", "@app.route", "render_template"],
        "React": ["react", "useState", "useEffect", "jsx", "component"],
        "Vue": ["vue", "v-if", "v-for", "computed", "ref("],
        "Express": ["express", "app.get", "app.post", "middleware", "router"],
        "Next.js": ["next", "getServerSideProps", "getStaticProps", "pages/"],
    }

    PROJECT_TYPE_INDICATORS = {
        ProjectType.WEB_APP: ["frontend", "ui", "component", "page", "render"],
        ProjectType.API_SERVICE: ["endpoint", "route", "handler", "api", "rest"],
        ProjectType.CLI_TOOL: ["command", "cli", "argument", "flag", "stdin"],
        ProjectType.LIBRARY: ["module", "export", "import", "package", "publish"],
        ProjectType.ML_PROJECT: ["model", "train", "predict", "dataset", "epoch"],
        ProjectType.DATA_PIPELINE: ["etl", "pipeline", "transform", "extract", "load"],
    }

    # Confidence adjustments
    TRANSFER_CONFIDENCE_DECAY = 0.1  # Reduce confidence when transferring
    MIN_TRANSFER_CONFIDENCE = 0.3    # Don't transfer below this
    SUCCESS_BOOST = 0.05             # Boost when transfer succeeds
    FAILURE_PENALTY = 0.1            # Penalty when transfer fails

    def __init__(self, mind_client: Optional[MindClient] = None):
        self.mind = mind_client
        self.transferable_learnings: Dict[str, TransferableLearning] = {}
        self.transfer_history: List[Dict] = []

    def classify_scope(self, learning_content: str, metadata: Dict) -> LearningScope:
        """
        Determine the scope of a learning.

        Args:
            learning_content: The learning text
            metadata: Associated metadata (pattern_type, tool, etc.)

        Returns:
            Appropriate LearningScope
        """
        content_lower = learning_content.lower()
        pattern_type = metadata.get("pattern_type", "").lower()

        # Check for universal patterns first
        for indicator in self.UNIVERSAL_INDICATORS:
            if indicator in content_lower or indicator in pattern_type:
                return LearningScope.UNIVERSAL

        # Check for framework-specific
        for framework, indicators in self.FRAMEWORK_INDICATORS.items():
            if any(ind.lower() in content_lower for ind in indicators):
                return LearningScope.FRAMEWORK

        # Check for language-specific
        for language, indicators in self.LANGUAGE_INDICATORS.items():
            if any(ind.lower() in content_lower for ind in indicators):
                return LearningScope.LANGUAGE

        # Check for project-type specific
        for ptype, indicators in self.PROJECT_TYPE_INDICATORS.items():
            if any(ind in content_lower for ind in indicators):
                return LearningScope.PROJECT_TYPE

        # Default to project-specific
        return LearningScope.PROJECT

    def annotate_learning(
        self,
        learning_id: str,
        content: str,
        source_fingerprint: ProjectFingerprint,
        metadata: Dict
    ) -> TransferableLearning:
        """
        Create a TransferableLearning with proper scope annotation.
        """
        scope = self.classify_scope(content, metadata)

        # Determine applicable contexts based on scope
        applicable_languages = []
        applicable_frameworks = []
        applicable_project_types = []

        if scope == LearningScope.LANGUAGE:
            # Find which language this applies to
            content_lower = content.lower()
            for lang, indicators in self.LANGUAGE_INDICATORS.items():
                if any(ind.lower() in content_lower for ind in indicators):
                    applicable_languages.append(lang)
            if not applicable_languages and source_fingerprint.primary_language:
                applicable_languages = [source_fingerprint.primary_language]

        elif scope == LearningScope.FRAMEWORK:
            # Find which framework this applies to
            content_lower = content.lower()
            for framework, indicators in self.FRAMEWORK_INDICATORS.items():
                if any(ind.lower() in content_lower for ind in indicators):
                    applicable_frameworks.append(framework)
            if not applicable_frameworks:
                applicable_frameworks = source_fingerprint.frameworks[:1]

        elif scope == LearningScope.PROJECT_TYPE:
            # Find which project type this applies to
            content_lower = content.lower()
            for ptype, indicators in self.PROJECT_TYPE_INDICATORS.items():
                if any(ind in content_lower for ind in indicators):
                    applicable_project_types.append(ptype.value)
            if not applicable_project_types:
                applicable_project_types = [source_fingerprint.project_type.value]

        learning = TransferableLearning(
            learning_id=learning_id,
            content=content,
            original_project=source_fingerprint.project_path,
            scope=scope,
            applicable_languages=applicable_languages,
            applicable_frameworks=applicable_frameworks,
            applicable_project_types=applicable_project_types,
            transfer_confidence=metadata.get("confidence", 1.0),
            metadata=metadata
        )

        self.transferable_learnings[learning_id] = learning
        return learning

    def get_applicable_learnings(
        self,
        target_fingerprint: ProjectFingerprint,
        min_confidence: float = 0.5
    ) -> List[TransferableLearning]:
        """
        Get learnings applicable to target project.

        Args:
            target_fingerprint: Target project fingerprint
            min_confidence: Minimum transfer confidence

        Returns:
            List of applicable learnings, sorted by relevance
        """
        applicable = []

        for learning in self.transferable_learnings.values():
            if learning.transfer_confidence < min_confidence:
                continue

            # Check scope applicability
            if learning.scope == LearningScope.UNIVERSAL:
                applicable.append((learning, 1.0))

            elif learning.scope == LearningScope.LANGUAGE:
                if target_fingerprint.primary_language in learning.applicable_languages:
                    applicable.append((learning, 0.9))
                elif any(lang in learning.applicable_languages for lang in target_fingerprint.languages):
                    applicable.append((learning, 0.7))

            elif learning.scope == LearningScope.FRAMEWORK:
                target_frameworks_lower = [f.lower() for f in target_fingerprint.frameworks]
                learning_frameworks_lower = [f.lower() for f in learning.applicable_frameworks]
                if any(f in target_frameworks_lower for f in learning_frameworks_lower):
                    applicable.append((learning, 0.85))

            elif learning.scope == LearningScope.PROJECT_TYPE:
                if target_fingerprint.project_type.value in learning.applicable_project_types:
                    applicable.append((learning, 0.8))

            # Project-specific learnings don't transfer
            # (scope == PROJECT is not included)

        # Sort by relevance score * confidence
        applicable.sort(key=lambda x: x[1] * x[0].transfer_confidence, reverse=True)
        return [learning for learning, _ in applicable]

    def calculate_transfer_confidence(
        self,
        learning: TransferableLearning,
        source: ProjectFingerprint,
        target: ProjectFingerprint
    ) -> float:
        """
        Calculate confidence when transferring a learning.

        Factors:
        - Original confidence
        - Project similarity
        - Historical transfer success rate
        - Scope match quality
        """
        base_confidence = learning.transfer_confidence

        # Apply similarity factor
        similarity = source.similarity(target)
        similarity_factor = 0.5 + (similarity * 0.5)  # Range: 0.5 to 1.0

        # Apply historical success factor
        if learning.times_transferred > 0:
            success_factor = 0.7 + (learning.transfer_success_rate * 0.3)
        else:
            success_factor = 0.85  # Neutral for untested transfers

        # Apply scope decay
        scope_factor = {
            LearningScope.UNIVERSAL: 1.0,
            LearningScope.LANGUAGE: 0.9,
            LearningScope.FRAMEWORK: 0.85,
            LearningScope.PROJECT_TYPE: 0.8,
            LearningScope.PROJECT: 0.5,
        }.get(learning.scope, 0.5)

        # Calculate final confidence
        confidence = base_confidence * similarity_factor * success_factor * scope_factor

        return max(confidence, self.MIN_TRANSFER_CONFIDENCE)

    def record_transfer_outcome(
        self,
        learning_id: str,
        was_successful: bool
    ) -> bool:
        """
        Record whether a transferred learning was successful.

        Args:
            learning_id: ID of the learning
            was_successful: Whether the transfer was successful

        Returns:
            True if recorded, False if learning not found
        """
        if learning_id not in self.transferable_learnings:
            return False

        learning = self.transferable_learnings[learning_id]
        learning.times_transferred += 1

        if was_successful:
            learning.success_when_transferred += 1
            learning.transfer_confidence = min(
                1.0,
                learning.transfer_confidence + self.SUCCESS_BOOST
            )
        else:
            learning.transfer_confidence = max(
                self.MIN_TRANSFER_CONFIDENCE,
                learning.transfer_confidence - self.FAILURE_PENALTY
            )

        # Record in history
        self.transfer_history.append({
            "learning_id": learning_id,
            "was_successful": was_successful,
            "timestamp": time.time(),
            "new_confidence": learning.transfer_confidence
        })

        return True

    async def sync_learnings_from_mind(self) -> int:
        """
        Load transferable learnings from Mind.

        Returns:
            Number of learnings loaded
        """
        if not self.mind or not await self.mind.is_available():
            return 0

        # Use retrieve_all for paginated retrieval (Mind Lite caps at 100)
        memories = await self.mind.retrieve_all(
            query="TRANSFERABLE_LEARNING",
            max_results=200
        )

        loaded = 0
        for memory in memories:
            content = memory.get("content", "")
            metadata = memory.get("metadata", {})

            if "learning_data" in metadata:
                try:
                    learning_data = metadata["learning_data"]
                    if isinstance(learning_data, str):
                        import json
                        learning_data = json.loads(learning_data)
                    learning = TransferableLearning.from_dict(learning_data)
                    self.transferable_learnings[learning.learning_id] = learning
                    loaded += 1
                except (ValueError, KeyError):
                    pass

        return loaded

    async def persist_learnings_to_mind(self) -> int:
        """
        Save transferable learnings to Mind.

        Returns:
            Number of learnings saved
        """
        if not self.mind or not await self.mind.is_available():
            return 0

        saved = 0
        for learning in self.transferable_learnings.values():
            if not learning.is_high_quality:
                continue

            import json
            content = f"TRANSFERABLE_LEARNING [{learning.scope.value}]: {learning.content[:100]}"

            await self.mind.store(
                content=content,
                temporal_level=4,  # Identity level
                content_type="reflection",
                salience=0.7,
                metadata={
                    "learning_id": learning.learning_id,
                    "scope": learning.scope.value,
                    "transfer_confidence": learning.transfer_confidence,
                    "learning_data": json.dumps(learning.to_dict())
                }
            )
            saved += 1

        return saved

    def get_stats(self) -> Dict:
        """Get statistics about learning transfer."""
        total = len(self.transferable_learnings)
        by_scope = {}
        total_transfers = 0
        successful_transfers = 0

        for learning in self.transferable_learnings.values():
            scope = learning.scope.value
            by_scope[scope] = by_scope.get(scope, 0) + 1
            total_transfers += learning.times_transferred
            successful_transfers += learning.success_when_transferred

        return {
            "total_learnings": total,
            "by_scope": by_scope,
            "total_transfers": total_transfers,
            "successful_transfers": successful_transfers,
            "transfer_success_rate": (
                successful_transfers / total_transfers
                if total_transfers > 0 else 0.5
            ),
            "high_quality_count": sum(
                1 for l in self.transferable_learnings.values()
                if l.is_high_quality
            )
        }
