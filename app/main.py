# 命令行版本，主要用于测试流程

from repo_loader import clone_repo
from file_scanner import scan_repo, scan_and_build_tree
from file_reader import read_key_files
from repo_analyzer import analyze_repo
from report_generator import generate_markdown_report, save_report
from llm_analyzer import generate_llm_report
from qa_agent import answer_question


def analyze_project(repo_url: str):
    """
    完整项目分析流程：
    GitHub URL -> 克隆仓库 -> 扫描文件 -> 读取关键文件 -> 规则分析 -> 生成报告
    """
    print("\n正在准备项目...")

    repo_path = clone_repo(repo_url)
    print(f"仓库路径：{repo_path}")

    print("\n正在扫描项目结构...")
    file_tree = scan_and_build_tree(str(repo_path))
    files = scan_repo(str(repo_path))
    print(f"扫描完成，文件数量：{len(files)}")

    print("\n正在读取关键文件...")
    key_files = read_key_files(files, str(repo_path))
    print(f"已读取关键文件数量：{len(key_files)}")

    print("\n正在进行规则分析...")
    analysis_result = analyze_repo(repo_path, files, key_files)
    print(f"项目类型：{analysis_result.get('project_type')}")
    print(f"技术栈：{analysis_result.get('tech_stack')}")

    print("\n正在生成基础报告...")
    basic_report = generate_markdown_report(
        analysis_result=analysis_result,
        file_tree=file_tree,
        key_files=key_files,
    )

    basic_report_path = save_report(
        report=basic_report,
        project_name=analysis_result["project_name"],
    )

    print(f"基础报告已保存到：{basic_report_path}")

    print("\n正在调用大模型生成项目导读，请稍等...")
    ai_report = generate_llm_report(
        file_tree=file_tree,
        analysis_result=analysis_result,
        key_files=key_files,
    )

    ai_report_path = save_report(
        report=ai_report,
        project_name=f"{analysis_result['project_name']}_ai",
    )

    print(f"AI 项目导读已保存到：{ai_report_path}")

    return repo_path, file_tree, analysis_result


def start_qa_loop(repo_path, file_tree: str, analysis_result: dict):
    """
    项目问答模式：
    用户可以围绕当前项目连续提问。
    """
    print("\n现在可以开始围绕这个项目提问。")
    print("输入 q / quit / exit 退出。\n")

    while True:
        question = input("你想问这个项目什么？：").strip()

        if question.lower() in {"q", "quit", "exit"}:
            print("已退出 RepoMind。")
            break

        if not question:
            continue

        print("\n正在检索项目上下文并生成回答，请稍等...\n")

        answer = answer_question(
            repo_path=repo_path,
            question=question,
            file_tree=file_tree,
            analysis_result=analysis_result,
        )

        print("RepoMind：")
        print(answer)
        print()


def main():
    print("欢迎使用 RepoMind")
    print("当前流程：输入 GitHub URL -> 生成项目导读 -> 进入项目问答\n")

    repo_url = input("请输入 GitHub 仓库 URL：").strip()

    repo_path, file_tree, analysis_result = analyze_project(repo_url)

    start_qa_loop(
        repo_path=repo_path,
        file_tree=file_tree,
        analysis_result=analysis_result,
    )


if __name__ == "__main__":
    main()