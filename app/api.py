from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel


from .langchain_llm import ask_with_langchain
from .repo_loader import clone_repo
from .llm_analyzer import generate_llm_report
from .file_scanner import scan_repo, scan_and_build_tree
from .file_reader import read_key_files
from .repo_analyzer import analyze_repo
from .report_generator import generate_markdown_report, save_report
from .memory_manager import create_memory_state, build_memory_context, add_turn
from .chroma_indexer import build_chroma_index
from .langgraph_agent import answer_with_langgraph
from .project_store import save_project, add_message, list_projects, get_project, list_messages

from .project_store import (
    add_message,
    delete_message,
    delete_project,
    get_project,
    list_messages,
    list_projects,
    save_project,
)
from .draft_store import get_or_create_draft, update_draft
from .learning_note_store import (
    add_learning_note,
    delete_learning_note,
    list_learning_notes,
    update_learning_note,
)

CURRENT_DIR = Path(__file__).parent
PROJECT_ROOT = CURRENT_DIR.parent
WEB_DIR = PROJECT_ROOT / "web"


app = FastAPI(title="RepoMind API")


class AnalyzeRequest(BaseModel):
    repo_url: str


class AskRequest(BaseModel):
    question: str

class DraftUpdateRequest(BaseModel):
    title: str | None = None
    content: str | None = None
    is_collapsed: bool | None = None


class LearningNoteUpdateRequest(BaseModel):
    title: str | None = None
    content: str | None = None

class LearningNoteCreateRequest(BaseModel):
    title: str = "新的学习记录"
    content: str = "# 新的学习记录\n\n"

