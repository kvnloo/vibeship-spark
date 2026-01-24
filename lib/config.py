#!/usr/bin/env python3
"""
Spark Configuration Management

Handles user-specific configuration for Spark.
Config file location: ~/.spark/config.json

This allows different users to configure:
- Mind installation path
- Mind API URL
- Auto-start behaviors
- Custom settings
"""

import json
from pathlib import Path
from typing import Optional, Dict, Any


# Default configuration
DEFAULT_CONFIG = {
    "version": "1.0",

    # Mind settings
    "mind": {
        "api_url": "http://localhost:8080",
        "lite_path": None,  # Auto-detected or user-specified
        "auto_start": True,
        "start_timeout_seconds": 5
    },

    # Daemon settings
    "daemon": {
        "auto_start": True,
        "interval_seconds": 15,
        "queue_threshold": 50  # Auto-process if queue exceeds this
    },

    # Hook settings
    "hooks": {
        "timeout_seconds": 3,
        "inject_context": True,
        "inject_warnings": True,
        "inject_self_awareness": True
    },

    # Learning settings
    "learning": {
        "min_confidence": 0.5,
        "store_predictions": True,
        "track_goals": True
    }
}

# Common Mind installation paths to check
MIND_SEARCH_PATHS = [
    # Windows paths
    Path.home() / "Desktop" / "the-mind" / "vibeship-mind" / "src" / "mind" / "lite_tier.py",
    Path.home() / "Desktop" / "vibeship-mind" / "src" / "mind" / "lite_tier.py",
    Path.home() / "projects" / "vibeship-mind" / "src" / "mind" / "lite_tier.py",
    Path.home() / "code" / "vibeship-mind" / "src" / "mind" / "lite_tier.py",
    # Unix paths
    Path.home() / "vibeship-mind" / "src" / "mind" / "lite_tier.py",
    Path("/opt") / "vibeship-mind" / "src" / "mind" / "lite_tier.py",
]


class SparkConfig:
    """Manages Spark configuration."""

    CONFIG_DIR = Path.home() / ".spark"
    CONFIG_FILE = CONFIG_DIR / "config.json"

    def __init__(self):
        self._config: Dict[str, Any] = {}
        self._load()

    def _load(self):
        """Load config from file, creating defaults if needed."""
        if self.CONFIG_FILE.exists():
            try:
                self._config = json.loads(self.CONFIG_FILE.read_text())
                # Merge with defaults for any missing keys
                self._config = self._merge_defaults(self._config)
            except (json.JSONDecodeError, Exception):
                self._config = DEFAULT_CONFIG.copy()
        else:
            self._config = DEFAULT_CONFIG.copy()
            # Try to auto-detect Mind path
            self._auto_detect_mind()

    def _merge_defaults(self, config: Dict) -> Dict:
        """Merge user config with defaults for missing keys."""
        result = DEFAULT_CONFIG.copy()
        for key, value in config.items():
            if isinstance(value, dict) and key in result and isinstance(result[key], dict):
                result[key] = {**result[key], **value}
            else:
                result[key] = value
        return result

    def _auto_detect_mind(self):
        """Try to find Mind installation automatically."""
        for path in MIND_SEARCH_PATHS:
            if path.exists():
                self._config["mind"]["lite_path"] = str(path)
                break

    def save(self):
        """Save config to file."""
        self.CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        self.CONFIG_FILE.write_text(json.dumps(self._config, indent=2))

    def get(self, key: str, default: Any = None) -> Any:
        """Get a config value using dot notation (e.g., 'mind.api_url')."""
        keys = key.split(".")
        value = self._config
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        return value

    def set(self, key: str, value: Any):
        """Set a config value using dot notation."""
        keys = key.split(".")
        config = self._config
        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]
        config[keys[-1]] = value

    @property
    def mind_api_url(self) -> str:
        return self.get("mind.api_url", "http://localhost:8080")

    @property
    def mind_lite_path(self) -> Optional[Path]:
        path = self.get("mind.lite_path")
        return Path(path) if path else None

    @property
    def mind_auto_start(self) -> bool:
        return self.get("mind.auto_start", True)

    @property
    def daemon_auto_start(self) -> bool:
        return self.get("daemon.auto_start", True)

    @property
    def daemon_interval(self) -> int:
        return self.get("daemon.interval_seconds", 15)

    @property
    def queue_threshold(self) -> int:
        return self.get("daemon.queue_threshold", 50)

    def to_dict(self) -> Dict[str, Any]:
        """Return full config as dict."""
        return self._config.copy()


# Singleton instance
_config: Optional[SparkConfig] = None


def get_config() -> SparkConfig:
    """Get the singleton config instance."""
    global _config
    if _config is None:
        _config = SparkConfig()
    return _config


def reload_config():
    """Reload config from disk."""
    global _config
    _config = SparkConfig()
    return _config
