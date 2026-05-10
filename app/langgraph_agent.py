import json
from pathlib import Path
from typing import TypedDict, Annotated

from langchain_core.tools import tool
from langgraph.graph import StateGraph, END, START
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition

from .langchain_llm import ask_with_langchain, get_deepseek_llm
from .chroma_indexer import search_chroma

tool_calling_model = get_deepseek_llm()

class RepoMindState(TypedDict, total=False):
    repo_path: str
    question: str
    file_tree: str
    analysis_result: dict
    memory_context: str
    messages: Annotated[list, add_messages] 

    route: str
    needs_retrieval: bool
    retrieval_method: str

    search_plan: dict
    retrieved_context: str
    is_sufficient: bool

    answer: str

def make_chroma_search_tool(repo_path: str):
    @tool
    def chroma_search_tool(query: str) -> str:
        """Search the current repository with Chroma semantic retrieval."""
        return search_chroma(
            repo_path=repo_path,
            query=query,
            top_k=6,
        )

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

        return {
            "messages": [response],
        }

    return agent_node

def collect_tool_context_node(state: RepoMindState) -> RepoMindState:
    messages = state.get("messages", [])

    tool_context = "\n\n".join(
        message.content
        for message in messages
        if getattr(message, "type", None) == "tool"
    )

    if not tool_context:
        tool_context = "没有检索到相关上下文。"

    return {
        **state,
        "retrieved_context": tool_context,
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

    return {
        **state,
        "answer": answer.strip(),
    }

def answer_node(state: RepoMindState) -> RepoMindState:
    prompt = f"""
你是 RepoMind，一个 GitHub 项目理解 Agent。

用户问题：
{state["question"]}

对话记忆：
{state.get("memory_context", "")}

项目分析结果：
{json.dumps(state.get("analysis_result", {}), ensure_ascii=False, indent=2)}

检索上下文：
{state.get("retrieved_context", "")}

回答要求：
- 第一句直接回答问题，不要寒暄。
- 优先通俗解释，不要堆术语。
- 如果适合流程说明，可以用 A → B → C。
- 如果适合建议，可以用简短列表。
- 不要编造上下文里没有依据的实现。
- 控制在 150 到 400 字。
"""

    answer = ask_with_langchain(prompt)

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
    graph.add_edge("collect_context", "answer")
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