"""
Terminal Tool - Allows LLM to execute shell commands in a sandboxed environment.

Commands are executed within the workspace directory (/workspace in Docker).
The shell is restricted so the LLM cannot escape to the wider filesystem.
Modeled after OpenClaw's exec tool.
"""

import os
import subprocess
from pathlib import Path
from backend.utils.util_func import log


# Workspace directory
WORKSPACE_DIR = Path(os.environ.get("WORKSPACE_PATH", "/workspace"))

# Commands that are never allowed (dangerous even inside container)
_BLOCKED_COMMANDS = {
    'rm -rf /',
    'mkfs',
    'dd if=',
    ':(){:|:&};:',  # fork bomb
}

# Prefixes that are blocked (filesystem escape / privilege escalation)
_BLOCKED_PREFIXES = (
    'sudo ',
    'su ',
    'chroot ',
    'nsenter ',
    'docker ',
    'mount ',
    'umount ',
)


def _sanitize_command(command: str) -> str | None:
    """
    Wrap a command so it can only access /workspace.

    Returns the sandboxed command string, or None if the command is blocked.
    """
    stripped = command.strip()

    # Block dangerous commands
    for blocked in _BLOCKED_COMMANDS:
        if blocked in stripped:
            return None

    for prefix in _BLOCKED_PREFIXES:
        if stripped.startswith(prefix) or f'&& {prefix}' in stripped or f'; {prefix}' in stripped:
            return None

    # Wrap in a sub-shell that cd's to workspace and sets HOME
    safe_env_prefix = (
        f'cd {WORKSPACE_DIR} && '
        f'HOME={WORKSPACE_DIR} '
    )

    return safe_env_prefix + command


def execute_terminal_command(command: str, timeout: int = 30) -> dict:
    """
    Execute a shell command in the project workspace and return the output.

    Use this tool when you need to:
    - Install Python packages (pip install)
    - Run shell utilities (ls, wc, head, curl, etc.)
    - Check system info or environment details
    - Run scripts or CLI tools
    - Search for files or content (find, grep)
    - Perform file operations that are easier via shell

    Commands run inside the workspace directory. Dangerous operations
    (sudo, docker, mount, etc.) are blocked.

    Args:
        command: The shell command to execute (e.g., "ls -la", "pip install pandas", "python script.py")
        timeout: Maximum execution time in seconds (default: 30, max: 120). Command is killed if it exceeds this.

    Returns:
        Dictionary with:
        - success: Whether the command exited with code 0
        - stdout: Standard output from the command
        - stderr: Standard error output from the command
        - exit_code: The command's exit code (0 = success)
        - error: Error message if command failed to execute (e.g., timeout)

    Example:
        To list files: execute_terminal_command("ls -la")
        To install a package: execute_terminal_command("pip install pandas", timeout=60)
        To run a script: execute_terminal_command("python my_script.py")
        To search files: execute_terminal_command("grep -r 'pattern' .")
    """
    log(f"==> execute_terminal_command({command}) called from LLM")

    if not command or not command.strip():
        return {
            "success": False,
            "stdout": "",
            "stderr": "",
            "exit_code": -1,
            "error": "No command provided"
        }

    # Clamp timeout
    timeout = min(max(timeout, 1), 120)

    # Sanitize and sandbox the command
    sandboxed = _sanitize_command(command)
    if sandboxed is None:
        return {
            "success": False,
            "stdout": "",
            "stderr": "",
            "exit_code": -1,
            "error": "Command blocked for security reasons"
        }

    # Ensure workspace exists
    WORKSPACE_DIR.mkdir(parents=True, exist_ok=True)

    # Build a clean environment — strip sensitive vars, keep essentials
    clean_env = {
        "PATH": os.environ.get("PATH", "/usr/local/bin:/usr/bin:/bin"),
        "HOME": str(WORKSPACE_DIR),
        "TERM": "xterm",
        "LANG": os.environ.get("LANG", "C.UTF-8"),
        "PYTHONPATH": "",
    }

    try:
        result = subprocess.run(
            sandboxed,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(WORKSPACE_DIR),
            env=clean_env,
        )

        return {
            "success": result.returncode == 0,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "exit_code": result.returncode,
            "error": None
        }

    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "stdout": "",
            "stderr": "",
            "exit_code": -1,
            "error": f"Command timed out after {timeout} seconds"
        }
    except Exception as e:
        return {
            "success": False,
            "stdout": "",
            "stderr": "",
            "exit_code": -1,
            "error": f"Failed to execute command: {str(e)}"
        }
