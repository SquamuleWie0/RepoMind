from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

from .repo_loader import clone_repo
from .llm_analyzer import generate_llm_report
from .file_scanner import scan_repo, scan_and_build_tree
from .file_reader import read_key_files
from .repo_analyzer import analyze_repo
from .report_generator import generate_markdown_report, save_report
from .memory_manager import create_memory_state, build_memory_context, add_turn
from .chroma_indexer import build_chroma_index
from .langgraph_agent import answer_with_langgraph


CURRENT_DIR = Path(__file__).parent
PROJECT_ROOT = CURRENT_DIR.parent
WEB_DIR = PROJECT_ROOT / "web"


app = FastAPI(title="RepoMind API")


class AnalyzeRequest(BaseModel):
    repo_url: str


class AskRequest(BaseModel):
    question: str


CURRENT_PROJECT = {
    "repo_path": None,
    "file_tree": "",
    "analysis_result": {},
    "memory": create_memory_state(),
}


@app.get("/")
def index():
    index_path = WEB_DIR / "index.html"

    if not index_path.exists():
        raise HTTPException(status_code=404, detail="web/index.html 不存在")

    return FileResponse(index_path)


@app.post("/analyze")
def analyze(request: AnalyzeRequest):
    repo_url = request.repo_url.strip()

    if not repo_url:
        raise HTTPException(status_code=400, detail="GitHub URL 不能为空")

    repo_path = clone_repo(repo_url)

    file_tree = scan_and_build_tree(str(repo_path))
    files = scan_repo(str(repo_path))
    key_files = read_key_files(files, str(repo_path))

    analysis_result = analyze_repo(repo_path, files, key_files)

    basic_report = generate_markdown_report(
        analysis_result=analysis_result,
        file_tree=file_tree,
        key_files=key_files,
    )

    ai_report = generate_llm_report(
        file_tree=file_tree,
        analysis_result=analysis_result,
        key_files=key_files,
    )

    ai_report_path = save_report(
        report=ai_report,
        project_name=f"{analysis_result['project_name']}_ai",
    )

    basic_report_path = save_report(
        report=basic_report,
        project_name=analysis_result["project_name"],
    )

    build_chroma_index(repo_path)

    CURRENT_PROJECT["repo_path"] = repo_path
    CURRENT_PROJECT["file_tree"] = file_tree
    CURRENT_PROJECT["analysis_result"] = analysis_result
    CURRENT_PROJECT["memory"] = create_memory_state()

    return {
        "project_name": analysis_result["project_name"],
        "project_type": analysis_result.get("project_type"),
        "tech_stack": analysis_result.get("tech_stack"),
        "basic_report_path": str(basic_report_path),
        "ai_report_path": str(ai_report_path),
        "ai_report": ai_report,
        "chat_history": CURRENT_PROJECT["memory"]["recent_turns"],
        "agent_version": "tool-calling-v1",
    }


@app.post("/ask-v2")
def ask_v2(request: AskRequest):
    question = request.question.strip()

    if not question:
        raise HTTPException(status_code=400, detail="问题不能为空")

    repo_path = CURRENT_PROJECT.get("repo_path")

    if repo_path is None:
        raise HTTPException(status_code=400, detail="请先分析一个 GitHub 项目")

    memory_context = build_memory_context(CURRENT_PROJECT["memory"])

    answer = answer_with_langgraph(
        repo_path=repo_path,
        question=question,
        file_tree=CURRENT_PROJECT["file_tree"],
        analysis_result=CURRENT_PROJECT["analysis_result"],
        memory_context=memory_context,
    )

    add_turn(
        memory_state=CURRENT_PROJECT["memory"],
        question=question,
        answer=answer,
    )

    return {
        "question": question,
        "answer": answer,
        "chat_history": CURRENT_PROJECT["memory"]["recent_turns"],
        "agent_version": "tool-calling-v1",
    }