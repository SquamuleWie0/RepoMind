import json
from pathlib import Path
from typing import TypedDict, Annotated, Literal

from pydantic import BaseModel, Field
from langchain_core.tools import tool
from langgraph.graph import StateGraph, END, START
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition

from .langchain_llm import ask_with_langchain, get_deepseek_llm
from .chroma_indexer import search_chroma_with_sources

tool_calling_model = get_deepseek_llm()

class RepoMindState(TypedDict, total=False):
    repo_path: str
    question: str
    file_tree: str
    analysis_result: dict
    memory_context: str
    messages: Annotated[list, add_messages]
    sources: list[str]

    retrieved_context: str

    is_relevant: bool
    grade_reason: str
    rewritten_question: str
    rewrite_count: int
    original_question: str

    answer: str

class GradeDocuments(BaseModel):
    """Evaluate whether retrieved context is relevant and sufficient."""

    is_relevant: bool = Field(
        description="Whether the retrieved context is relevant and sufficient to answer the user question."
    )
    reason: str = Field(
        description="Brief reason explaining why the context is or is not sufficient."
    )

def make_chroma_search_tool(repo_path: str):
    @tool
    def chroma_search_tool(query: str) -> str:
        """Search the current repository with Chroma semantic retrieval."""
        result = search_chroma_with_sources(
            repo_path=repo_path,
            query=query,
            top_k=6,
        )

        return json.dumps(result, ensure_ascii=False)
    
    return chroma_search_tool

def make_agent_node(chroma_tool):
    def agent_node(state: RepoMindState) -> RepoMindState:
        question = state["question"]

        messages = [
            {
                "role": "system",
                "content": (
                    "你是 RepoMind，一个代码仓库理解 Agent。"
                    "如果用户问题涉及具体代码、实现、文件、调用关系，请调用 chroma_search_tool 检索项目。"
                    "如果问题不需要查看代码，可以直接回答。"
                ),
            },
            {
                "role": "user",
                "content": question,
            },
        ]

        response = tool_calling_model.bind_tools([chroma_tool]).invoke(messages)

        print("[Agent] question:", question)
        print("[Agent] tool_calls:", getattr(response, "tool_calls", []))

        return {
            "messages": [response],
        }

    return agent_node

def collect_tool_context_node(state: RepoMindState) -> RepoMindState:
    messages = state.get("messages", [])

    contexts = []
    sources = []

    for message in messages:
        if getattr(message, "type", None) != "tool":
            continue

        try:
            data = json.loads(message.content)
        except Exception:
            contexts.append(message.content)
            continue

        context = data.get("context", "")
        tool_sources = data.get("sources", [])

        if context:
            contexts.append(context)

        for source in tool_sources:
            if source not in sources:
                sources.append(source)

    retrieved_context = "\n\n".join(contexts).strip()

    if not retrieved_context:
        retrieved_context = "没有检索到相关上下文。"


    print("[Collect] context length:", len(retrieved_context))
    print("[Collect] sources:", sources)

    return {
        **state,
        "retrieved_context": retrieved_context,
        "sources": sources,
    }

def grade_documents_node(state: RepoMindState) -> RepoMindState:
    question = state.get("original_question", state["question"])
    current_query = state["question"]
    retrieved_context = state.get("retrieved_context", "")

    prompt = f"""
你是 RepoMind 的检索结果评估器。

你的任务是判断检索上下文是否足够回答用户原始问题。

用户原始问题：
{question}

当前检索问题：
{current_query}

检索上下文：
{retrieved_context[:8000]}

请只返回 JSON，不要输出多余解释。

JSON 格式如下：
{{
  "is_relevant": true,
  "reason": "简短说明判断原因"
}}

判断标准：
- 如果检索上下文和用户问题明显相关，并且足够支持回答，is_relevant=true。
- 如果检索上下文为空、明显跑题、只包含无关内容，is_relevant=false。
- 不要因为缺少很细的行号就轻易判 false。
"""

    response = tool_calling_model.invoke(
        [{"role": "user", "content": prompt}]
    )

    raw_text = response.content.strip()

    try:
        data = json.loads(raw_text)
        grade = GradeDocuments(**data)
        is_relevant = grade.is_relevant
        reason = grade.reason
    except Exception:
        is_relevant = False
        reason = f"检索评估 JSON 解析失败，原始输出：{raw_text[:300]}"

    print("[Grade] is_relevant:", is_relevant)
    print("[Grade] reason:", reason)

    return {
        **state,
        "is_relevant": is_relevant,
        "grade_reason": reason,
    }

def decide_after_grade(state: RepoMindState) -> Literal["answer", "rewrite_question"]:
    if state.get("is_relevant", False):
        return "answer"

    if state.get("rewrite_count", 0) >= 1:
        return "answer"

    return "rewrite_question"


