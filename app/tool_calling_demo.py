import os
from app.chroma_indexer import search_chroma
from dotenv import load_dotenv
from pathlib import Path
from langchain_openai import ChatOpenAI
from langchain_core.tools import tool
from langgraph.graph import StateGraph, START, END, MessagesState
from langgraph.prebuilt import ToolNode, tools_condition

load_dotenv()

model = ChatOpenAI(
    model="deepseek-chat",
    base_url="https://api.deepseek.com",
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    temperature=0,
)

REPO_PATH = "data/repos/squad"

chroma_dir = Path(REPO_PATH) / ".repomind" / "chroma"

if not chroma_dir.exists():
    raise RuntimeError(f"Chroma 索引不存在，请先构建索引：{chroma_dir}")

def make_repo_search_tool(repo_path: str):
    @tool
    def repo_search_tool(query: str) -> str:
        """Search the current repository for relevant code or documentation."""
        return search_chroma(
            repo_path=repo_path,
            query=query,
            top_k=5,
        )
    return repo_search_tool

repo_search_tool = make_repo_search_tool(REPO_PATH)

GENERATE_PROMPT = (
    "你是一个代码仓库的问答助手。"
    "请基于下面这个检索结果回答用户问题，如果检索不足就说不知道\n\n"
    "用户问题：{question}\n\n"
    "检索结果：{context}"
)

def generate_answer(state: MessagesState):
    question = state["messages"][0].content
    
    context = "\n\n".join(
        message.content
        for message in state["messages"]
        if message.type == "tool"
    )

    prompt = GENERATE_PROMPT.format(
        question = question,
        context = context,
    )

    response = model.invoke([
        {"role": "user", "content": prompt}
    ])

    return {"messages": [response]}



def agent_node(state: MessagesState):
    response = model.bind_tools([repo_search_tool]).invoke(state["messages"])
    return {"messages": [response]}

workflow = StateGraph(MessagesState)

workflow.add_node("agent", agent_node)
workflow.add_node("tools", ToolNode([repo_search_tool]))
workflow.add_node("generate_answer", generate_answer)

workflow.add_edge(START, "agent")
workflow.add_conditional_edges(
    "agent",
    tools_condition,
    {
        "tools": "tools",
        END: END,
    }
)

workflow.add_edge("tools", "generate_answer")
workflow.add_edge("generate_answer",END)

graph = workflow.compile()

if __name__ == "__main__":
    input_state = {
        "messages": [
            {
                "role": "user",
                "content": "这个项目的 MCP workflow 是怎么设计的？",
            }
        ]
    }

    for chunk in graph.stream(input_state):
        for node_name, update in chunk.items():
            print(f"\n--- 来自节点：{node_name} ---")
            update["messages"][-1].pretty_print()
            