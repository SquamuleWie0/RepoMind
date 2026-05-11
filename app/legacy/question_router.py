# 判断是否需要检索
import json
import re
from typing import Any

from llm_client import ask_deepseek


DEFAULT_ROUTE = {
    "route": "general_understanding",
    "needs_code_search": False,
    "reason": "默认按整体理解问题处理。",
}


def extract_json_from_text(text: str) -> dict[str, Any]:
    text = text.strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    match = re.search(r"\{[\s\S]*\}", text)

    if not match:
        raise ValueError("没有找到 JSON")

    return json.loads(match.group(0))


def normalize_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value

    if isinstance(value, str):
        return value.strip().lower() in {"true", "yes", "1", "需要", "是"}

    return bool(value)


def normalize_route(route: dict[str, Any]) -> dict[str, Any]:
    result = DEFAULT_ROUTE.copy()

    route_name = str(route.get("route", "")).strip()

    if route_name in {"general_understanding", "code_detail", "dev_suggestion"}:
        result["route"] = route_name

    result["needs_code_search"] = normalize_bool(route.get("needs_code_search", False))
    result["reason"] = str(route.get("reason", result["reason"])).strip()[:120]

    return result


def build_route_prompt(
    question: str,
    file_tree: str = "",
    analysis_result: dict | None = None,
    memory_context: str = "",
) -> str:
    analysis_json = json.dumps(
        analysis_result or {},
        ensure_ascii=False,
        indent=2,
    )

    file_tree_preview = file_tree[:4000]

    return f"""
你是 RepoMind 的问题路由器。

你的任务不是回答用户问题，而是判断这个问题应该如何处理。

用户问题：

{question}

对话记忆上下文：

{memory_context}

项目规则分析结果：

{analysis_json}

项目文件树摘要：

{file_tree_preview}

请只返回 JSON，不要输出 Markdown，不要解释。

JSON 格式：

{{
  "route": "general_understanding | code_detail | dev_suggestion",
  "needs_code_search": true,
  "reason": "一句话说明为什么这样判断"
}}

判断标准：

1. general_understanding
用户想理解项目整体、核心难点、技术选型、学习价值、架构思路、项目定位、使用方式。
这类问题通常不需要检索具体源码。

2. code_detail
用户明确想知道具体函数、具体文件、调用链、SQL、报错原因、某段代码在哪里、某个功能具体怎么实现。
这类问题需要检索源码。

3. dev_suggestion
用户想复刻、二次开发、加功能、修改项目、做简化版 Demo、优化项目。
这类问题优先给开发建议；如果涉及具体修改位置，可以设置 needs_code_search 为 true。

重要要求：
- 要结合对话记忆理解“它”“这个设计”“刚才那个模块”等指代。
- 不要只靠关键词判断，要理解用户真正想知道什么。
- 如果用户只是问“怎么存储、怎么协作、核心难点是什么、技术上怎么理解”，优先判断为 general_understanding，除非他明确要具体函数/代码。
- 如果用户问“具体哪个函数、哪一行、哪个文件、SQL 怎么写、调用链是什么”，才判断为 code_detail。
- needs_code_search 表示是否必须检索源码才能回答。
"""


def route_question(
    question: str,
    file_tree: str = "",
    analysis_result: dict | None = None,
    memory_context: str = "",
) -> dict[str, Any]:
    prompt = build_route_prompt(
        question=question,
        file_tree=file_tree,
        analysis_result=analysis_result,
        memory_context=memory_context,
    )

    response = ask_deepseek(prompt)

    try:
        route = extract_json_from_text(response)
        return normalize_route(route)
    except Exception:
        return DEFAULT_ROUTE.copy()