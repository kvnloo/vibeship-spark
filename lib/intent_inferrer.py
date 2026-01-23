"""
Spark Intent Inferrer: Guess what Claude is trying to achieve.

Since we can't read Claude's actual reasoning, we infer intent from:
1. Tool name
2. Tool input parameters
3. Recent context

This is fast (< 5ms) and runs in the observe hook.
"""

from typing import Any, Dict, List, Optional, Tuple


def infer_intent(tool_name: str, tool_input: Dict[str, Any]) -> Tuple[str, float, List[str]]:
    """
    Infer intent from tool name and input.

    Returns: (intent_description, predicted_confidence, risk_factors)
    """
    intent = "unknown operation"
    confidence = 0.7  # Default confidence
    risks: List[str] = []

    if tool_name == "Read":
        file_path = tool_input.get("file_path", "")
        if file_path:
            intent = f"read file to understand content"
            confidence = 0.9  # Read usually works
            if " " in file_path:
                risks.append("path contains spaces")
                confidence = 0.7
            if "\\" in file_path:
                risks.append("windows path format")

    elif tool_name == "Edit":
        file_path = tool_input.get("file_path", "")
        old_string = tool_input.get("old_string", "")
        intent = "modify existing code"
        confidence = 0.75

        if len(old_string) < 20:
            risks.append("old_string may not be unique")
            confidence = 0.5
        if len(old_string) > 200:
            risks.append("large edit block")
            confidence = 0.6
        if not file_path:
            risks.append("no file path specified")
            confidence = 0.3

    elif tool_name == "Write":
        file_path = tool_input.get("file_path", "")
        intent = "create or overwrite file"
        confidence = 0.85

        if not file_path:
            risks.append("no file path")
            confidence = 0.3

    elif tool_name == "Bash":
        command = tool_input.get("command", "")
        intent = _infer_bash_intent(command)
        confidence, risks = _assess_bash_risks(command)

    elif tool_name == "Grep":
        pattern = tool_input.get("pattern", "")
        intent = f"search for pattern in codebase"
        confidence = 0.85

        if len(pattern) < 3:
            risks.append("very short pattern may match too much")
            confidence = 0.6

    elif tool_name == "Glob":
        pattern = tool_input.get("pattern", "")
        intent = "find files matching pattern"
        confidence = 0.9

    elif tool_name == "Task":
        agent_type = tool_input.get("subagent_type", "")
        intent = f"delegate to {agent_type} agent"
        confidence = 0.7
        risks.append("agent may not complete task fully")

    elif tool_name == "Skill":
        skill = tool_input.get("skill", "")
        intent = f"invoke {skill} skill"
        confidence = 0.75

    elif tool_name == "WebFetch":
        url = tool_input.get("url", "")
        intent = "fetch web content"
        confidence = 0.6
        risks.append("external network dependency")
        risks.append("content may not be what expected")

    elif tool_name == "WebSearch":
        intent = "search the web for information"
        confidence = 0.7
        risks.append("results may not be relevant")

    elif tool_name == "TodoWrite":
        intent = "update task tracking"
        confidence = 0.95

    elif tool_name == "AskUserQuestion":
        intent = "get clarification from user"
        confidence = 0.95

    elif tool_name == "LSP":
        operation = tool_input.get("operation", "")
        intent = f"code intelligence: {operation}"
        confidence = 0.7
        risks.append("LSP server may not be available")

    return intent, confidence, risks


def _infer_bash_intent(command: str) -> str:
    """Infer intent from bash command."""
    cmd_lower = command.lower()

    if cmd_lower.startswith("git "):
        if "commit" in cmd_lower:
            return "commit changes to git"
        elif "push" in cmd_lower:
            return "push to remote"
        elif "pull" in cmd_lower:
            return "pull from remote"
        elif "status" in cmd_lower:
            return "check git status"
        elif "diff" in cmd_lower:
            return "view git changes"
        elif "log" in cmd_lower:
            return "view git history"
        return "git operation"

    if cmd_lower.startswith("npm ") or cmd_lower.startswith("yarn ") or cmd_lower.startswith("pnpm "):
        if "install" in cmd_lower:
            return "install dependencies"
        elif "run" in cmd_lower or "start" in cmd_lower:
            return "run npm script"
        elif "test" in cmd_lower:
            return "run tests"
        return "package manager operation"

    if cmd_lower.startswith("python "):
        if "test" in cmd_lower or "pytest" in cmd_lower:
            return "run Python tests"
        elif "-m" in cmd_lower:
            return "run Python module"
        return "execute Python script"

    if cmd_lower.startswith("pip "):
        return "manage Python packages"

    if cmd_lower.startswith("cd "):
        return "change directory"

    if cmd_lower.startswith("mkdir "):
        return "create directory"

    if cmd_lower.startswith("curl ") or cmd_lower.startswith("wget "):
        return "make HTTP request"

    if "docker" in cmd_lower:
        return "docker operation"

    return "execute shell command"


def _assess_bash_risks(command: str) -> Tuple[float, List[str]]:
    """Assess confidence and risks for bash command."""
    confidence = 0.7
    risks = []
    cmd_lower = command.lower()

    # High-risk commands
    if any(x in cmd_lower for x in ["rm -rf", "rm -r", "rmdir"]):
        risks.append("destructive command")
        confidence = 0.5

    if "sudo" in cmd_lower:
        risks.append("elevated privileges")
        confidence = 0.5

    # Network operations
    if any(x in cmd_lower for x in ["curl", "wget", "fetch"]):
        risks.append("network dependency")
        confidence = 0.6

    # Long-running operations
    if any(x in cmd_lower for x in ["npm install", "pip install", "docker build"]):
        risks.append("may take a while")
        confidence = 0.65

    # Git operations
    if "git push" in cmd_lower:
        risks.append("remote operation")
        confidence = 0.75

    if "git commit" in cmd_lower and "-m" not in cmd_lower:
        risks.append("missing commit message")
        confidence = 0.4

    # Path issues
    if " " in command and '"' not in command and "'" not in command:
        risks.append("unquoted path with spaces")
        confidence = 0.5

    return confidence, risks


def predict_outcome(tool_name: str, tool_input: Dict[str, Any]) -> str:
    """Generate a predicted outcome description."""
    intent, _, risks = infer_intent(tool_name, tool_input)

    if not risks:
        return f"Successfully {intent}"

    risk_str = risks[0] if risks else "unknown issue"
    return f"May {intent}, but watch for: {risk_str}"
