# 负责克隆仓库，把GitHub项目拿到本地

from pathlib import Path
from git import Repo


def validate_repo_url(repo_url: str) -> None:
    """检查 GitHub URL 是否基本合法"""
    if not repo_url:
        raise ValueError("GitHub URL 不能为空")

    if not repo_url.startswith("https://github.com/"):
        raise ValueError("目前只支持 https://github.com/ 开头的 GitHub 仓库地址")


def get_repo_name(repo_url: str) -> str:
    """从 GitHub URL 中提取仓库名"""
    repo_name = repo_url.rstrip("/").split("/")[-1]

    if repo_name.endswith(".git"):
        repo_name = repo_name[:-4]

    if not repo_name:
        raise ValueError("无法从 URL 中提取仓库名")

    return repo_name


def get_target_path(repo_url: str, base_dir: str = "data/repos") -> Path:
    """生成仓库本地保存路径"""
    repo_name = get_repo_name(repo_url)

    base_path = Path(base_dir)
    base_path.mkdir(parents=True, exist_ok=True)

    return base_path / repo_name


def clone_repo(repo_url: str, base_dir: str = "data/repos") -> Path:
    """克隆 GitHub 仓库到本地"""
    validate_repo_url(repo_url)

    target_path = get_target_path(repo_url, base_dir)

    if target_path.exists():
        print(f"仓库已存在：{target_path}")
        return target_path

    print(f"正在克隆仓库：{repo_url}")
    Repo.clone_from(repo_url, target_path)

    print(f"克隆完成：{target_path}")
    return target_path