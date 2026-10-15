from datetime import datetime
import json

from .db import SessionLocal
from .db_models import LearningNote, Project


def serialize_learning_note(note: LearningNote) -> dict:
    try:
        sources = json.loads(note.sources_json or "[]")
    except Exception:
        sources = []

    return {
        "id": note.id,
        "project_id": note.project_id,
        "title": note.title or "项目学习记录",
        "content": note.content or "",
        "sources": sources,
        "created_at": note.created_at.isoformat(),
        "updated_at": note.updated_at.isoformat(),
    }


def add_learning_note(
    project_id: int,
    title: str,
    content: str,
    sources: list[str] | None = None,
) -> dict | None:
    db = SessionLocal()

    try:
        project = db.query(Project).filter(Project.id == project_id).first()

        if project is None:
            return None

        note = LearningNote(
            project_id=project_id,
            title=title or "项目学习记录",
            content=content or "",
            sources_json=json.dumps(sources or [], ensure_ascii=False),
        )

        db.add(note)
        db.commit()
        db.refresh(note)

        return serialize_learning_note(note)

    finally:
        db.close()


def list_learning_notes(project_id: int) -> list[dict]:
    db = SessionLocal()

    try:
        notes = (
            db.query(LearningNote)
            .filter(LearningNote.project_id == project_id)
            .order_by(LearningNote.updated_at.desc())
            .all()
        )

        return [serialize_learning_note(note) for note in notes]

    finally:
        db.close()


def update_learning_note(
    project_id: int,
    note_id: int,
    title: str | None = None,
    content: str | None = None,
) -> dict | None:
    db = SessionLocal()

    try:
        note = (
            db.query(LearningNote)
            .filter(
                LearningNote.id == note_id,
                LearningNote.project_id == project_id,
            )
            .first()
        )

        if note is None:
            return None

        if title is not None:
            note.title = title

        if content is not None:
            note.content = content

        note.updated_at = datetime.utcnow()

        db.commit()
        db.refresh(note)

        return serialize_learning_note(note)

    finally:
        db.close()


def delete_learning_note(project_id: int, note_id: int) -> bool:
    db = SessionLocal()

    try:
        note = (
            db.query(LearningNote)
            .filter(
                LearningNote.id == note_id,
                LearningNote.project_id == project_id,
            )
            .first()
        )

        if note is None:
            return False

        db.delete(note)
        db.commit()

        return True

    finally:
        db.close()