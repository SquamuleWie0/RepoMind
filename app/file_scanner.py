# 扫描项目目录，生成文件列表和文件树
from pathlib import Path


IGNORED_DIRS = {
    ".git",
    "__pycache__",
    "node_modules",
    "target",
    "dist",
    "build",
    ".venv",
    "venv",
    ".idea",
    ".vscode",
}

IGNORED_FILES = {
    ".env",
    ".DS_Store",
}


def is_ignored(path: Path) -> bool:
    """
    判断文件或目录是否应该被忽略
    """
    if path.name in IGNORED_DIRS:
        return True

    if path.name in IGNORED_FILES:
        return True

    return False


def scan_repo(repo_path: str) -> list[Path]:
    """
    扫描仓库，返回有效文件路径列表
    """
    root = Path(repo_path)

    if not root.exists():
        raise FileNotFoundError(f"仓库路径不存在：{repo_path}")

    if not root.is_dir():
        raise NotADirectoryError(f"不是有效目录：{repo_path}")

    valid_files = []

    for path in root.rglob("*"):
        if any(part in IGNORED_DIRS for part in path.parts):
            continue

        if is_ignored(path):
            continue

        if path.is_file():
            valid_files.append(path)

    return valid_files


def get_relative_path(file_path: Path, repo_path: str) -> str:
    """
    将文件路径转成相对于仓库根目录的路径
    """
    root = Path(repo_path)
    return str(file_path.relative_to(root))


def build_file_tree(relative_paths: list[str], root_name: str = "repo") -> str:
    """
    根据相对路径生成类似 tree 命令的层级目录结构
    """
    tree = {}

    # 1. 把路径列表转换成嵌套字典
    for path in sorted(relative_paths):
        parts = path.split("/")
        current = tree

        for part in parts:
            current = current.setdefault(part, {})

    # 2. 递归生成树形文本
    def render_tree(node: dict, prefix: str = "") -> list[str]:
        lines = []
        items = list(node.items())

        for index, (name, child) in enumerate(items):
            is_last = index == len(items) - 1
            connector = "└── " if is_last else "├── "
            lines.append(prefix + connector + name)

            if child:
                extension = "    " if is_last else "│   "
                lines.extend(render_tree(child, prefix + extension))

        return lines

    lines = [f"{root_name}/"]
    lines.extend(render_tree(tree))

    return "\n".join(lines)


def scan_and_build_tree(repo_path: str) -> str:
    """
    对外主函数：扫描仓库并生成文件树文本
    """
    root = Path(repo_path)
    files = scan_repo(repo_path)
    relative_paths = [get_relative_path(file, repo_path) for file in files]
    file_tree = build_file_tree(relative_paths, root_name=root.name)

    return file_tree