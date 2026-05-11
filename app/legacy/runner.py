import shlex
import subprocess
from pathlib import Path


ALLOWED_COMMAND_PREFIXES = [
    ["python"],
    ["python3"],
    ["pytest"],
    ["cargo"],
    ["npm"],
    ["pnpm"],
    ["yarn"],
    ["node"],
]


BLOCKED_TOKENS = {
    "rm",
    "sudo",
    "curl",
    "wget",
    "ssh",
    "scp",
    "chmod",
    "chown",
    "kill",
    "pkill",
    "dd",
    ">",
    ">>",
    "|",
    "&&",
    ";",
}


def is_allowed_command(command: str) -> tuple[bool, str]:
    try:
        parts = shlex.split(command)
    except ValueError as e:
        return False, f"命令解析失败：{e}"

    if not parts:
        return False, "命令为空。"

    for token in parts:
        if token in BLOCKED_TOKENS:
            return False, f"命令包含暂不允许的危险 token：{token}"

    first = parts[0]

    allowed = any(first == prefix[0] for prefix in ALLOWED_COMMAND_PREFIXES)

    if not allowed:
        return False, f"暂不允许执行该命令：{first}"

    return True, ""


def run_project_command(
    repo_path: str | Path,
    command: str,
    timeout: int = 60,
) -> dict:
    repo_path = Path(repo_path)

    ok, reason = is_allowed_command(command)
    if not ok:
        return {
            "ok": False,
            "command": command,
            "returncode": None,
            "stdout": "",
            "stderr": reason,
        }

    parts = shlex.split(command)

    try:
        result = subprocess.run(
            parts,
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=timeout,
        )

        return {
            "ok": result.returncode == 0,
            "command": command,
            "returncode": result.returncode,
            "stdout": result.stdout[-8000:],
            "stderr": result.stderr[-8000:],
        }

    except subprocess.TimeoutExpired:
        return {
            "ok": False,
            "command": command,
            "returncode": None,
            "stdout": "",
            "stderr": f"命令执行超时，超过 {timeout} 秒。",
        }

    except Exception as e:
        return {
            "ok": False,
            "command": command,
            "returncode": None,
            "stdout": "",
            "stderr": str(e),
        }