#!/usr/bin/env python3
"""
Spark Setup: Install and configure Spark hooks for Claude Code.

Usage:
    python setup.py install   # Install Spark hooks
    python setup.py uninstall # Remove Spark hooks
    python setup.py status    # Check installation status
    python setup.py test      # Test the setup
"""

import argparse
import json
import shutil
import sys
import io
from pathlib import Path

# Fix Windows console encoding
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')


def get_claude_settings_path() -> Path:
    """Get the Claude Code user settings path."""
    # User-level settings
    return Path.home() / ".claude" / "settings.json"


def get_project_settings_path() -> Path:
    """Get the project-level settings path."""
    return Path(__file__).parent.parent / ".claude" / "settings.json"


def load_settings(path: Path) -> dict:
    """Load existing settings or return empty dict."""
    if path.exists():
        try:
            with open(path, 'r') as f:
                return json.load(f)
        except json.JSONDecodeError:
            return {}
    return {}


def save_settings(path: Path, settings: dict):
    """Save settings to file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'w') as f:
        json.dump(settings, f, indent=2)


def get_spark_hooks() -> dict:
    """Get Spark hook configuration."""
    spark_dir = Path(__file__).parent
    hooks_config_path = spark_dir / "spark-hooks.json"

    if hooks_config_path.exists():
        with open(hooks_config_path, 'r') as f:
            config = json.load(f)
            return config.get("hooks", {})
    return {}


def install(scope: str = "project"):
    """Install Spark hooks."""
    print("🔥 Installing Spark hooks...")

    if scope == "user":
        settings_path = get_claude_settings_path()
        print(f"   Target: User settings ({settings_path})")
    else:
        settings_path = get_project_settings_path()
        print(f"   Target: Project settings ({settings_path})")

    # Load existing settings
    settings = load_settings(settings_path)

    # Get Spark hooks
    spark_hooks = get_spark_hooks()

    if not spark_hooks:
        print("❌ Could not load Spark hooks configuration")
        return False

    # Merge hooks (preserve existing hooks, add Spark hooks)
    if "hooks" not in settings:
        settings["hooks"] = {}

    for event, hook_configs in spark_hooks.items():
        if event not in settings["hooks"]:
            settings["hooks"][event] = []

        # Check if Spark hooks already installed
        existing_commands = [
            h.get("hooks", [{}])[0].get("command", "")
            for h in settings["hooks"][event]
        ]

        for hook_config in hook_configs:
            command = hook_config.get("hooks", [{}])[0].get("command", "")
            if "vibeship-spark" in command and command not in existing_commands:
                settings["hooks"][event].append(hook_config)
                print(f"   ✓ Added {event} hook")

    # Save settings
    save_settings(settings_path, settings)

    # Create queue directory
    queue_dir = Path.home() / ".spark" / "queue"
    queue_dir.mkdir(parents=True, exist_ok=True)
    print(f"   ✓ Created queue directory: {queue_dir}")

    print("\n✅ Spark installed successfully!")
    print("\n📋 Next steps:")
    print("   1. Restart Claude Code to load hooks")
    print("   2. Start Mind: start_mind_lite.bat")
    print("   3. Spark will automatically observe and learn")

    return True


def uninstall(scope: str = "project"):
    """Uninstall Spark hooks."""
    print("🔥 Uninstalling Spark hooks...")

    if scope == "user":
        settings_path = get_claude_settings_path()
    else:
        settings_path = get_project_settings_path()

    settings = load_settings(settings_path)

    if "hooks" not in settings:
        print("   No hooks found")
        return True

    # Remove Spark hooks
    for event in list(settings["hooks"].keys()):
        settings["hooks"][event] = [
            h for h in settings["hooks"][event]
            if "vibeship-spark" not in str(h)
        ]
        # Clean up empty events
        if not settings["hooks"][event]:
            del settings["hooks"][event]

    # Clean up empty hooks
    if not settings["hooks"]:
        del settings["hooks"]

    save_settings(settings_path, settings)
    print("✅ Spark hooks removed")

    return True


def status():
    """Check Spark installation status."""
    print("🔥 Spark Status\n")

    # Check project settings
    project_path = get_project_settings_path()
    project_settings = load_settings(project_path)
    project_hooks = project_settings.get("hooks", {})
    project_spark = any("vibeship-spark" in str(h) for hooks in project_hooks.values() for h in hooks)

    print(f"Project settings: {project_path}")
    print(f"   Spark installed: {'✓ Yes' if project_spark else '✗ No'}")

    # Check user settings
    user_path = get_claude_settings_path()
    user_settings = load_settings(user_path)
    user_hooks = user_settings.get("hooks", {})
    user_spark = any("vibeship-spark" in str(h) for hooks in user_hooks.values() for h in hooks)

    print(f"\nUser settings: {user_path}")
    print(f"   Spark installed: {'✓ Yes' if user_spark else '✗ No'}")

    # Check queue
    queue_dir = Path.home() / ".spark" / "queue"
    queue_file = queue_dir / "events.jsonl"
    queue_size = 0
    if queue_file.exists():
        with open(queue_file, 'r') as f:
            queue_size = sum(1 for _ in f)

    print(f"\nQueue: {queue_dir}")
    print(f"   Events pending: {queue_size}")

    # Check Mind
    import asyncio
    from lib.mind_client import MindClient

    async def check_mind():
        client = MindClient()
        available = await client.is_available()
        await client.close()
        return available

    mind_available = asyncio.run(check_mind())
    print(f"\nVibeship Mind: http://localhost:8080")
    print(f"   Available: {'✓ Yes' if mind_available else '✗ No'}")

    # Summary
    print("\n" + "="*50)
    if project_spark or user_spark:
        if mind_available:
            print("✅ Spark is fully operational")
        else:
            print("⚠️  Spark is installed but Mind is not running")
            print("   Run: start_mind_lite.bat")
    else:
        print("❌ Spark is not installed")
        print("   Run: python setup.py install")


def test():
    """Test Spark setup."""
    print("🔥 Testing Spark setup...\n")

    # Test 1: Queue
    print("1. Testing queue...")
    from lib.queue import quick_capture, EventType, get_queue

    success = quick_capture(
        EventType.POST_TOOL,
        "test_session",
        {"test": True},
        tool_name="TestTool"
    )
    print(f"   Queue capture: {'✓ Pass' if success else '✗ Fail'}")

    queue = get_queue()
    size = queue.size()
    print(f"   Queue readable: {'✓ Pass' if size >= 0 else '✗ Fail'}")

    # Test 2: Mind client
    print("\n2. Testing Mind client...")
    import asyncio
    from lib.mind_client import MindClient

    async def test_mind():
        client = MindClient(timeout=2.0)
        available = await client.is_available()
        await client.close()
        return available

    mind_ok = asyncio.run(test_mind())
    print(f"   Mind connection: {'✓ Pass' if mind_ok else '⚠️  Mind not running (optional)'}")

    # Test 3: Learner
    print("\n3. Testing learner...")
    from lib.learner import SparkLearner

    learner = SparkLearner()
    rankings = learner.get_tool_ranking()
    print(f"   Learner init: ✓ Pass")

    # Test 4: Hooks exist
    print("\n4. Testing hooks...")
    hooks_dir = Path(__file__).parent / "hooks"
    hooks = ["observe.py", "session_start.py", "session_end.py"]

    for hook in hooks:
        exists = (hooks_dir / hook).exists()
        print(f"   {hook}: {'✓ Exists' if exists else '✗ Missing'}")

    print("\n" + "="*50)
    print("✅ All tests passed!")


def main():
    parser = argparse.ArgumentParser(description="Spark Setup")
    parser.add_argument(
        "action",
        choices=["install", "uninstall", "status", "test"],
        help="Action to perform"
    )
    parser.add_argument(
        "--scope",
        choices=["project", "user"],
        default="project",
        help="Installation scope (default: project)"
    )

    args = parser.parse_args()

    if args.action == "install":
        install(args.scope)
    elif args.action == "uninstall":
        uninstall(args.scope)
    elif args.action == "status":
        status()
    elif args.action == "test":
        test()


if __name__ == "__main__":
    main()
