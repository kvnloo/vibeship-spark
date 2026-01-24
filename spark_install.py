#!/usr/bin/env python3
"""
Spark Installer - One-Click Setup

Run this script to set up Spark for your system:
    python spark_install.py

This will:
1. Detect or ask for Mind installation path
2. Configure ~/.spark/config.json
3. Install hooks in ~/.claude/settings.json
4. Verify everything works

Usage:
    python spark_install.py              # Interactive setup
    python spark_install.py --auto       # Auto-detect everything
    python spark_install.py --mind PATH  # Specify Mind path
    python spark_install.py --uninstall  # Remove Spark hooks
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Optional, Dict, Any

# Add lib to path
sys.path.insert(0, str(Path(__file__).parent))

from lib.config import SparkConfig, MIND_SEARCH_PATHS, DEFAULT_CONFIG


class SparkInstaller:
    """Handles Spark installation and configuration."""

    SPARK_DIR = Path(__file__).parent.resolve()
    CLAUDE_SETTINGS = Path.home() / ".claude" / "settings.json"

    def __init__(self):
        self.config = SparkConfig()
        self.errors = []
        self.warnings = []

    def run_interactive(self):
        """Run interactive installation."""
        print("\n" + "=" * 60)
        print("  SPARK INSTALLER - Self-Evolving Intelligence for Claude")
        print("=" * 60 + "\n")

        # Step 1: Find Mind
        print("[1/4] Locating Mind installation...")
        mind_path = self._find_or_ask_mind()

        if mind_path:
            self.config.set("mind.lite_path", str(mind_path))
            print(f"      Found: {mind_path}")
        else:
            print("      WARNING: Mind not found. Auto-start disabled.")
            print("      You can set it later in ~/.spark/config.json")
            self.config.set("mind.auto_start", False)

        # Step 2: Configure settings
        print("\n[2/4] Creating configuration...")
        self.config.save()
        print(f"      Saved: {self.config.CONFIG_FILE}")

        # Step 3: Install hooks
        print("\n[3/4] Installing Claude Code hooks...")
        self._install_hooks()

        # Step 4: Verify
        print("\n[4/4] Verifying installation...")
        self._verify_installation()

        # Summary
        self._print_summary()

    def run_auto(self, mind_path: Optional[str] = None):
        """Run automatic installation."""
        print("\n  SPARK AUTO-INSTALL\n")

        # Find Mind
        if mind_path:
            path = Path(mind_path)
            if path.exists():
                self.config.set("mind.lite_path", str(path))
                print(f"  Mind path: {path}")
            else:
                self.errors.append(f"Mind path not found: {mind_path}")
                self.config.set("mind.auto_start", False)
        else:
            detected = self._detect_mind()
            if detected:
                self.config.set("mind.lite_path", str(detected))
                print(f"  Mind detected: {detected}")
            else:
                self.warnings.append("Mind not found - auto-start disabled")
                self.config.set("mind.auto_start", False)

        # Save config
        self.config.save()
        print(f"  Config saved: {self.config.CONFIG_FILE}")

        # Install hooks
        self._install_hooks()
        print("  Hooks installed")

        # Verify
        self._verify_installation()

        if self.errors:
            print(f"\n  ERRORS: {len(self.errors)}")
            for e in self.errors:
                print(f"    - {e}")
            sys.exit(1)
        else:
            print("\n  SUCCESS: Spark installed!")

    def uninstall(self):
        """Remove Spark hooks from Claude settings."""
        print("\n  SPARK UNINSTALL\n")

        if not self.CLAUDE_SETTINGS.exists():
            print("  No Claude settings found.")
            return

        try:
            settings = json.loads(self.CLAUDE_SETTINGS.read_text())
            if "hooks" in settings:
                del settings["hooks"]
                self.CLAUDE_SETTINGS.write_text(json.dumps(settings, indent=2))
                print("  Hooks removed from Claude settings.")
            else:
                print("  No hooks found to remove.")

            # Remove Spark MCP server if present
            if "mcpServers" in settings and "spark" in settings["mcpServers"]:
                del settings["mcpServers"]["spark"]
                self.CLAUDE_SETTINGS.write_text(json.dumps(settings, indent=2))
                print("  MCP server removed.")

            print("  Uninstall complete.")
            print("  Note: ~/.spark/ directory preserved (contains learnings)")
        except Exception as e:
            print(f"  Error: {e}")

    def _detect_mind(self) -> Optional[Path]:
        """Try to auto-detect Mind installation."""
        for path in MIND_SEARCH_PATHS:
            if path.exists():
                return path
        return None

    def _find_or_ask_mind(self) -> Optional[Path]:
        """Find Mind or ask user for path."""
        # Try auto-detect first
        detected = self._detect_mind()
        if detected:
            return detected

        # Ask user
        print("      Mind not found in common locations.")
        print("      Please enter the path to Mind Lite (lite_tier.py)")
        print("      Or press Enter to skip (auto-start will be disabled):")

        try:
            user_input = input("      > ").strip()
            if user_input:
                path = Path(user_input)
                if path.exists():
                    return path
                else:
                    print(f"      Path not found: {path}")
        except (EOFError, KeyboardInterrupt):
            pass

        return None

    def _install_hooks(self):
        """Install Spark hooks in Claude settings."""
        # Ensure .claude directory exists
        self.CLAUDE_SETTINGS.parent.mkdir(parents=True, exist_ok=True)

        # Load existing settings or create new
        if self.CLAUDE_SETTINGS.exists():
            try:
                settings = json.loads(self.CLAUDE_SETTINGS.read_text())
            except:
                settings = {}
        else:
            settings = {}

        # Build hook commands
        hooks_dir = self.SPARK_DIR / "hooks"
        observe_cmd = f'python "{hooks_dir / "observe.py"}"'
        session_start_cmd = f'python "{hooks_dir / "session_start.py"}"'
        session_end_cmd = f'python "{hooks_dir / "session_end.py"}"'

        # Define all hooks
        hooks_config = {
            "SessionStart": [
                {
                    "hooks": [
                        {"type": "command", "command": session_start_cmd, "timeout": 5}
                    ]
                }
            ],
            "UserPromptSubmit": [
                {
                    "hooks": [
                        {"type": "command", "command": observe_cmd, "timeout": 1}
                    ]
                }
            ],
            "PreToolUse": [
                {
                    "matcher": ".*",
                    "hooks": [
                        {"type": "command", "command": observe_cmd, "timeout": 1}
                    ]
                }
            ],
            "PostToolUse": [
                {
                    "matcher": ".*",
                    "hooks": [
                        {"type": "command", "command": observe_cmd, "timeout": 1}
                    ]
                }
            ],
            "PostToolUseFailure": [
                {
                    "matcher": ".*",
                    "hooks": [
                        {"type": "command", "command": observe_cmd, "timeout": 1}
                    ]
                }
            ],
            "Stop": [
                {
                    "hooks": [
                        {"type": "command", "command": observe_cmd, "timeout": 1}
                    ]
                }
            ],
            "SessionEnd": [
                {
                    "hooks": [
                        {"type": "command", "command": session_end_cmd, "timeout": 2}
                    ]
                }
            ]
        }

        # Merge hooks
        settings["hooks"] = hooks_config

        # Add MCP server if not present
        if "mcpServers" not in settings:
            settings["mcpServers"] = {}

        mcp_server_path = self.SPARK_DIR / "mcp-server" / "dist" / "index.js"
        if mcp_server_path.exists():
            settings["mcpServers"]["spark"] = {
                "command": "node",
                "args": [str(mcp_server_path)]
            }

        # Save settings
        self.CLAUDE_SETTINGS.write_text(json.dumps(settings, indent=2))
        print(f"      Hooks installed in: {self.CLAUDE_SETTINGS}")

    def _verify_installation(self) -> bool:
        """Verify the installation is correct."""
        ok = True

        # Check config file
        if not self.config.CONFIG_FILE.exists():
            self.errors.append("Config file not created")
            ok = False
        else:
            print("      Config file: OK")

        # Check hooks in Claude settings
        if self.CLAUDE_SETTINGS.exists():
            try:
                settings = json.loads(self.CLAUDE_SETTINGS.read_text())
                hooks = settings.get("hooks", {})
                required = ["SessionStart", "PostToolUse", "SessionEnd"]
                missing = [h for h in required if h not in hooks]
                if missing:
                    self.errors.append(f"Missing hooks: {', '.join(missing)}")
                    ok = False
                else:
                    print(f"      Hooks: OK ({len(hooks)} configured)")
            except:
                self.errors.append("Cannot read Claude settings")
                ok = False
        else:
            self.errors.append("Claude settings not found")
            ok = False

        # Check hook scripts exist
        hooks_dir = self.SPARK_DIR / "hooks"
        for script in ["observe.py", "session_start.py", "session_end.py"]:
            if not (hooks_dir / script).exists():
                self.errors.append(f"Hook script missing: {script}")
                ok = False

        if ok:
            print("      Hook scripts: OK")

        # Check Mind path (if configured)
        mind_path = self.config.mind_lite_path
        if mind_path:
            if mind_path.exists():
                print(f"      Mind path: OK")
            else:
                self.warnings.append(f"Mind path configured but not found: {mind_path}")
        else:
            if self.config.mind_auto_start:
                self.warnings.append("Mind auto-start enabled but path not set")

        return ok

    def _print_summary(self):
        """Print installation summary."""
        print("\n" + "=" * 60)

        if self.errors:
            print("  INSTALLATION FAILED")
            print("=" * 60)
            print("\n  Errors:")
            for e in self.errors:
                print(f"    ✗ {e}")
        else:
            print("  INSTALLATION SUCCESSFUL")
            print("=" * 60)

        if self.warnings:
            print("\n  Warnings:")
            for w in self.warnings:
                print(f"    ! {w}")

        if not self.errors:
            print("\n  Next steps:")
            print("    1. Restart Claude Code (to load new hooks)")
            print("    2. Start a new session - Spark will activate automatically!")
            print("")
            print("  Configuration file: ~/.spark/config.json")
            print("  To verify: python spark_cli.py startup")

        print("\n")


def main():
    parser = argparse.ArgumentParser(
        description="Spark Installer - Set up self-evolving intelligence for Claude Code"
    )
    parser.add_argument("--auto", action="store_true",
                       help="Automatic installation (no prompts)")
    parser.add_argument("--mind", type=str,
                       help="Path to Mind Lite (lite_tier.py)")
    parser.add_argument("--uninstall", action="store_true",
                       help="Remove Spark hooks")

    args = parser.parse_args()

    installer = SparkInstaller()

    if args.uninstall:
        installer.uninstall()
    elif args.auto:
        installer.run_auto(mind_path=args.mind)
    else:
        installer.run_interactive()


if __name__ == "__main__":
    main()
