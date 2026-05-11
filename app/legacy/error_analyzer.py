import json

from llm_client import ask_deepseek


def analyze_error(
    error_text: str,
    command: str = "",
    file_tree: str = "",
    analysis_result: dict | None = None,
    memory_context: str = "",
) -> str:
    analysis_json = json.dumps(
        analysis_result or {},
        ensure_ascii=False,
        indent=2,
    )

    file_tree_preview = file_tree[:5000]

    prompt = f"""
你是 RepoMind 的运行错误分析助手。

用户在运行项目时遇到了错误。请结合项目上下文分析可能原因，并给出排查建议。

命令：

{command}

错误信息：

{error_text}

对话记忆上下文：

{memory_context}

项目规则分析结果：

{analysis_json}

项目文件树摘要：

{file_tree_preview}

回答要求：

- 第一句话直接说明最可能的问题方向。
- 不要寒暄，不要写成报告。
- 先解释错误大概是什么意思。
- 再给 2 到 4 个排查步骤。
- 如果不能确定，就说明还需要哪些信息。
- 不要编造项目里不存在的文件或命令。
- 回答要简洁、实用。
"""

    return ask_deepseek(prompt).strip()
