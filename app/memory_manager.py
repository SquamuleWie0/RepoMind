# 管理多轮对话记忆：负责保存最近对话，生成记忆上下文，压缩较早的对话（最近问答，摘要，关键结论）

import re
from .llm_client import ask_deepseek

MAX_RECENT_TURNS = 5
SUMMARY_TRIGGER_TURNS = 8
KEEP_RECENT_TURNS = 4


def create_memory_state() -> dict:
    return {
        "recent_turns": [],
        "conversation_summary": "",
        "key_findings": [],
    }


def clean_text(text: str) -> str:
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def build_memory_context(memory_state: dict | None) -> str:
    if not memory_state:
        return "暂无历史对话。"

    parts = []

    summary = memory_state.get("conversation_summary", "")
    if summary:
        parts.append(f"【较早对话摘要】\n{summary}")

    key_findings = memory_state.get("key_findings", [])
    if key_findings:
        findings_text = "\n".join(f"- {item}" for item in key_findings)
        parts.append(f"【已确认的关键结论】\n{findings_text}")

    recent_turns = memory_state.get("recent_turns", [])
    if recent_turns:
        recent_text = []
        for turn in recent_turns[-MAX_RECENT_TURNS:]:
            recent_text.append(
                f"用户：{turn.get('question', '')}\n"
                f"RepoMind：{turn.get('answer', '')}"
            )
        parts.append("【最近对话】\n" + "\n\n".join(recent_text))

    if not parts:
        return "暂无历史对话。"

    return "\n\n".join(parts)


def summarize_old_turns(memory_state: dict) -> None:
    recent_turns = memory_state.get("recent_turns", [])

    if len(recent_turns) <= SUMMARY_TRIGGER_TURNS:
        return

    old_turns = recent_turns[:-KEEP_RECENT_TURNS]
    kept_turns = recent_turns[-KEEP_RECENT_TURNS:]

    old_text = []
    for turn in old_turns:
        old_text.append(
            f"用户：{turn.get('question', '')}\n"
            f"RepoMind：{turn.get('answer', '')}"
        )

    previous_summary = memory_state.get("conversation_summary", "")

    prompt = f"""
你是一个对话记忆整理助手。

请把下面较早的项目问答压缩成简洁摘要，用于后续多轮对话理解。
不要写成报告，不要太长，只保留用户关注点、已经讨论过的结论、后续追问可能需要的背景。

已有摘要：

{previous_summary}

需要压缩的较早对话：

{chr(10).join(old_text)}

输出要求：
- 控制在 150 到 300 字
- 用自然语言总结
- 不要编造
"""

    summary = ask_deepseek(prompt)

    memory_state["conversation_summary"] = clean_text(summary)
    memory_state["recent_turns"] = kept_turns


def add_turn(memory_state: dict, question: str, answer: str) -> dict:
    memory_state.setdefault("recent_turns", [])
    memory_state.setdefault("conversation_summary", "")
    memory_state.setdefault("key_findings", [])

    memory_state["recent_turns"].append(
        {
            "question": question,
            "answer": answer,
        }
    )

    summarize_old_turns(memory_state)
    return memory_state


def add_key_finding(memory_state: dict, finding: str) -> dict:
    memory_state.setdefault("key_findings", [])

    finding = finding.strip()

    if finding and finding not in memory_state["key_findings"]:
        memory_state["key_findings"].append(finding)

    memory_state["key_findings"] = memory_state["key_findings"][-10:]
    return memory_state