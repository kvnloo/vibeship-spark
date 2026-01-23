"""
Spark Backup: Learning persistence and export.

Provides:
- Full system state backup
- Learning export/import
- Pattern archive management
- Migration between environments
- Disaster recovery
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any, Tuple
from datetime import datetime
from pathlib import Path
from enum import Enum
import json
import gzip
import shutil
import hashlib

from .mind_client import MindClient
from .prompt_evolver import PromptEvolver, PromptPattern
from .learner import SparkLearner
from .queue import SparkQueue


class BackupFormat(Enum):
    """Backup file formats."""
    JSON = "json"
    JSON_GZ = "json.gz"


class BackupType(Enum):
    """Types of backups."""
    FULL = "full"
    LEARNINGS = "learnings"
    PATTERNS = "patterns"
    QUEUE = "queue"
    INCREMENTAL = "incremental"


@dataclass
class BackupManifest:
    """Manifest describing a backup."""
    backup_id: str
    backup_type: BackupType
    created_at: datetime
    spark_version: str
    components: List[str]
    item_counts: Dict[str, int]
    file_size_bytes: int
    checksum: str
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RestoreResult:
    """Result of a restore operation."""
    success: bool
    backup_id: str
    items_restored: Dict[str, int]
    warnings: List[str]
    errors: List[str]


class SparkBackup:
    """
    Backup and restore system for Spark.

    Handles persistence of learnings, patterns, and
    system state for disaster recovery and migration.
    """

    VERSION = "1.0.0"

    # Default backup location
    BACKUP_DIR = Path.home() / ".spark" / "backups"

    def __init__(
        self,
        mind_client: Optional[MindClient] = None,
        evolver: Optional[PromptEvolver] = None,
        learner: Optional[SparkLearner] = None,
        queue: Optional[SparkQueue] = None,
        backup_dir: Optional[Path] = None
    ):
        self.mind = mind_client
        self.evolver = evolver
        self.learner = learner
        self.queue = queue or SparkQueue()

        self.backup_dir = backup_dir or self.BACKUP_DIR
        self.backup_dir.mkdir(parents=True, exist_ok=True)

        self._manifests: Dict[str, BackupManifest] = {}
        self._load_manifests()

    def _load_manifests(self):
        """Load existing backup manifests."""
        manifest_file = self.backup_dir / "manifests.json"
        if manifest_file.exists():
            try:
                data = json.loads(manifest_file.read_text())
                for item in data:
                    manifest = BackupManifest(
                        backup_id=item["backup_id"],
                        backup_type=BackupType(item["backup_type"]),
                        created_at=datetime.fromisoformat(item["created_at"]),
                        spark_version=item["spark_version"],
                        components=item["components"],
                        item_counts=item["item_counts"],
                        file_size_bytes=item["file_size_bytes"],
                        checksum=item["checksum"],
                        metadata=item.get("metadata", {})
                    )
                    self._manifests[manifest.backup_id] = manifest
            except Exception:
                pass

    def _save_manifests(self):
        """Save manifests to disk."""
        manifest_file = self.backup_dir / "manifests.json"
        data = [
            {
                "backup_id": m.backup_id,
                "backup_type": m.backup_type.value,
                "created_at": m.created_at.isoformat(),
                "spark_version": m.spark_version,
                "components": m.components,
                "item_counts": m.item_counts,
                "file_size_bytes": m.file_size_bytes,
                "checksum": m.checksum,
                "metadata": m.metadata
            }
            for m in self._manifests.values()
        ]
        manifest_file.write_text(json.dumps(data, indent=2))

    async def create_backup(
        self,
        backup_type: BackupType = BackupType.FULL,
        format: BackupFormat = BackupFormat.JSON_GZ,
        description: Optional[str] = None
    ) -> BackupManifest:
        """
        Create a new backup.

        Args:
            backup_type: Type of backup to create
            format: Output format
            description: Optional description

        Returns:
            BackupManifest
        """
        backup_id = f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        backup_data: Dict[str, Any] = {
            "backup_id": backup_id,
            "backup_type": backup_type.value,
            "created_at": datetime.now().isoformat(),
            "spark_version": self.VERSION,
            "components": {}
        }

        item_counts = {}
        components = []

        # Collect data based on backup type
        if backup_type in [BackupType.FULL, BackupType.LEARNINGS]:
            if self.mind:
                learnings = await self._export_learnings()
                backup_data["components"]["learnings"] = learnings
                item_counts["learnings"] = len(learnings)
                components.append("learnings")

        if backup_type in [BackupType.FULL, BackupType.PATTERNS]:
            if self.evolver:
                patterns = self._export_patterns()
                backup_data["components"]["patterns"] = patterns
                item_counts["patterns"] = len(patterns)
                components.append("patterns")

            if self.learner:
                tool_stats = self._export_tool_stats()
                backup_data["components"]["tool_stats"] = tool_stats
                item_counts["tool_stats"] = len(tool_stats)
                components.append("tool_stats")

        if backup_type in [BackupType.FULL, BackupType.QUEUE]:
            queue_events = self._export_queue()
            backup_data["components"]["queue"] = queue_events
            item_counts["queue"] = len(queue_events)
            components.append("queue")

        # Write backup file
        filename = f"{backup_id}.{format.value}"
        filepath = self.backup_dir / filename

        content = json.dumps(backup_data, indent=2, default=str)

        if format == BackupFormat.JSON_GZ:
            with gzip.open(filepath, 'wt', encoding='utf-8') as f:
                f.write(content)
        else:
            filepath.write_text(content)

        # Calculate checksum
        file_content = filepath.read_bytes()
        checksum = hashlib.sha256(file_content).hexdigest()[:16]

        # Create manifest
        manifest = BackupManifest(
            backup_id=backup_id,
            backup_type=backup_type,
            created_at=datetime.now(),
            spark_version=self.VERSION,
            components=components,
            item_counts=item_counts,
            file_size_bytes=len(file_content),
            checksum=checksum,
            metadata={"description": description} if description else {}
        )

        self._manifests[backup_id] = manifest
        self._save_manifests()

        return manifest

    async def _export_learnings(self) -> List[Dict[str, Any]]:
        """Export learnings from Mind using pagination."""
        if not self.mind:
            return []

        try:
            # Use retrieve_all for paginated retrieval (Mind Lite caps at 100)
            # Query for LEARNING patterns which is what Spark stores
            learnings = await self.mind.retrieve_all("LEARNING", max_results=1000)
            return [
                {
                    "content": l.get("content", ""),
                    "temporal_level": l.get("temporal_level", 2),
                    "salience": l.get("salience", 0.5),
                    "content_type": l.get("content_type", "observation"),
                    "created_at": l.get("created_at", "")
                }
                for l in learnings
            ]
        except Exception:
            return []

    def _export_patterns(self) -> List[Dict[str, Any]]:
        """Export patterns from evolver."""
        if not self.evolver:
            return []

        return [
            {
                "pattern_id": p.pattern_id,
                "pattern_type": p.pattern_type,
                "description": p.description,
                "trigger_conditions": p.trigger_conditions,
                "approach": p.approach,
                "total_uses": p.total_uses,
                "success_count": p.success_count,
                "failure_count": p.failure_count,
                "tool_sequence": p.tool_sequence,
                "created_at": (p.created_at.isoformat() if hasattr(p.created_at, 'isoformat')
                             else datetime.fromtimestamp(p.created_at).isoformat() if p.created_at else None)
            }
            for p in self.evolver.patterns.values()
        ]

    def _export_tool_stats(self) -> Dict[str, Any]:
        """Export tool statistics from learner."""
        if not self.learner:
            return {}

        return {
            "tool_success": dict(self.learner.tool_success),
            "tool_duration": dict(self.learner.tool_duration),
            "tool_count": dict(self.learner.tool_count),
            "error_patterns": dict(self.learner.error_patterns)
        }

    def _export_queue(self) -> List[Dict[str, Any]]:
        """Export pending queue events."""
        events = self.queue.peek(self.queue.size())
        return [
            {
                "event_type": e.event_type.value,
                "timestamp": e.timestamp,
                "session_id": e.session_id,
                "tool_name": e.tool_name,
                "duration_ms": e.duration_ms,
                "error": e.error,
                "data": e.data
            }
            for e in events
        ]

    async def restore_backup(
        self,
        backup_id: str,
        components: Optional[List[str]] = None,
        dry_run: bool = False
    ) -> RestoreResult:
        """
        Restore from a backup.

        Args:
            backup_id: Backup to restore
            components: Specific components to restore (all if None)
            dry_run: If True, simulate without actually restoring

        Returns:
            RestoreResult
        """
        manifest = self._manifests.get(backup_id)
        if not manifest:
            return RestoreResult(
                success=False,
                backup_id=backup_id,
                items_restored={},
                warnings=[],
                errors=["Backup not found"]
            )

        # Load backup file
        backup_data = self._load_backup_file(backup_id)
        if not backup_data:
            return RestoreResult(
                success=False,
                backup_id=backup_id,
                items_restored={},
                warnings=[],
                errors=["Failed to load backup file"]
            )

        items_restored = {}
        warnings = []
        errors = []

        target_components = components or manifest.components

        # Restore each component
        if "learnings" in target_components and "learnings" in backup_data.get("components", {}):
            if not dry_run:
                count = await self._restore_learnings(backup_data["components"]["learnings"])
                items_restored["learnings"] = count
            else:
                items_restored["learnings"] = len(backup_data["components"]["learnings"])

        if "patterns" in target_components and "patterns" in backup_data.get("components", {}):
            if not dry_run:
                count = self._restore_patterns(backup_data["components"]["patterns"])
                items_restored["patterns"] = count
            else:
                items_restored["patterns"] = len(backup_data["components"]["patterns"])

        if "tool_stats" in target_components and "tool_stats" in backup_data.get("components", {}):
            if not dry_run:
                self._restore_tool_stats(backup_data["components"]["tool_stats"])
                items_restored["tool_stats"] = 1
            else:
                items_restored["tool_stats"] = 1

        # Version check
        if backup_data.get("spark_version") != self.VERSION:
            warnings.append(f"Version mismatch: backup={backup_data.get('spark_version')}, current={self.VERSION}")

        return RestoreResult(
            success=len(errors) == 0,
            backup_id=backup_id,
            items_restored=items_restored,
            warnings=warnings,
            errors=errors
        )

    def _load_backup_file(self, backup_id: str) -> Optional[Dict[str, Any]]:
        """Load a backup file."""
        for format in BackupFormat:
            filepath = self.backup_dir / f"{backup_id}.{format.value}"
            if filepath.exists():
                try:
                    if format == BackupFormat.JSON_GZ:
                        with gzip.open(filepath, 'rt', encoding='utf-8') as f:
                            return json.load(f)
                    else:
                        return json.loads(filepath.read_text())
                except Exception:
                    continue
        return None

    async def _restore_learnings(self, learnings: List[Dict[str, Any]]) -> int:
        """Restore learnings to Mind."""
        if not self.mind:
            return 0

        count = 0
        for learning in learnings:
            try:
                await self.mind.store(
                    content=learning["content"],
                    temporal_level=learning.get("temporal_level", 2),
                    salience=learning.get("salience", 0.5),
                    content_type=learning.get("content_type", "observation")
                )
                count += 1
            except Exception:
                continue

        return count

    def _restore_patterns(self, patterns: List[Dict[str, Any]]) -> int:
        """Restore patterns to evolver."""
        if not self.evolver:
            return 0

        count = 0
        for p in patterns:
            try:
                pattern = PromptPattern(
                    pattern_id=p["pattern_id"],
                    pattern_type=p["pattern_type"],
                    description=p["description"],
                    trigger_conditions=p.get("trigger_conditions", {}),
                    approach=p["approach"],
                    total_uses=p.get("total_uses", 0),
                    success_count=p.get("success_count", 0),
                    failure_count=p.get("failure_count", 0),
                    tool_sequence=p.get("tool_sequence"),
                    created_at=datetime.fromisoformat(p["created_at"]) if p.get("created_at") else None
                )
                self.evolver.patterns[pattern.pattern_id] = pattern
                count += 1
            except Exception:
                continue

        return count

    def _restore_tool_stats(self, stats: Dict[str, Any]):
        """Restore tool statistics to learner."""
        if not self.learner:
            return

        if "tool_success" in stats:
            self.learner.tool_success.update(stats["tool_success"])
        if "tool_duration" in stats:
            self.learner.tool_duration.update(stats["tool_duration"])
        if "tool_count" in stats:
            self.learner.tool_count.update(stats["tool_count"])
        if "error_patterns" in stats:
            self.learner.error_patterns.update(stats["error_patterns"])

    def list_backups(self, backup_type: Optional[BackupType] = None) -> List[BackupManifest]:
        """
        List available backups.

        Args:
            backup_type: Filter by type

        Returns:
            List of manifests
        """
        manifests = list(self._manifests.values())

        if backup_type:
            manifests = [m for m in manifests if m.backup_type == backup_type]

        return sorted(manifests, key=lambda m: m.created_at, reverse=True)

    def get_backup_info(self, backup_id: str) -> Optional[BackupManifest]:
        """Get info about a specific backup."""
        return self._manifests.get(backup_id)

    def delete_backup(self, backup_id: str) -> bool:
        """
        Delete a backup.

        Args:
            backup_id: Backup to delete

        Returns:
            True if deleted
        """
        if backup_id not in self._manifests:
            return False

        # Delete files
        for format in BackupFormat:
            filepath = self.backup_dir / f"{backup_id}.{format.value}"
            if filepath.exists():
                filepath.unlink()

        del self._manifests[backup_id]
        self._save_manifests()

        return True

    def cleanup_old_backups(self, keep_count: int = 10) -> int:
        """
        Delete old backups, keeping the most recent.

        Args:
            keep_count: Number of backups to keep

        Returns:
            Number of backups deleted
        """
        manifests = self.list_backups()

        if len(manifests) <= keep_count:
            return 0

        to_delete = manifests[keep_count:]
        deleted = 0

        for manifest in to_delete:
            if self.delete_backup(manifest.backup_id):
                deleted += 1

        return deleted

    def verify_backup(self, backup_id: str) -> Tuple[bool, List[str]]:
        """
        Verify a backup's integrity.

        Args:
            backup_id: Backup to verify

        Returns:
            (is_valid, issues)
        """
        manifest = self._manifests.get(backup_id)
        if not manifest:
            return False, ["Backup not found"]

        issues = []

        # Check file exists
        found_file = None
        for format in BackupFormat:
            filepath = self.backup_dir / f"{backup_id}.{format.value}"
            if filepath.exists():
                found_file = filepath
                break

        if not found_file:
            return False, ["Backup file not found"]

        # Verify checksum
        file_content = found_file.read_bytes()
        current_checksum = hashlib.sha256(file_content).hexdigest()[:16]

        if current_checksum != manifest.checksum:
            issues.append(f"Checksum mismatch: expected {manifest.checksum}, got {current_checksum}")

        # Verify size
        if len(file_content) != manifest.file_size_bytes:
            issues.append(f"Size mismatch: expected {manifest.file_size_bytes}, got {len(file_content)}")

        # Verify content is valid JSON
        try:
            if found_file.suffix == ".gz":
                with gzip.open(found_file, 'rt') as f:
                    json.load(f)
            else:
                json.loads(file_content)
        except json.JSONDecodeError as e:
            issues.append(f"Invalid JSON: {e}")

        return len(issues) == 0, issues

    async def export_to_file(
        self,
        filepath: Path,
        format: BackupFormat = BackupFormat.JSON
    ) -> bool:
        """
        Export current state to a specific file.

        Args:
            filepath: Destination file
            format: Export format

        Returns:
            True if successful
        """
        try:
            manifest = await self.create_backup(
                backup_type=BackupType.FULL,
                format=format
            )

            # Move to target location
            source = self.backup_dir / f"{manifest.backup_id}.{format.value}"
            shutil.copy(source, filepath)

            return True
        except Exception:
            return False

    async def import_from_file(self, filepath: Path) -> RestoreResult:
        """
        Import state from an external file.

        Args:
            filepath: Source file

        Returns:
            RestoreResult
        """
        if not filepath.exists():
            return RestoreResult(
                success=False,
                backup_id="",
                items_restored={},
                warnings=[],
                errors=["File not found"]
            )

        try:
            # Copy to backup dir
            backup_id = f"import_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

            if filepath.suffix == ".gz":
                dest = self.backup_dir / f"{backup_id}.json.gz"
            else:
                dest = self.backup_dir / f"{backup_id}.json"

            shutil.copy(filepath, dest)

            # Load and create manifest
            backup_data = self._load_backup_file(backup_id)
            if not backup_data:
                return RestoreResult(
                    success=False,
                    backup_id=backup_id,
                    items_restored={},
                    warnings=[],
                    errors=["Failed to parse backup file"]
                )

            # Create manifest
            file_content = dest.read_bytes()
            manifest = BackupManifest(
                backup_id=backup_id,
                backup_type=BackupType(backup_data.get("backup_type", "full")),
                created_at=datetime.now(),
                spark_version=backup_data.get("spark_version", "unknown"),
                components=list(backup_data.get("components", {}).keys()),
                item_counts={k: len(v) if isinstance(v, list) else 1
                            for k, v in backup_data.get("components", {}).items()},
                file_size_bytes=len(file_content),
                checksum=hashlib.sha256(file_content).hexdigest()[:16],
                metadata={"imported_from": str(filepath)}
            )

            self._manifests[backup_id] = manifest
            self._save_manifests()

            # Restore
            return await self.restore_backup(backup_id)

        except Exception as e:
            return RestoreResult(
                success=False,
                backup_id="",
                items_restored={},
                warnings=[],
                errors=[str(e)]
            )

    def get_stats(self) -> Dict[str, Any]:
        """Get backup system statistics."""
        manifests = list(self._manifests.values())
        total_size = sum(m.file_size_bytes for m in manifests)

        return {
            "backup_count": len(manifests),
            "total_size_bytes": total_size,
            "total_size_human": self._humanize_bytes(total_size),
            "backup_dir": str(self.backup_dir),
            "oldest_backup": min(m.created_at for m in manifests).isoformat() if manifests else None,
            "newest_backup": max(m.created_at for m in manifests).isoformat() if manifests else None,
            "by_type": {
                bt.value: sum(1 for m in manifests if m.backup_type == bt)
                for bt in BackupType
            }
        }

    def _humanize_bytes(self, bytes: int) -> str:
        """Convert bytes to human-readable string."""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if bytes < 1024:
                return f"{bytes:.1f} {unit}"
            bytes /= 1024
        return f"{bytes:.1f} TB"
