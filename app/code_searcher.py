# 根据搜索计划调用 ripgrep / rg 搜本地仓库

import json
import subprocess
from collections import defaultdict
from pathlib import Path
from typing import Any

from .context_builder import extract_context_block


CODE_SUFFIXES = {
    ".py",
    ".rs",
    ".js",
    ".ts",
    ".go",
    ".java",
    ".tsx",
    ".jsx",
}

CONFIG_FILE_NAMES = {
    "cargo.toml",
    "package.json",
    "requirements.txt",
    "pyproject.toml",
    "go.mod",
    "pom.xml",
    "dockerfile",
}

LOW_VALUE_DIRS = {
    "docs",
    "tests",
    "test",
    ".github",
    "assets",
    "static",
    "public",
    "examples",
}

IMPORTANT_FILE_NAMES = {
    "main.py",
    "app.py",
    "server.py",
    "main.rs",
    "lib.rs",
    "store.rs",
    "tasks.rs",
    "session.rs",
    "teams.rs",
    "roles.rs",
    "routes.py",
    "models.py",
    "services.py",
}


def should_keep_match(relative_path: str, plan: dict[str, Any]) -> bool:
    """
    判断某个搜索结果是否应该进入上下文。

    默认优先保留代码文件，避免 README、docs、tests、角色提示词等内容干扰代码问答。
    """
    path = Path(relative_path)
    suffix = path.suffix
    parts = set(path.parts)
    file_name = path.name.lower()

    # 如果 query_planner 明确指定了重点文件，优先保留
    if relative_path in plan.get("focus_files", []):
        return True

    # 默认保留代码文件
    if suffix in CODE_SUFFIXES:
        return True

    # 保留依赖 / 配置文件
    if file_name in CONFIG_FILE_NAMES:
        return True

    # 默认过滤 Markdown / 文档 / 提示词文件
    if suffix in {".md", ".txt", ".rst"}:
        return False

    # 默认过滤低价值目录
    if parts & LOW_VALUE_DIRS:
        return False

    return False


def resolve_focus_files(repo_path: Path, focus_files: list[str]) -> list[Path]:
    """
    将搜索计划中的重点文件路径转成真实文件路径。
    """
    result = []

    for file in focus_files:
        path = repo_path / file
        if path.exists() and path.is_file():
            result.append(path)

    return result


def resolve_focus_dirs(repo_path: Path, focus_dirs: list[str]) -> list[Path]:
    """
    将搜索计划中的重点目录转成真实目录路径。
    """
    result = []

    for directory in focus_dirs:
        path = repo_path / directory
        if path.exists() and path.is_dir():
            result.append(path)

    return result


def build_rg_command(
    keyword: str,
    targets: list[Path],
    avoid_dirs: list[str],
) -> list[str]:
    """
    构造 ripgrep 命令。
    """
    command = [
        "rg",
        "--json",
        "-n",
        "-i",
        "--max-count",
        "20",
    ]

    for directory in avoid_dirs:
        command.extend(["--glob", f"!{directory}/**"])

    command.append(keyword)

    for target in targets:
        command.append(str(target))

    return command


def run_rg_json(
    keyword: str,
    targets: list[Path],
    avoid_dirs: list[str],
) -> list[dict[str, Any]]:
    """
    调用 ripgrep，并读取 JSON 格式的搜索结果。
    """
    if not targets:
        return []

    command = build_rg_command(
        keyword=keyword,
        targets=targets,
        avoid_dirs=avoid_dirs,
    )

    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except FileNotFoundError:
        raise RuntimeError("未找到 rg 命令，请先安装 ripgrep：brew install ripgrep")

    if result.returncode == 1:
        return []

    if result.returncode != 0:
        return []

    matches = []

    for line in result.stdout.splitlines():
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue

        if item.get("type") != "match":
            continue

        data = item.get("data", {})
        path_text = data.get("path", {}).get("text", "")
        line_number = data.get("line_number", 0)
        line_text = data.get("lines", {}).get("text", "").rstrip()

        if path_text and line_number:
            matches.append(
                {
                    "path": path_text,
                    "line_number": line_number,
                    "line_text": line_text,
                    "keyword": keyword,
                }
            )

    return matches


def score_match(
    repo_path: Path,
    match: dict[str, Any],
    plan: dict[str, Any],
    is_primary: bool,
) -> int:
    """
    给搜索结果打分，优先保留更可能是核心源码的结果。
    """
    file_path = Path(match["path"])

    try:
        relative_path = str(file_path.relative_to(repo_path))
    except ValueError:
        relative_path = str(file_path)

    path = Path(relative_path)
    parts = set(path.parts)
    file_name = path.name
    suffix = path.suffix

    score = 0

    if is_primary:
        score += 40

    if relative_path in plan.get("focus_files", []):
        score += 120

    if parts & set(plan.get("focus_dirs", [])):
        score += 80

    if suffix in CODE_SUFFIXES:
        score += 50

    if file_name in IMPORTANT_FILE_NAMES:
        score += 60

    if "store" in file_name or "task" in file_name or "session" in file_name:
        score += 30

    if parts & LOW_VALUE_DIRS:
        score -= 80

    if file_name.lower().startswith("readme"):
        score -= 50

    if suffix in {".md", ".txt", ".rst"}:
        score -= 60

    if match["keyword"].lower() in match["line_text"].lower():
        score += 20

    return score