CURRENT_PROJECT = {
    "project_id": None,
    "repo_path": None,
    "file_tree": "",
    "ai_report": "",
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

    project_id = save_project(
        repo_url=repo_url,
        project_name=analysis_result["project_name"],
        tech_stack=analysis_result.get("tech_stack"),
        repo_path=str(repo_path),
        file_tree=file_tree,
        analysis_result=analysis_result,
        ai_report=ai_report,
        basic_report=basic_report,
    )

    CURRENT_PROJECT["project_id"] = project_id
    CURRENT_PROJECT["repo_path"] = repo_path
    CURRENT_PROJECT["file_tree"] = file_tree
    CURRENT_PROJECT["analysis_result"] = analysis_result
    CURRENT_PROJECT["ai_report"] = ai_report
    CURRENT_PROJECT["memory"] = create_memory_state()

    return {
        "project_id": project_id,
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
        project_report=CURRENT_PROJECT.get("ai_report", ""),
        memory_context=memory_context,
    )

    add_turn(
        memory_state=CURRENT_PROJECT["memory"],
        question=question,
        answer=answer,
    )

    project_id = CURRENT_PROJECT.get("project_id")

    if project_id is not None:
        add_message(
            project_id=project_id,
            question=question,
            answer=answer,
        )

    return {
        "question": question,
        "answer": answer,
        "chat_history": CURRENT_PROJECT["memory"]["recent_turns"],
        "agent_version": "tool-calling-v1",
    }

@app.get("/projects")
def get_projects_api():
    return {
        "projects": list_projects()
    }


@app.get("/projects/{project_id}")
def get_project_api(project_id: int):
    project = get_project(project_id)

    if project is None:
        raise HTTPException(status_code=404, detail="项目不存在")

    return project


@app.get("/projects/{project_id}/messages")
def get_project_messages_api(project_id: int):
    project = get_project(project_id)

    if project is None:
        raise HTTPException(status_code=404, detail="项目不存在")

    return {
        "messages": list_messages(project_id)
    }

@app.post("/projects/{project_id}/ask")
def ask_project_api(project_id: int, request: AskRequest):
    question = request.question.strip()

    if not question:
        raise HTTPException(status_code=400, detail="问题不能为空")

    project = get_project(project_id)

    if project is None:
        raise HTTPException(status_code=404, detail="项目不存在")

    messages = list_messages(project_id)

    memory_context = "\n\n".join(
        f"用户：{message['question']}\n助手：{message['answer']}"
        for message in messages[-6:]
    )

    answer = answer_with_langgraph(
        repo_path=project["repo_path"],
        question=question,
        file_tree=project["file_tree"],
        analysis_result=project["analysis_result"],
        project_report=project["ai_report"],
        memory_context=memory_context,
    )

    add_message(
        project_id=project_id,
        question=question,
        answer=answer,
    )

    updated_messages = list_messages(project_id)

    return {
        "project_id": project_id,
        "question": question,
        "answer": answer,
        "chat_history": updated_messages,
        "agent_version": "project-history-v1",
    }

@app.get("/projects")
def get_projects():
    return {
        "projects": list_projects()
    }


@app.delete("/projects/{project_id}")
def remove_project(project_id: int):
    ok = delete_project(project_id)

    if not ok:
        raise HTTPException(status_code=404, detail="项目不存在")

    return {
        "ok": True,
        "message": "项目已删除",
        "project_id": project_id,
    }

@app.get("/projects/{project_id}/messages")
def get_project_messages(project_id: int):
    project = get_project(project_id)

    if project is None:
        raise HTTPException(status_code=404, detail="项目不存在")

    return {
        "project_id": project_id,
        "messages": list_messages(project_id),
    }


@app.delete("/projects/{project_id}/messages/{message_id}")
def remove_project_message(project_id: int, message_id: int):
    ok = delete_message(project_id=project_id, message_id=message_id)

    if not ok:
        raise HTTPException(status_code=404, detail="消息不存在")

    return {
        "ok": True,
        "message": "消息已删除",
        "project_id": project_id,
        "message_id": message_id,
    }

@app.get("/projects/{project_id}/draft")
def get_project_draft(project_id: int):
    draft = get_or_create_draft(project_id)

    if draft is None:
        raise HTTPException(status_code=404, detail="项目不存在")

    return draft


@app.patch("/projects/{project_id}/draft")
def update_project_draft(project_id: int, request: DraftUpdateRequest):
    draft = update_draft(
        project_id=project_id,
        title=request.title,
        content=request.content,
        is_collapsed=request.is_collapsed,
    )

    if draft is None:
        raise HTTPException(status_code=404, detail="项目不存在")

    return draft

@app.post("/projects/{project_id}/learning-notes/generate")
def generate_project_learning_note(project_id: int):
    project = get_project(project_id)

    if project is None:
        raise HTTPException(status_code=404, detail="项目不存在")

    draft = get_or_create_draft(project_id)
    messages = list_messages(project_id)

    qa_text = "\n\n".join(
        f"用户问题：{item['question']}\nRepoMind 回答：{item['answer']}"
        for item in messages[-10:]
    )

    draft_content = ""
    if draft:
        draft_content = draft.get("content", "")

    prompt = f"""
你是一个项目学习记录整理助手。

请基于下面的信息，生成一份适合开发者学习复盘的 Markdown 初稿。

要求：
- 不要写成宣传稿。
- 要像真实学习笔记。
- 结构清晰，方便用户继续编辑。
- 如果信息不足，请明确写“待继续确认”。
- 不要编造项目中不存在的实现。
- 输出 Markdown。

建议结构：
# 项目学习记录

## 1. 项目定位

## 2. 技术栈与整体架构

## 3. 核心流程理解

## 4. 我已经理解的关键点

## 5. 仍需要继续看的问题

## 6. 参考文件 / 依据

项目名称：
{project["project_name"]}

项目技术栈：
{project["tech_stack"]}

项目分析结果：
{project["analysis_result"]}

AI 项目导读：
{project["ai_report"]}

用户草稿：
{draft_content}

最近问答：
{qa_text}
"""

    content = ask_with_langchain(prompt)

    note = add_learning_note(
        project_id=project_id,
        title=f"{project['project_name']} 学习记录",
        content=content,
        sources=[],
    )

    if note is None:
        raise HTTPException(status_code=404, detail="项目不存在")

    return note

@app.get("/projects/{project_id}/learning-notes")
def get_project_learning_notes(project_id: int):
    project = get_project(project_id)

    if project is None:
        raise HTTPException(status_code=404, detail="项目不存在")

    return {
        "project_id": project_id,
        "learning_notes": list_learning_notes(project_id),
    }


@app.patch("/projects/{project_id}/learning-notes/{note_id}")
def update_project_learning_note(
    project_id: int,
    note_id: int,
    request: LearningNoteUpdateRequest,
):
    note = update_learning_note(
        project_id=project_id,
        note_id=note_id,
        title=request.title,
        content=request.content,
    )

    if note is None:
        raise HTTPException(status_code=404, detail="学习记录不存在")

    return note


@app.delete("/projects/{project_id}/learning-notes/{note_id}")
def remove_project_learning_note(project_id: int, note_id: int):
    ok = delete_learning_note(project_id=project_id, note_id=note_id)

    if not ok:
        raise HTTPException(status_code=404, detail="学习记录不存在")

    return {
        "ok": True,
        "message": "学习记录已删除",
        "project_id": project_id,
        "note_id": note_id,
    }

@app.post("/projects/{project_id}/learning-notes")
def create_project_learning_note(
    project_id: int,
    request: LearningNoteCreateRequest,
):
    project = get_project(project_id)

    if project is None:
        raise HTTPException(status_code=404, detail="项目不存在")

    note = add_learning_note(
        project_id=project_id,
        title=request.title,
        content=request.content,
        sources=[],
    )

    if note is None:
        raise HTTPException(status_code=404, detail="学习记录创建失败")

    return note