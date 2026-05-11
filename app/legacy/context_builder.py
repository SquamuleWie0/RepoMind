# 把搜到的命中行扩展成更完整的函数或代码块


import re
from pathlib import Path


BRACE_LANGUAGE_SUFFIXES = {
    ".rs",
    ".js",
    ".ts",
    ".go",
    ".java",
    ".cpp",
    ".c",
    ".jsx",
    ".tsx",
}


def read_lines(file_path: str | Path) -> list[str]:
    file_path = Path(file_path)
    return file_path.read_text(encoding="utf-8", errors="ignore").splitlines()


def fallback_window(
    lines: list[str],
    line_number: int,
    context_lines: int = 80,
) -> str:
    """
    兜底方案：读取命中行前后若干行。
    """
    start = max(line_number - context_lines - 1, 0)
    end = min(line_number + context_lines, len(lines))

    return format_lines(lines, start, end, highlight_line=line_number)


def format_lines(
    lines: list[str],
    start: int,
    end: int,
    highlight_line: int | None = None,
) -> str:
    result = []

    for index in range(start, end):
        current_line = index + 1
        prefix = ">" if current_line == highlight_line else " "
        result.append(f"{prefix} {current_line}: {lines[index]}")

    return "\n".join(result)


def find_brace_block_start(lines: list[str], line_index: int) -> int | None:
    """
    向上寻找函数、方法、impl、class 等代码块起点。
    主要适合 Rust / JS / Go / Java 这类大括号语言。
    """
    patterns = [
        r"^\s*(pub\s+)?(async\s+)?fn\s+\w+",
        r"^\s*fn\s+\w+",
        r"^\s*impl\b",
        r"^\s*struct\b",
        r"^\s*enum\b",
        r"^\s*function\s+\w+",
        r"^\s*(export\s+)?(async\s+)?function\s+\w+",
        r"^\s*(public|private|protected)?\s*\w+.*\(",
    ]

    for index in range(line_index, -1, -1):
        line = lines[index]

        for pattern in patterns:
            if re.search(pattern, line):
                return index

    return None


def extract_brace_block(lines: list[str], line_number: int) -> str:
    """
    提取大括号语言中的完整函数/代码块。
    """
    line_index = line_number - 1
    start = find_brace_block_start(lines, line_index)

    if start is None:
        return fallback_window(lines, line_number)

    brace_count = 0
    found_open_brace = False
    end = start

    for index in range(start, len(lines)):
        line = lines[index]

        brace_count += line.count("{")
        brace_count -= line.count("}")

        if "{" in line:
            found_open_brace = True

        end = index

        if found_open_brace and brace_count == 0:
            break

    # 防止代码块过短或识别失败
    if end <= start:
        return fallback_window(lines, line_number)

    return format_lines(lines, start, end + 1, highlight_line=line_number)


def find_python_block_start(lines: list[str], line_index: int) -> int | None:
    """
    向上寻找 Python def/class 起点。
    """
    for index in range(line_index, -1, -1):
        line = lines[index]

        if re.match(r"^\s*(def|class)\s+\w+", line):
            return index

    return None


def extract_python_block(lines: list[str], line_number: int) -> str:
    """
    提取 Python 函数或类代码块。
    """
    line_index = line_number - 1
    start = find_python_block_start(lines, line_index)

    if start is None:
        return fallback_window(lines, line_number)

    start_indent = len(lines[start]) - len(lines[start].lstrip())
    end = start + 1

    for index in range(start + 1, len(lines)):
        line = lines[index]

        if not line.strip():
            end = index + 1
            continue

        current_indent = len(line) - len(line.lstrip())

        if current_indent <= start_indent:
            break

        end = index + 1

    return format_lines(lines, start, end, highlight_line=line_number)


def extract_context_block(
    file_path: str | Path,
    line_number: int,
) -> str:
    """
    根据文件路径和命中行号，提取更完整的上下文代码块。
    优先提取完整函数/代码块，失败时回退到前后窗口。
    """
    file_path = Path(file_path)

    try:
        lines = read_lines(file_path)
    except Exception as e:
        return f"[读取文件失败：{e}]"

    suffix = file_path.suffix

    if suffix == ".py":
        return extract_python_block(lines, line_number)

    if suffix in BRACE_LANGUAGE_SUFFIXES:
        return extract_brace_block(lines, line_number)

    return fallback_window(lines, line_number)