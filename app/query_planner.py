# 如果需要查询代码，让LLM生成检索计划
import json
import re
from typing import Any

from .llm_client import ask_deepseek


DEFAULT_PLAN = {
    "intent": "理解用户问题",
    "primary_terms": [],
    "fallback_terms": [],
    "focus_files": [],
    "focus_dirs": ["src", "app", "api", "routes", "services", "models", "core"],
    "avoid_dirs": ["docs", "tests", "test", ".github", "target", "node_modules", ".git"],
    "reason": "默认优先搜索源码目录。",
}


def extract_json_from_text(text: str) -> dict[str, Any]:
    text = text.strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    match = re.search(r"\{[\s\S]*\}", text)
    if not match:
        raise ValueError("大模型返回内容中没有找到 JSON")

    return json.loads(match.group(0))


def normalize_list(value: Any, limit: int) -> list[str]:
    if not isinstance(value, list):
        return []

    result = []
    for item in value:
        item = str(item).strip()
        if item and item not in result:
            result.append(item)

    return result[:limit]


def normalize_search_plan(plan: dict[str, Any]) -> dict[str, Any]:
    normalized = DEFAULT_PLAN.copy()

    # 兼容旧字段 search_terms
    if "search_terms" in plan and "primary_terms" not in plan:
        plan["primary_terms"] = plan["search_terms"]

    normalized["intent"] = str(plan.get("intent", normalized["intent"])).strip()[:60]
    normalized["primary_terms"] = normalize_list(plan.get("primary_terms", []), 5)
    normalized["fallback_terms"] = normalize_list(plan.get("fallback_terms", []), 4)
    normalized["focus_files"] = normalize_list(plan.get("focus_files", []), 5)
    normalized["focus_dirs"] = normalize_list(plan.get("focus_dirs", normalized["focus_dirs"]), 5)
    normalized["avoid_dirs"] = normalize_list(plan.get("avoid_dirs", normalized["avoid_dirs"]), 8)
    normalized["reason"] = str(plan.get("reason", normalized["reason"])).strip()[:100]

    return normalized


def build_query_plan_prompt(
    question: str,
    file_tree: str = "",
    analysis_result: dict | None = None,
) -> str:
    analysis_json = json.dumps(
        analysis_result or {},
        ensure_ascii=False,
        indent=2,
    )

    return f"""
你是一个代码检索规划助手。

用户正在理解一个 GitHub 项目。你的任务不是回答问题，而是把用户问题转成一个精简的代码搜索计划，供程序后续使用 ripgrep 搜索本地仓库。

用户问题：
{question}

项目规则分析结果：
{analysis_json}

项目文件树：
{file_tree}

请只返回 JSON，不要输出 Markdown，不要解释。

JSON 格式如下：

{{
  "intent": "用一句话说明用户真正想了解什么",
  "primary_terms": ["第一轮优先搜索的关键词，3 到 5 个，尽量是代码符号、函数名、结构体名、文件名、库名"],
  "fallback_terms": ["第一轮不够时再搜索的兜底关键词，0 到 4 个"],
  "focus_files": ["如果能从文件树判断出重点文件，就写相对路径；不能确定就留空"],
  "focus_dirs": ["优先搜索的目录，通常 1 到 3 个"],
  "avoid_dirs": ["应避开的目录，例如 docs、tests、target"],
  "reason": "用一句话说明为什么这样搜"
}}

要求：
- primary_terms 要精炼，不要超过 5 个。
- 优先给接近代码真实写法的关键词，例如 TaskRecord、store、INSERT、execute、rusqlite。
- 不要把抽象中文句子放进 primary_terms。
- fallback_terms 用于兜底，可以稍微宽泛一点。
- focus_files 不要乱猜，只有从文件树能看出来时再写。
- focus_dirs 不要泛泛列很多，优先只写最可能相关的目录。
- reason 控制在一句话内。
"""


def create_search_plan(
    question: str,
    file_tree: str = "",
    analysis_result: dict | None = None,
) -> dict[str, Any]:
    prompt = build_query_plan_prompt(
        question=question,
        file_tree=file_tree,
        analysis_result=analysis_result,
    )

    response = ask_deepseek(prompt)

    try:
        plan = extract_json_from_text(response)
        return normalize_search_plan(plan)
    except Exception:
        fallback = DEFAULT_PLAN.copy()
        fallback["intent"] = "搜索计划解析失败"
        fallback["reason"] = "大模型返回内容无法解析，使用默认策略。"
        return fallback