def rewrite_question_node(state: RepoMindState) -> RepoMindState:
    original_question = state.get("original_question", state["question"])
    current_query = state["question"]
    retrieved_context = state.get("retrieved_context", "")
    grade_reason = state.get("grade_reason", "")
    rewrite_count = state.get("rewrite_count", 0)

    prompt = f"""
你是 RepoMind 的代码仓库检索问题改写器。

用户原始问题：
{original_question}

当前检索问题：
{current_query}

上一次检索结果评估原因：
{grade_reason}

上一次检索上下文摘要：
{retrieved_context[:3000]}

请把问题改写成更适合代码仓库语义检索的问题。

要求：
- 保留用户原始意图。
- 更具体地描述可能涉及的模块、文件、函数、流程、类名、配置或关键词。
- 不要回答问题。
- 只输出改写后的检索问题。
"""

    response = tool_calling_model.invoke(
        [{"role": "user", "content": prompt}]
    )

    rewritten_question = response.content.strip()

    print("[Rewrite] rewritten_question:", rewritten_question)
    
    return {
        **state,
        "question": rewritten_question,
        "rewritten_question": rewritten_question,
        "rewrite_count": rewrite_count + 1,
        "retrieved_context": "",
        "sources": [],
    }

def direct_answer_node(state: RepoMindState) -> RepoMindState:
    messages = state.get("messages", [])

    if not messages:
        return {
            **state,
            "answer": "",
        }

    last_message = messages[-1]
    answer = getattr(last_message, "content", "")

    print("[DirectAnswer] answer length:", len(answer))

    return {
        **state,
        "answer": answer.strip(),
    }

def answer_node(state: RepoMindState) -> RepoMindState:
    user_question = state.get("original_question", state["question"])
    current_query = state["question"]

    sources = state.get("sources", [])

    sources_text = (
        "\n".join(f"- {source}" for source in sources)
        if sources
        else "无"
    )

    prompt = f"""
你是 RepoMind，一个 GitHub 项目理解 Agent。

用户原始问题：
{user_question}

当前检索问题：
{current_query}

对话记忆：
{state.get("memory_context", "")}

项目分析结果：
{json.dumps(state.get("analysis_result", {}), ensure_ascii=False, indent=2)}

检索上下文：
{state.get("retrieved_context", "")}

参考来源文件：
{sources_text}

回答要求：
- 第一句直接回答问题，不要寒暄。
- 优先基于检索上下文回答。
- 优先通俗解释，不要堆术语。
- 如果适合流程说明，可以用 A → B → C。
- 如果适合建议，可以用简短列表。
- 不要编造检索上下文里没有依据的实现。
- 如果检索上下文不足以回答，请明确说不知道。
- 如果参考来源文件不是“无”，回答末尾必须包含“参考文件”小节。
- “参考文件”只能使用上方“参考来源文件”中列出的文件，不要编造文件名。
- 控制在 150 到 400 字。
"""

    answer = ask_with_langchain(prompt)

    print("[Answer] answer length:", len(answer))

    return {
        **state,
        "answer": answer.strip(),
    }

def build_repomind_graph(repo_path: str | Path):
    chroma_tool = make_chroma_search_tool(str(repo_path))

    graph = StateGraph(RepoMindState)

    graph.add_node("agent", make_agent_node(chroma_tool))
    graph.add_node("tools", ToolNode([chroma_tool]))
    graph.add_node("collect_context", collect_tool_context_node)
    graph.add_node("grade_documents", grade_documents_node)
    graph.add_node("rewrite_question", rewrite_question_node)
    graph.add_node("direct_answer", direct_answer_node)
    graph.add_node("answer", answer_node)

    graph.add_edge(START, "agent")

    graph.add_conditional_edges(
        "agent",
        tools_condition,
        {
            "tools": "tools",
            END: "direct_answer",
        },
    )

    graph.add_edge("tools", "collect_context")
    graph.add_edge("collect_context", "grade_documents")

    graph.add_conditional_edges(
        "grade_documents",
        decide_after_grade,
        {
            "answer": "answer",
            "rewrite_question": "rewrite_question",
        },
    )

    graph.add_edge("rewrite_question", "agent")
    graph.add_edge("direct_answer", END)
    graph.add_edge("answer", END)

    return graph.compile()

def answer_with_langgraph(
    repo_path: str | Path,
    question: str,
    file_tree: str = "",
    analysis_result: dict | None = None,
    memory_context: str = "",
) -> str:
    app = build_repomind_graph(repo_path)

    result = app.invoke(
        {
            "repo_path": str(repo_path),
            "question": question,
            "file_tree": file_tree,
            "analysis_result": analysis_result or {},
            "memory_context": memory_context,
            "original_question": question,
            "sources": [],
            "rewrite_count": 0,
            "messages": [
                {
                    "role": "user",
                    "content": question,
                }
            ],
        }
    )

    return result.get("answer", "").strip()

if __name__ == "__main__":
    answer = answer_with_langgraph(
        repo_path="data/repos/squad",
        question="这个项目的 MCP workflow 是怎么设计的？",
    )
    print(answer)