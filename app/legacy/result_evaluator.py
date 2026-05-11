# 检索结果自查模块。
# 负责判断 code_searcher 返回的上下文是否足够回答用户问题。
# 如果上下文不足，它会让 LLM 生成第二轮补充搜索计划，
# 再由 qa_agent 触发二次检索，提升回答的可靠性。
import json
import re
from typing import Any

from llm_client import ask_deepseek


DEFAULT_EVALUATION = {
    "is_sufficient": True,
    "reason": "默认认为当前上下文可以用于回答。",
    "missing_info": "",
    "follow_up_plan": {
        "primary_terms": [],
        "fallback_terms": [],
        "focus_files": [],
        "focus_dirs": [],
        "avoid_dirs": ["docs", "tests", "test", ".github", "target", "node_modules", ".git"],
        "reason": "",
    },
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
        return value.strip().lower() in {"true", "yes", "1", "是", "足够"}

    return bool(value)


def normalize_list(value: Any, limit: int) -> list[str]:
    if not isinstance(value, list):
        return []

    result = []

    for item in value:
        item = str(item).strip()
        if item and item not in result:
            result.append(item)

    return result[:limit]


def normalize_evaluation(data: dict[str, Any]) -> dict[str, Any]:
    result = DEFAULT_EVALUATION.copy()

    result["is_sufficient"] = normalize_bool(data.get("is_sufficient", True))
    result["reason"] = str(data.get("reason", "")).strip()[:160]
    result["missing_info"] = str(data.get("missing_info", "")).strip()[:200]

    follow_up = data.get("follow_up_plan", {})
    if not isinstance(follow_up, dict):
        follow_up = {}

    result["follow_up_plan"] = {
        "primary_terms": normalize_list(follow_up.get("primary_terms", []), 5),
        "fallback_terms": normalize_list(follow_up.get("fallback_terms", []), 4),
        "focus_files": normalize_list(follow_up.get("focus_files", []), 5),
        "focus_dirs": normalize_list(follow_up.get("focus_dirs", ["src"]), 5),
        "avoid_dirs": normalize_list(
            follow_up.get(
                "avoid_dirs",
                ["docs", "tests", "test", ".github", "target", "node_modules", ".git"],
            ),
            8,
        ),
        "reason": str(follow_up.get("reason", "")).strip()[:120],
    }

    return result


def build_evaluation_prompt(
    question: str,
    search_plan: dict,
    search_context: str,
) -> str:
    plan_json = json.dumps(
        search_plan,
        ensure_ascii=False,
        indent=2,
    )

    context_preview = search_context[:9000]

    return f"""
你是 RepoMind 的检索结果评估器。

你的任务不是回答用户问题，而是判断当前检索到的项目上下文是否足够支持回答。

用户问题：

{question}

本轮搜索计划：

{plan_json}

检索到的上下文：

{context_preview}

请只返回 JSON，不要输出 Markdown，不要解释。

JSON 格式：

{{
  "is_sufficient": true,
  "reason": "一句话说明当前上下文是否足够",
  "missing_info": "如果不足，缺少什么信息；如果足够，留空",
  "follow_up_plan": {{
    "primary_terms": ["如果不足，下一轮优先搜索词，3 到 5 个"],
    "fallback_terms": ["兜底搜索词，0 到 4 个"],
    "focus_files": ["如果能判断重点文件，写相对路径"],
    "focus_dirs": ["优先搜索目录"],
    "avoid_dirs": ["应避开的目录"],
    "reason": "为什么这样补搜"
  }}
}}

判断标准：

- 如果已经能回答用户问题的主要意思，就判断 is_sufficient 为 true。
- 不要为了追求具体函数、具体行号而过度判定不足。
- 如果用户问的是概念、机制、技术方案，只要上下文能支持机制级回答，就算足够。
- 只有当缺少关键信息会导致回答明显不可靠时，才判断不足。
- 如果不足，follow_up_plan 要给更精炼、更接近代码符号的搜索词。
- follow_up_plan 的搜索词不要太多，不要放抽象中文句子。
"""


def evaluate_search_result(
    question: str,
    search_plan: dict,
    search_context: str,
) -> dict[str, Any]:
    if not search_context or "没有找到相关代码片段" in search_context:
        return {
            "is_sufficient": False,
            "reason": "当前没有检索到有效代码上下文。",
            "missing_info": "缺少能支撑回答的相关代码片段。",
            "follow_up_plan": {
                "primary_terms": search_plan.get("fallback_terms", [])[:5],
                "fallback_terms": search_plan.get("primary_terms", [])[:4],
                "focus_files": search_plan.get("focus_files", []),
                "focus_dirs": search_plan.get("focus_dirs", ["src"]),
                "avoid_dirs": search_plan.get(
                    "avoid_dirs",
                    ["docs", "tests", "test", ".github", "target", "node_modules", ".git"],
                ),
                "reason": "首轮没有找到有效结果，交换主关键词和兜底词再尝试一次。",
            },
        }

    prompt = build_evaluation_prompt(
        question=question,
        search_plan=search_plan,
        search_context=search_context,
    )

    response = ask_deepseek(prompt)

    try:
        data = extract_json_from_text(response)
        return normalize_evaluation(data)
    except Exception:
        return DEFAULT_EVALUATION.copy()