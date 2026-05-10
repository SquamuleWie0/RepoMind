# 把 file_tree + analysis_result + key_files 传给 LLM
# 生成 AI 项目导读

import json
import re
from .llm_client import ask_deepseek

def truncate_text(text: str, max_chars: int = 2200) -> str:
    """
    限制单个文件内容长度，避免传给模型的内容过长。
    """
    if len(text) <= max_chars:
        return text

    return text[:max_chars] + "\n\n[内容过长，已截断]"


def clean_markdown(text: str) -> str:
    """
    清理大模型返回的 Markdown，减少连续空行。
    """
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def build_key_files_context(key_files: dict[str, str], max_files: int = 8) -> str:
    """
    将关键文件内容整理成适合发给大模型的文本。
    """
    parts = []

    for index, (file_path, content) in enumerate(key_files.items()):
        if index >= max_files:
            break

        file_block = (
            f"\n### 文件：{file_path}\n\n"
            f"{truncate_text(content)}\n"
        )
        parts.append(file_block)

    return "\n".join(parts)


def build_analysis_prompt(
    file_tree: str,
    analysis_result: dict,
    key_files: dict[str, str],
) -> str:
    """
    构造发送给大模型的项目导读 Prompt。
    """
    analysis_json = json.dumps(
        analysis_result,
        ensure_ascii=False,
        indent=2,
    )

    key_files_context = build_key_files_context(key_files)
    project_name = analysis_result.get("project_name", "unknown")

    prompt = f"""
你是一个有经验的软件工程师，也是一名擅长带学习者理解开源项目的开发导师。

请基于下面的项目材料，写一篇“像人写的开源项目导读文章”。

你的目标不是生成模板化报告，也不是把仓库信息全部罗列出来。
你的目标是帮助一个编程学习者用较低成本理解这个项目：
它是什么、核心思路是什么、值得关注什么、如果想继续学习可以怎么尝试。

请严格基于我提供的文件树、规则分析结果和关键文件内容进行分析。
如果信息不足，请明确说明是推测，不要编造。

====================
规则分析结果
====================

{analysis_json}

====================
项目文件树
====================

{file_tree}

====================
关键文件内容
====================

{key_files_context}

写作要求：

- 写成自然的项目导读文章，不要写成机械报告。
- 语言要像一个懂项目的人在给学习者讲解，清楚、直接、有判断。
- 不要写成论文、百科、简历项目介绍或 AI 总结。
- 不要展示完整文件树。
- 不要机械罗列所有目录和文件。
- 不要把报告写成“源码阅读路线”。
- 文件路径只作为辅助指引出现，不要成为文章主线。
- 技术栈不要堆名词，要说明它们在项目中承担什么作用。
- 不要给过于激进的操作建议，不要要求用户立刻完整复刻或大规模改造项目。
- 建议使用“可以尝试”“如果想进一步理解”“如果项目容易运行，可以……”这类温和表达。
- 信息密度要高，但不要冗长。
- 总字数控制在 900 到 1300 字。
- 每段尽量不超过 4 行。
- 不要连续出现多个空行。
- 少用项目符号，只有在学习尝试建议中需要时再使用。

文章标题：

# {project_name} 项目导读

文章请自然围绕以下内容展开，不一定每个都写成死板标题：

一、这个项目在做什么

先用通俗但专业的话讲清楚：
这个项目是什么，它解决什么问题，适合什么类型的学习者关注。
不要太抽象，要让用户第一时间建立方向感。

二、它的核心思路是什么

抓住项目最重要的设计主线。
不要罗列所有模块，而是解释这个项目背后最关键的组织方式或运行机制。

三、从用户视角看，它大概怎么使用

说明用户大概如何和这个项目交互，它提供了哪些核心能力。
不要陷入源码细节，先帮助用户理解“这个东西用起来是什么样”。

四、从开发者视角看，它大概怎么拆

解释项目背后的核心组成。
可以提到入口、数据层、配置、任务、命令、核心模块等，但只讲最影响理解主线的部分。
文件路径可以作为依据出现，但不要写成文件清单。

五、如果想继续理解它，可以怎么尝试

这一节不要写成死板的“阅读顺序”。
请给出温和、低压力、可选择的学习尝试建议，例如：

- 先理解它解决的问题；
- 如果项目容易运行，可以尝试走一个最小使用流程；
- 带着这个流程回到关键代码里找实现；
- 如果想进一步学习，可以做一个很小的实验或简化复刻。

注意：建议要小、具体、可尝试，不要好高骛远。

六、如果想做一个简化版

给一个小而可行的 Demo 方向。
说明应该保留什么核心能力，哪些复杂部分可以先删掉。
不要建议完整复刻原项目。

七、当前分析边界

简短说明当前分析主要基于文件树和部分关键文件。
如果用户想了解更细节的问题，可以后续通过代码问答继续追问。
"""

    return prompt


def generate_llm_report(
    file_tree: str,
    analysis_result: dict,
    key_files: dict[str, str],
) -> str:
    """
    对外主函数：调用大模型生成项目导读文章。
    """
    prompt = build_analysis_prompt(
        file_tree=file_tree,
        analysis_result=analysis_result,
        key_files=key_files,
    )

    report = ask_deepseek(prompt)
    return clean_markdown(report)