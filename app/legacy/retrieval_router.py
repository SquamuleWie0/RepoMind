# 判断用哪种检索方式
import json
import re
from typing import Any

from llm_client import ask_deepseek


DEFAULT_RETRIEVAL_ROUTE = {
    "method": "hybrid",
    "semantic_query": "",
    "reason": "默认使用混合检索。",
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


def normalize_retrieval_route(data: dict[str, Any], question: str) -> dict[str, Any]:
    result = DEFAULT_RETRIEVAL_ROUTE.copy()

    method = str(data.get("method", "")).strip()

    if method in {"rg", "vector", "hybrid"}:
        result["method"] = method

    result["semantic_query"] = str(data.get("semantic_query", "")).strip()

    if not result["semantic_query"]:
        result["semantic_query"] = question

    result["reason"] = str(data.get("reason", result["reason"])).strip()[:120]

    return result


def build_retrieval_route_prompt(
    question: str,
    route_info: dict,
    analysis_result: dict | None = None,
    memory_context: str = "",
) -> str:
    analysis_json = json.dumps(
        analysis_result or {},
        ensure_ascii=False,
        indent=2,
    )

    route_json = json.dumps(
        route_info or {},
        ensure_ascii=False,
        indent=2,
    )

    return f"""
你是 RepoMind 的检索方式路由器。

你的任务不是回答用户问题，而是判断这次应该使用哪种检索方式。

用户问题：

{question}

问题类型判断：

{route_json}

对话记忆上下文：

{memory_context}

项目规则分析结果：

{analysis_json}

请只返回 JSON，不要输出 Markdown，不要解释。

JSON 格式：

{{
  "method": "rg | vector | hybrid",
  "semantic_query": "用于向量检索的改写查询，尽量使用英文代码词、模块词、技术词",
  "reason": "一句话说明为什么这样选择"
}}

判断标准：

1. rg
适合明确代码符号、函数名、文件名、命令名、SQL、报错、变量名、结构体名。

2. vector
适合语义理解问题，例如项目机制、设计思路、模块关系、学习价值、架构难点。

3. hybrid
适合既需要理解机制，又需要结合具体实现的问题。

要求：
- 不要所有问题都选 hybrid。
- 如果用户明确问具体代码位置，优先 rg。
- 如果用户问抽象机制、设计、难点，优先 vector。
- 如果问题里同时包含“机制”和“代码里怎么体现”，选 hybrid。
- semantic_query 要适合语义检索，比如：task storage sqlite store TaskRecord，而不是整句中文。
"""


def route_retrieval(
    question: str,
    route_info: dict,
    analysis_result: dict | None = None,
    memory_context: str = "",
) -> dict[str, Any]:
    prompt = build_retrieval_route_prompt(
        question=question,
        route_info=route_info,
        analysis_result=analysis_result,
        memory_context=memory_context,
    )

    response = ask_deepseek(prompt)

    try:
        data = extract_json_from_text(response)
        return normalize_retrieval_route(data, question)
    except Exception:
        return DEFAULT_RETRIEVAL_ROUTE.copy()