def search_terms_in_targets(
    repo_path: Path,
    terms: list[str],
    targets: list[Path],
    avoid_dirs: list[str],
    plan: dict[str, Any],
    is_primary: bool,
) -> list[dict[str, Any]]:
    """
    在指定文件或目录中搜索关键词。
    """
    results = []

    for term in terms:
        matches = run_rg_json(
            keyword=term,
            targets=targets,
            avoid_dirs=avoid_dirs,
        )

        for match in matches:
            file_path = Path(match["path"])

            try:
                relative_path = str(file_path.relative_to(repo_path))
            except ValueError:
                relative_path = str(file_path)

            if not should_keep_match(relative_path, plan):
                continue

            score = score_match(
                repo_path=repo_path,
                match=match,
                plan=plan,
                is_primary=is_primary,
            )

            results.append(
                {
                    "relative_path": relative_path,
                    "absolute_path": str(file_path),
                    "line_number": match["line_number"],
                    "line_text": match["line_text"],
                    "keyword": term,
                    "score": score,
                }
            )

    return results


def collect_matches(repo_path: Path, plan: dict[str, Any]) -> list[dict[str, Any]]:
    """
    根据搜索计划执行多轮搜索：
    1. 优先搜重点文件
    2. 再搜重点目录
    3. 不够再搜整个仓库
    4. 最后使用兜底关键词
    """
    primary_terms = plan.get("primary_terms", [])
    fallback_terms = plan.get("fallback_terms", [])
    avoid_dirs = plan.get("avoid_dirs", [])

    focus_files = resolve_focus_files(repo_path, plan.get("focus_files", []))
    focus_dirs = resolve_focus_dirs(repo_path, plan.get("focus_dirs", []))

    matches = []

    if focus_files and primary_terms:
        matches.extend(
            search_terms_in_targets(
                repo_path=repo_path,
                terms=primary_terms,
                targets=focus_files,
                avoid_dirs=avoid_dirs,
                plan=plan,
                is_primary=True,
            )
        )

    if len(matches) < 4 and focus_dirs and primary_terms:
        matches.extend(
            search_terms_in_targets(
                repo_path=repo_path,
                terms=primary_terms,
                targets=focus_dirs,
                avoid_dirs=avoid_dirs,
                plan=plan,
                is_primary=True,
            )
        )

    if len(matches) < 4 and primary_terms:
        matches.extend(
            search_terms_in_targets(
                repo_path=repo_path,
                terms=primary_terms,
                targets=[repo_path],
                avoid_dirs=avoid_dirs,
                plan=plan,
                is_primary=True,
            )
        )

    if len(matches) < 4 and fallback_terms:
        targets = focus_dirs if focus_dirs else [repo_path]

        matches.extend(
            search_terms_in_targets(
                repo_path=repo_path,
                terms=fallback_terms,
                targets=targets,
                avoid_dirs=avoid_dirs,
                plan=plan,
                is_primary=False,
            )
        )

    return deduplicate_and_rank(matches)


def deduplicate_and_rank(matches: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    去重并按分数排序。
    """
    seen = set()
    unique = []

    for match in matches:
        key = (
            match["relative_path"],
            match["line_number"],
            match["keyword"],
        )

        if key in seen:
            continue

        seen.add(key)
        unique.append(match)

    unique.sort(key=lambda item: item["score"], reverse=True)
    return unique


def build_search_context(
    matches: list[dict[str, Any]],
    max_snippets: int = 8,
    max_per_file: int = 2,
    max_chars: int = 12000,
) -> str:
    """
    将搜索命中结果整理成给大模型使用的上下文。

    这里不只取命中行前后几行，
    而是调用 context_builder 提取完整函数或较完整代码块。
    """
    if not matches:
        return ""

    file_count = defaultdict(int)
    sections = []
    total_chars = 0

    for match in matches:
        relative_path = match["relative_path"]

        if file_count[relative_path] >= max_per_file:
            continue

        code_block = extract_context_block(
            file_path=match["absolute_path"],
            line_number=match["line_number"],
        )

        section = (
            f"## 文件：{relative_path}\n"
            f"- 命中关键词：{match['keyword']}\n"
            f"- 命中行号：{match['line_number']}\n\n"
            f"```text\n{code_block}\n```"
        )

        if total_chars + len(section) > max_chars:
            break

        sections.append(section)
        total_chars += len(section)
        file_count[relative_path] += 1

        if len(sections) >= max_snippets:
            break

    return "\n\n".join(sections)


def search_code_with_plan(
    repo_path: str | Path,
    plan: dict[str, Any],
) -> str:
    """
    对外主函数：根据搜索计划检索相关代码上下文。
    """
    repo_path = Path(repo_path)

    if not repo_path.exists():
        raise FileNotFoundError(f"仓库路径不存在：{repo_path}")

    matches = collect_matches(repo_path, plan)
    context = build_search_context(matches)

    if not context:
        terms = plan.get("primary_terms", []) + plan.get("fallback_terms", [])
        return f"没有找到相关代码片段。搜索词：{', '.join(terms)}"

    header = (
        f"搜索意图：{plan.get('intent', '')}\n"
        f"主要搜索词：{', '.join(plan.get('primary_terms', []))}\n"
        f"兜底搜索词：{', '.join(plan.get('fallback_terms', []))}\n\n"
    )

    return header + context