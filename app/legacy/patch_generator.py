import difflib
import json
import re
from pathlib import Path
from typing import Any

from llm_client import ask_deepseek
from query_planner import create_search_plan
from code_searcher import search_code_with_plan


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


def is_safe_relative_path(file_path: str) -> bool:
    path = Path(file_path)

    if path.is_absolute():
        return False

    if ".." in path.parts:
        return False

    return True


def build_patch_context(
    repo_path: str | Path,
    requirement: str,
    dev_plan: dict,
    file_tree: str = "",
    analysis_result: dict | None = None,
) -> str:
    search_text = requirement + "\n" + json.dumps(
        dev_plan,
        ensure_ascii=False,
        indent=2,
    )

    search_plan = create_search_plan(
        question=search_text,
        file_tree=file_tree,
        analysis_result=analysis_result,
    )

    hints = dev_plan.get("search_hints", [])
    if hints:
        current_terms = search_plan.get("primary_terms", [])
        for hint in hints:
            hint = str(hint).strip()
            if hint and hint not in current_terms:
                current_terms.append(hint)
        search_plan["primary_terms"] = current_terms[:8]

    return search_code_with_plan(
        repo_path=repo_path,
        plan=search_plan,
    )


def create_edit_plan(
    requirement: str,
    dev_plan: dict,
    code_context: str,
) -> dict[str, Any]:
    prompt = f"""
你是 RepoMind 的代码修改规划助手。

你不能直接输出 diff patch。
你只能输出 JSON，描述要修改哪个文件、把哪段旧代码替换成哪段新代码。

用户需求：

{requirement}

开发计划：

{json.dumps(dev_plan, ensure_ascii=False, indent=2)}

相关真实代码上下文：

{code_context}

请只返回 JSON，不要输出 Markdown，不要解释。

JSON 格式：

{{
  "can_edit": true,
  "reason": "一句话说明为什么可以或不可以修改",
  "edits": [
    {{
      "file_path": "相对项目根目录的文件路径",
      "old_text": "需要被替换的原始代码，必须从上下文中精确复制",
      "new_text": "替换后的新代码"
    }}
  ]
}}

要求：

- old_text 必须是目标文件中真实存在的一整段文本。
- 不要自己编造 old_text。
- 如果无法确定旧代码原文，设置 can_edit=false。
- 修改要尽量小。
- 不要输出 diff。
- 不要输出解释。
- 如果是 Rust match 分支，注意分支之间通常需要逗号。
- 如果用户要求新增 CLI 命令，优先修改命令分发的 match / command 处理逻辑。
"""

    response = ask_deepseek(prompt)

    try:
        return extract_json_from_text(response)
    except Exception:
        return {
            "can_edit": False,
            "reason": "无法解析模型返回的修改计划。",
            "edits": [],
        }


def apply_edits_to_files(
    repo_path: str | Path,
    edit_plan: dict[str, Any],
) -> tuple[bool, str, dict[str, tuple[str, str]]]:
    """
    不直接写入文件，只在内存中生成修改后的内容。
    返回：
    - 是否成功
    - 错误原因
    - {relative_path: (old_content, new_content)}
    """
    repo_path = Path(repo_path)
    changed_files: dict[str, tuple[str, str]] = {}

    if not edit_plan.get("can_edit", False):
        return False, edit_plan.get("reason", "模型判断不适合修改。"), {}

    edits = edit_plan.get("edits", [])

    if not edits:
        return False, "修改计划中没有 edits。", {}

    for edit in edits:
        file_path = str(edit.get("file_path", "")).strip()
        old_text = str(edit.get("old_text", ""))
        new_text = str(edit.get("new_text", ""))

        if not file_path:
            return False, "edit 缺少 file_path。", {}

        if not is_safe_relative_path(file_path):
            return False, f"不安全的文件路径：{file_path}", {}

        if not old_text:
            return False, f"{file_path} 缺少 old_text。", {}

        target_path = repo_path / file_path

        if not target_path.exists():
            return False, f"目标文件不存在：{file_path}", {}

        old_content = target_path.read_text(encoding="utf-8", errors="ignore")

        if file_path in changed_files:
            base_old_content, current_content = changed_files[file_path]
        else:
            base_old_content = old_content
            current_content = old_content

        if old_text not in current_content:
            return False, f"在 {file_path} 中没有找到 old_text，无法安全生成 patch。", {}

        updated_content = current_content.replace(old_text, new_text, 1)
        changed_files[file_path] = (base_old_content, updated_content)

    return True, "", changed_files


def build_unified_diff(
    changed_files: dict[str, tuple[str, str]],
) -> str:
    patches = []

    for file_path, (old_content, new_content) in changed_files.items():
        old_lines = old_content.splitlines(keepends=True)
        new_lines = new_content.splitlines(keepends=True)

        diff_lines = difflib.unified_diff(
            old_lines,
            new_lines,
            fromfile=f"a/{file_path}",
            tofile=f"b/{file_path}",
        )

        patch = "".join(diff_lines)
        if patch.strip():
            patches.append(patch)

    return "\n".join(patches).strip()


def generate_patch(
    repo_path: str | Path,
    requirement: str,
    dev_plan: dict,
    code_context: str,
) -> str:
    """
    生成 patch 的稳定版：
    1. LLM 只负责生成 JSON 修改计划
    2. Python 读取真实文件
    3. Python 替换文本
    4. Python 生成标准 unified diff
    """
    edit_plan = create_edit_plan(
        requirement=requirement,
        dev_plan=dev_plan,
        code_context=code_context,
    )

    ok, reason, changed_files = apply_edits_to_files(
        repo_path=repo_path,
        edit_plan=edit_plan,
    )

    if not ok:
        return f"CANNOT_GENERATE_PATCH: {reason}"

    patch_text = build_unified_diff(changed_files)

    if not patch_text:
        return "CANNOT_GENERATE_PATCH: 修改后没有生成有效 diff。"

    return patch_text