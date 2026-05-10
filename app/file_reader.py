# 筛选并读取关键文件的内容

from pathlib import Path


HIGH_PRIORITY_FILES = {
    "README.md",
    "README.zh-CN.md",
    "requirements.txt",
    "pyproject.toml",
    "package.json",
    "Cargo.toml",
    "setup.py",
    ".env.example",
}

ENTRY_FILES = {
    "main.py",
    "app.py",
    "server.py",
    "manage.py",
    "index.js",
    "main.rs",
    "lib.rs",
}

CORE_DIRS = {
    "src",
    "app",
    "api",
    "routes",
    "services",
    "models",
    "core",
}

TEXT_EXTENSIONS = {
    ".py",
    ".js",
    ".ts",
    ".rs",
    ".go",
    ".java",
    ".md",
    ".txt",
    ".toml",
    ".json",
    ".yaml",
    ".yml",
    ".env",
    ".sh",
}


def is_text_file(file_path: Path) -> bool:
    """
    判断文件是否是适合读取的文本文件
    """
    return file_path.suffix in TEXT_EXTENSIONS or file_path.name in HIGH_PRIORITY_FILES


def score_file(file_path: Path, repo_path: str) -> int:
    """
    给文件打分，分数越高越值得优先读取
    """
    score = 0
    relative_path = file_path.relative_to(repo_path)
    parts = relative_path.parts
    filename = file_path.name

    if filename in HIGH_PRIORITY_FILES:
        score += 100

    if filename in ENTRY_FILES:
        score += 80

    if any(part in CORE_DIRS for part in parts):
        score += 60

    if "test" in parts or "tests" in parts:
        score -= 20

    if "docs" in parts:
        score -= 10

    if file_path.stat().st_size > 50 * 1024:
        score -= 30

    if not is_text_file(file_path):
        score -= 100

    return score


def select_key_files(file_paths: list[Path], repo_path: str, max_files: int = 15) -> list[Path]:
    """
    从文件列表中筛选最值得读取的关键文件
    """
    scored_files = []

    for file_path in file_paths:
        if not file_path.is_file():
            continue

        score = score_file(file_path, repo_path)

        if score > 0:
            scored_files.append((score, file_path))

    scored_files.sort(key=lambda item: item[0], reverse=True)

    return [file_path for score, file_path in scored_files[:max_files]]


def read_file_safely(file_path: Path, max_chars: int = 6000) -> str:
    """
    安全读取文件内容，避免读取过大文件
    """
    try:
        content = file_path.read_text(encoding="utf-8", errors="ignore")
        return content[:max_chars]
    except Exception as e:
        return f"[读取失败：{e}]"


def read_key_files(file_paths: list[Path], repo_path: str, max_files: int = 15) -> dict[str, str]:
    """
    读取关键文件内容，返回 {相对路径: 文件内容}
    """
    key_files = select_key_files(file_paths, repo_path, max_files=max_files)

    result = {}

    for file_path in key_files:
        relative_path = str(file_path.relative_to(repo_path))
        result[relative_path] = read_file_safely(file_path)

    return result