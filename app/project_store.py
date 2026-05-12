from datetime import datetime
import json

from .db import SessionLocal
from .db_models import Project, ProjectMessage


def save_project(
    repo_url: str,
    project_name: str,
    tech_stack,
    repo_path: str,
    file_tree: str,
    analysis_result: dict,
    ai_report: str,
    basic_report: str,
) -> int:
    db = SessionLocal()

    try:
        project = db.query(Project).filter(Project.repo_url == repo_url).first()

        analysis_result_json = json.dumps(
            analysis_result or {},
            ensure_ascii=False,
        )

        if project is None:
            project = Project(
                repo_url=repo_url,
                project_name=project_name,
                tech_stack=str(tech_stack or ""),
                repo_path=str(repo_path),
                file_tree=file_tree or "",
                analysis_result_json=analysis_result_json,
                ai_report=ai_report or "",
                basic_report=basic_report or "",
            )
            db.add(project)
        else:
            project.project_name = project_name
            project.tech_stack = str(tech_stack or "")
            project.repo_path = str(repo_path)
            project.file_tree = file_tree or ""
            project.analysis_result_json = analysis_result_json
            project.ai_report = ai_report or ""
            project.basic_report = basic_report or ""
            project.updated_at = datetime.utcnow()

        db.commit()
        db.refresh(project)

        return project.id

    finally:
        db.close()


def add_message(
    project_id: int,
    question: str,
    answer: str,
) -> None:
    db = SessionLocal()

    try:
        message = ProjectMessage(
            project_id=project_id,
            question=question,
            answer=answer,
        )

        db.add(message)
        db.commit()

    finally:
        db.close()


def list_projects() -> list[dict]:
    db = SessionLocal()

    try:
        projects = (
            db.query(Project)
            .order_by(Project.updated_at.desc())
            .all()
        )

        return [
            {
                "id": project.id,
                "repo_url": project.repo_url,
                "project_name": project.project_name,
                "tech_stack": project.tech_stack,
                "created_at": project.created_at.isoformat(),
                "updated_at": project.updated_at.isoformat(),
            }
            for project in projects
        ]

    finally:
        db.close()


def get_project(project_id: int) -> dict | None:
    db = SessionLocal()

    try:
        project = db.query(Project).filter(Project.id == project_id).first()

        if project is None:
            return None

        try:
            analysis_result = json.loads(project.analysis_result_json or "{}")
        except Exception:
            analysis_result = {}

        return {
            "id": project.id,
            "repo_url": project.repo_url,
            "project_name": project.project_name,
            "tech_stack": project.tech_stack,
            "repo_path": project.repo_path,
            "file_tree": project.file_tree or "",
            "analysis_result": analysis_result,
            "ai_report": project.ai_report or "",
            "basic_report": project.basic_report or "",
            "created_at": project.created_at.isoformat(),
            "updated_at": project.updated_at.isoformat(),
        }

    finally:
        db.close()


def list_messages(project_id: int) -> list[dict]:
    db = SessionLocal()

    try:
        messages = (
            db.query(ProjectMessage)
            .filter(ProjectMessage.project_id == project_id)
            .order_by(ProjectMessage.timestamp.asc())
            .all()
        )

        return [
            {
                "id": message.id,
                "project_id": message.project_id,
                "question": message.question,
                "answer": message.answer,
                "timestamp": message.timestamp.isoformat(),
            }
            for message in messages
        ]

    finally:
        db.close()