import json
import re
from typing import Any

from llm_client import ask_deepseek


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


def normalize_plan(plan: dict[str, Any], requirement: str) -> dict[str, Any]:
    return {
        "intent": str(plan.get("intent") or requirement).strip(),
        "change_type": str(plan.get("change_type") or "unknown").strip(),
        "affected_areas": plan.get("affected_areas") if isinstance(plan.get("affected_areas"), list) else [],
        "search_hints": plan.get("search_hints") if isinstance(plan.get("search_hints"), list) else [],
        "suggested_steps": plan.get("suggested_steps") if isinstance(plan.get("suggested_steps"), list) else [],
        "risks": plan.get("risks") if isinstance(plan.get("risks"), list) else [],
        "can_generate_patch": bool(plan.get("can_generate_patch", True)),
        "reason": str(plan.get("reason") or "需求明确，可以尝试生成最小 patch。").strip(),
    }


def fallback_dev_plan(requirement: str) -> dict[str, Any]:
    """
    当 LLM 没有返回稳定 JSON 时，用规则兜底。
    避免明确需求被错误拦截。
    """
    lower = requirement.lower()

    search_hints = []
    affected_areas = []
    suggested_steps = []
    change_type = "unknown"

    if "version" in lower or "版本" in requirement:
        change_type = "add_feature"
        affected_areas = ["CLI 入口", "命令分发", "项目版本信息"]
        search_hints = [
            "main.rs",
            "clap",
            "command",
            "cmd",
            "version",
            "Cargo.toml",
            "CARGO_PKG_VERSION",
            "match",
        ]
        suggested_steps = [
            "找到 CLI 命令分发入口",
            "新增 version 命令分支",
            "从 Cargo.toml 或环境宏中读取版本号",
            "输出项目名称和版本",
        ]

    elif "增加" in requirement or "新增" in requirement or "add" in lower:
        change_type = "add_feature"
        search_hints = ["main", "command", "cmd", "handler", "route"]
        suggested_steps = ["定位入口逻辑", "找到相关处理函数", "做最小功能修改"]

    elif "修复" in requirement or "bug" in lower or "报错" in requirement:
        change_type = "fix_bug"
        search_hints = ["error", "result", "handler", "test"]
        suggested_steps = ["定位报错相关模块", "找到失败路径", "做最小修复"]

    can_generate_patch = bool(search_hints)

    return {
        "intent": requirement,
        "change_type": change_type,
        "affected_areas": affected_areas,
        "search_hints": search_hints,
        "suggested_steps": suggested_steps,
        "risks": [
            "这是规则兜底生成的开发计划，patch 仍需要 git apply --check 检查。"
        ],
        "can_generate_patch": can_generate_patch,
        "reason": "LLM 开发计划 JSON 解析失败，已根据明确需求使用规则兜底。",
    }


def create_dev_plan(
    requirement: str,
    file_tree: str = "",
    analysis_result: dict | None = None,
    memory_context: str = "",
) -> dict[str, Any]:
    analysis_json = json.dumps(
        analysis_result or {},
        ensure_ascii=False,
        indent=2,
    )

    file_tree_preview = file_tree[:5000]

    prompt = f"""
你是 RepoMind 的二次开发规划助手。

用户提出了一个修改需求。你的任务不是直接写代码，而是先分析：
- 用户真正想改什么
- 可能影响哪些模块
- 应该先看哪些位置
- 修改风险是什么
- 是否适合生成 patch

用户需求：

{requirement}

对话记忆上下文：

{memory_context}

项目规则分析结果：

{analysis_json}

项目文件树摘要：

{file_tree_preview}

请只返回 JSON，不要输出 Markdown，不要解释。

JSON 格式：

{{
  "intent": "一句话说明用户想实现什么",
  "change_type": "add_feature",
  "affected_areas": ["可能受影响的模块或功能"],
  "search_hints": ["后续检索代码时建议搜索的关键词"],
  "suggested_steps": ["建议修改步骤"],
  "risks": ["可能风险"],
  "can_generate_patch": true,
  "reason": "为什么可以或不适合生成 patch"
}}

要求：
- 只要用户需求包含明确的修改目标，就尽量设置 can_generate_patch=true。
- 不要因为需要进一步确认细节就拒绝生成 patch。
- 可以先生成最小可行修改方案。
- 只有当用户需求完全无法判断要改什么时，才设置 can_generate_patch=false。
- 优先给最小可行修改路径。
- search_hints 尽量使用代码里可能出现的英文词、模块名、函数名。
- 如果用户要求新增 CLI 命令，优先搜索 main、cmd、command、clap、version、Cargo.toml 等关键词。
"""

    response = ask_deepseek(prompt)

    try:
        raw_plan = extract_json_from_text(response)
        return normalize_plan(raw_plan, requirement)
    except Exception:
        return fallback_dev_plan(requirement)