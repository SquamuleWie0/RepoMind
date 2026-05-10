# 用规则分析结果生成基础的markdown报告
from pathlib import Path
from datetime import datetime


def format_list(items: list[str]) -> str:
    if not items:
        return "- 暂未识别"
    return "\n".join(f"- {item}" for item in items)


def generate_markdown_report(
    analysis_result: dict,
    file_tree: str,
    key_files: dict[str, str],
) -> str:
    project_name = analysis_result.get("project_name", "unknown")
    project_type = analysis_result.get("project_type", "未知类型")
    tech_stack = analysis_result.get("tech_stack", [])
    total_files = analysis_result.get("total_files", 0)

    tech_stack_text = ", ".join(tech_stack) if tech_stack else "暂未识别"
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    lines = [
        f"# {project_name} 项目理解报告",
        "",
        f"生成时间：{current_time}",
        "",
        "---",
        "",
        "## 1. 项目基础信息",
        "",
        f"- 项目名称：{project_name}",
        f"- 项目类型：{project_type}",
        f"- 技术栈：{tech_stack_text}",
        f"- 文件总数：{total_files}",
        "",
        "---",
        "",
        "## 2. 入口文件",
        "",
        format_list(analysis_result.get("entry_files", [])),
        "",
        "---",
        "",
        "## 3. 依赖 / 配置文件",
        "",
        format_list(analysis_result.get("dependency_files", [])),
        "",
        "---",
        "",
        "## 4. 核心目录",
        "",
        format_list(analysis_result.get("core_dirs", [])),
        "",
        "---",
        "",
        "## 5. 关键文件",
        "",
        format_list(analysis_result.get("key_files", [])),
        "",
        "---",
        "",
        "## 6. 项目文件树",
        "",
        "```text",
        file_tree,
        "```",
        "",
        "---",
        "",
        "## 7. 初步阅读建议",
        "",
        "1. 先阅读 README，了解项目目标和使用方式。",
        "2. 再阅读依赖 / 配置文件，了解技术栈和运行环境。",
        "3. 接着阅读入口文件，理解程序从哪里启动。",
        "4. 最后阅读核心目录，理解主要模块和业务逻辑。",
        "",
        "---",
        "",
        "## 8. 当前分析说明",
        "",
        "当前报告主要基于规则分析生成，包括文件名、目录结构、依赖文件和入口文件判断。",
        "",
        "后续接入大模型后，可以进一步生成更深入的项目定位、核心流程、模块职责、运行逻辑和二次开发建议。",
        "",
    ]

    return "\n".join(lines)


def save_report(
    report: str,
    project_name: str,
    output_dir: str = "data/reports",
) -> Path:
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    report_path = output_path / f"{project_name}_report.md"
    report_path.write_text(report, encoding="utf-8")

    return report_path