# 用规则粗略判断项目类型、技术栈、文件入口、依赖文件、核心目录

from pathlib import Path


PROJECT_TYPE_RULES = {
    "Cargo.toml": "Rust 项目",
    "requirements.txt": "Python 项目",
    "pyproject.toml": "Python 项目",
    "package.json": "Node.js 项目",
    "go.mod": "Go 项目",
    "pom.xml": "Java Maven 项目",
}

DEPENDENCY_FILES = {
    "requirements.txt",
    "pyproject.toml",
    "setup.py",
    "package.json",
    "Cargo.toml",
    "go.mod",
    "pom.xml",
    "docker-compose.yml",
    "Dockerfile",
    ".env.example",
}

ENTRY_FILE_NAMES = {
    "main.py",
    "app.py",
    "server.py",
    "manage.py",
    "index.js",
    "index.ts",
    "main.ts",
    "main.rs",
    "lib.rs",
}

CORE_DIR_NAMES = {
    "src",
    "app",
    "api",
    "routes",
    "services",
    "models",
    "core",
    "cmd",
    "internal",
}


def to_relative_paths(file_paths: list[Path], repo_path: str | Path) -> list[str]:
    root = Path(repo_path)
    relative_paths = []

    for file_path in file_paths:
        try:
            relative_paths.append(str(file_path.relative_to(root)))
        except ValueError:
            relative_paths.append(str(file_path))

    return relative_paths


def detect_project_type(relative_paths: list[str]) -> str:
    file_names = {Path(path).name for path in relative_paths}

    for filename, project_type in PROJECT_TYPE_RULES.items():
        if filename in file_names:
            return project_type

    return "未知类型项目"


def detect_tech_stack(relative_paths: list[str]) -> list[str]:
    tech_stack = set()
    file_names = {Path(path).name for path in relative_paths}
    suffixes = {Path(path).suffix for path in relative_paths}

    if "Cargo.toml" in file_names or ".rs" in suffixes:
        tech_stack.add("Rust")
        tech_stack.add("Cargo")

    if "requirements.txt" in file_names or "pyproject.toml" in file_names or ".py" in suffixes:
        tech_stack.add("Python")

    if "package.json" in file_names or ".js" in suffixes or ".ts" in suffixes:
        tech_stack.add("Node.js / JavaScript / TypeScript")

    if "go.mod" in file_names or ".go" in suffixes:
        tech_stack.add("Go")

    if "pom.xml" in file_names or ".java" in suffixes:
        tech_stack.add("Java")

    if "Dockerfile" in file_names or "docker-compose.yml" in file_names:
        tech_stack.add("Docker")

    return sorted(tech_stack)


def find_entry_files(relative_paths: list[str]) -> list[str]:
    entry_files = []

    for path in relative_paths:
        if Path(path).name in ENTRY_FILE_NAMES:
            entry_files.append(path)

    return sorted(entry_files)


def find_dependency_files(relative_paths: list[str]) -> list[str]:
    dependency_files = []

    for path in relative_paths:
        if Path(path).name in DEPENDENCY_FILES:
            dependency_files.append(path)

    return sorted(dependency_files)


def find_core_dirs(relative_paths: list[str]) -> list[str]:
    core_dirs = set()

    for path in relative_paths:
        parts = Path(path).parts

        for part in parts:
            if part in CORE_DIR_NAMES:
                core_dirs.add(part)

    return sorted(core_dirs)


def analyze_repo(
    repo_path: str | Path,
    file_paths: list[Path],
    key_files: dict[str, str],
) -> dict:
    repo_path = Path(repo_path)
    relative_paths = to_relative_paths(file_paths, repo_path)

    return {
        "project_name": repo_path.name,
        "project_type": detect_project_type(relative_paths),
        "tech_stack": detect_tech_stack(relative_paths),
        "entry_files": find_entry_files(relative_paths),
        "dependency_files": find_dependency_files(relative_paths),
        "core_dirs": find_core_dirs(relative_paths),
        "key_files": list(key_files.keys()),
        "total_files": len(relative_paths),
    }