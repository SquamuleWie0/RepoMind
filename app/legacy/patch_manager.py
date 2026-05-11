import subprocess
import time
from pathlib import Path


def is_safe_patch(patch_text: str) -> tuple[bool, str]:
    """
    做基础安全检查，避免 patch 写到仓库外部。
    """
    unsafe_patterns = [
        "../",
        "--- /",
        "+++ /",
    ]

    for pattern in unsafe_patterns:
        if pattern in patch_text:
            return False, f"patch 中包含不安全路径：{pattern}"

    if "CANNOT_GENERATE_PATCH" in patch_text:
        return False, patch_text

    if "--- " not in patch_text or "+++ " not in patch_text or "@@" not in patch_text:
        return False, "不是有效的 unified diff patch。"

    return True, ""


def get_patch_dir(repo_path: str | Path) -> Path:
    repo_path = Path(repo_path).resolve()
    patch_dir = repo_path / ".repomind" / "patches"
    patch_dir.mkdir(parents=True, exist_ok=True)
    return patch_dir


def save_pending_patch(repo_path: str | Path, patch_text: str) -> dict:
    repo_path = Path(repo_path).resolve()
    patch_dir = get_patch_dir(repo_path)

    patch_id = f"patch_{int(time.time())}"
    patch_path = patch_dir / f"{patch_id}.diff"

    patch_path.write_text(patch_text, encoding="utf-8")

    return {
        "patch_id": patch_id,
        "patch_path": str(patch_path),
        "patch_text": patch_text,
    }


def check_patch(repo_path: str | Path, patch_text: str) -> dict:
    repo_path = Path(repo_path).resolve()

    safe, reason = is_safe_patch(patch_text)
    if not safe:
        return {
            "ok": False,
            "message": reason,
            "stdout": "",
            "stderr": reason,
        }

    patch_dir = get_patch_dir(repo_path)
    temp_patch = patch_dir / "temp_check.diff"
    temp_patch.write_text(patch_text, encoding="utf-8")

    result = subprocess.run(
        ["git", "apply", "--check", str(temp_patch.resolve())],
        cwd=str(repo_path),
        capture_output=True,
        text=True,
        timeout=30,
    )

    return {
        "ok": result.returncode == 0,
        "message": "patch 可以应用" if result.returncode == 0 else "patch 检查失败",
        "stdout": result.stdout,
        "stderr": result.stderr,
    }


def apply_patch(repo_path: str | Path, patch_text: str) -> dict:
    repo_path = Path(repo_path).resolve()

    check_result = check_patch(repo_path, patch_text)
    if not check_result["ok"]:
        return check_result

    patch_dir = get_patch_dir(repo_path)
    temp_patch = patch_dir / "temp_apply.diff"
    temp_patch.write_text(patch_text, encoding="utf-8")

    result = subprocess.run(
        ["git", "apply", str(temp_patch.resolve())],
        cwd=str(repo_path),
        capture_output=True,
        text=True,
        timeout=30,
    )

    return {
        "ok": result.returncode == 0,
        "message": "patch 已应用" if result.returncode == 0 else "patch 应用失败",
        "stdout": result.stdout,
        "stderr": result.stderr,
    }


def rollback_patch(repo_path: str | Path, patch_text: str) -> dict:
    repo_path = Path(repo_path).resolve()

    patch_dir = get_patch_dir(repo_path)
    temp_patch = patch_dir / "temp_rollback.diff"
    temp_patch.write_text(patch_text, encoding="utf-8")

    result = subprocess.run(
        ["git", "apply", "-R", str(temp_patch.resolve())],
        cwd=str(repo_path),
        capture_output=True,
        text=True,
        timeout=30,
    )

    return {
        "ok": result.returncode == 0,
        "message": "patch 已回滚" if result.returncode == 0 else "patch 回滚失败",
        "stdout": result.stdout,
        "stderr": result.stderr,
    }