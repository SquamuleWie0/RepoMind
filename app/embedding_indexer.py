# 把项目文件切块，生成向量索引
import math
import re
from collections import Counter
from pathlib import Path


IGNORE_DIRS = {
    ".git",
    "__pycache__",
    "node_modules",
    "target",
    "dist",
    "build",
    ".venv",
    "venv",
}

INDEX_SUFFIXES = {
    ".py",
    ".rs",
    ".js",
    ".ts",
    ".tsx",
    ".jsx",
    ".go",
    ".java",
    ".md",
    ".toml",
    ".json",
    ".yml",
    ".yaml",
}

INDEX_FILE_NAMES = {
    "README",
    "README.md",
    "Cargo.toml",
    "package.json",
    "requirements.txt",
    "pyproject.toml",
    "go.mod",
    "pom.xml",
}

STOP_WORDS = {
    "the", "and", "for", "with", "this", "that", "from", "into",
    "true", "false", "none", "null", "pub", "fn", "let", "use",
}


def should_index_file(file_path: Path) -> bool:
    parts = set(file_path.parts)

    if parts & IGNORE_DIRS:
        return False

    if file_path.name in INDEX_FILE_NAMES:
        return True

    return file_path.suffix in INDEX_SUFFIXES


def tokenize(text: str) -> list[str]:
    """
    轻量本地向量化：把文本拆成 token。
    第一版不是专业 embedding，但可以作为本地语义检索雏形。
    后续可以替换成真正 embedding 模型。
    """
    text = re.sub(r"([a-z])([A-Z])", r"\1 \2", text)
    text = text.replace("_", " ").replace("-", " ")
    tokens = re.findall(r"[a-zA-Z][a-zA-Z0-9]{1,}|[\u4e00-\u9fff]", text.lower())

    return [
        token
        for token in tokens
        if token not in STOP_WORDS and len(token.strip()) > 0
    ]


def vectorize(text: str) -> Counter:
    return Counter(tokenize(text))


def cosine_similarity(vec_a: Counter, vec_b: Counter) -> float:
    if not vec_a or not vec_b:
        return 0.0

    common = set(vec_a.keys()) & set(vec_b.keys())
    dot = sum(vec_a[token] * vec_b[token] for token in common)

    norm_a = math.sqrt(sum(value * value for value in vec_a.values()))
    norm_b = math.sqrt(sum(value * value for value in vec_b.values()))

    if norm_a == 0 or norm_b == 0:
        return 0.0

    return dot / (norm_a * norm_b)


def chunk_lines(lines: list[str], chunk_size: int = 80, overlap: int = 20) -> list[tuple[int, int, str]]:
    chunks = []
    start = 0

    while start < len(lines):
        end = min(start + chunk_size, len(lines))
        content = "\n".join(lines[start:end])

        if content.strip():
            chunks.append((start + 1, end, content))

        if end >= len(lines):
            break

        start = max(end - overlap, start + 1)

    return chunks


def build_vector_index(repo_path: str | Path) -> dict:
    """
    构建本地轻量向量索引。
    保存：文件路径、行号范围、文本块、向量。
    """
    repo_path = Path(repo_path)
    chunks = []

    for file_path in repo_path.rglob("*"):
        if not file_path.is_file():
            continue

        if not should_index_file(file_path):
            continue

        try:
            text = file_path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue

        lines = text.splitlines()

        for start_line, end_line, content in chunk_lines(lines):
            vector = vectorize(content)

            if not vector:
                continue

            try:
                relative_path = str(file_path.relative_to(repo_path))
            except ValueError:
                relative_path = str(file_path)

            chunks.append(
                {
                    "relative_path": relative_path,
                    "absolute_path": str(file_path),
                    "start_line": start_line,
                    "end_line": end_line,
                    "content": content,
                    "vector": vector,
                }
            )

    return {
        "repo_path": str(repo_path),
        "chunks": chunks,
    }