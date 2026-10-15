from datetime import datetime

from .db import SessionLocal
from .db_models import DraftNote, Project


def serialize_draft(draft: DraftNote) -> dict:
    return {
        "id": draft.id,
        "project_id": draft.project_id,
        "title": draft.title or "学习草稿",
        "content": draft.content or "",
        "is_collapsed": bool(draft.is_collapsed),
        "created_at": draft.created_at.isoformat(),
        "updated_at": draft.updated_at.isoformat(),
    }


def get_or_create_draft(project_id: int) -> dict | None:
    db = SessionLocal()

    try:
        project = db.query(Project).filter(Project.id == project_id).first()

        if project is None:
            return None

        draft = (
            db.query(DraftNote)
            .filter(DraftNote.project_id == project_id)
            .first()
        )

        if draft is None:
            draft = DraftNote(
                project_id=project_id,
                title="学习草稿",
                content="",
                is_collapsed=True,
            )
            db.add(draft)
            db.commit()
            db.refresh(draft)

        return serialize_draft(draft)

    finally:
        db.close()


def update_draft(
    project_id: int,
    title: str | None = None,
    content: str | None = None,
    is_collapsed: bool | None = None,
) -> dict | None:
    db = SessionLocal()

    try:
        project = db.query(Project).filter(Project.id == project_id).first()

        if project is None:
            return None

        draft = (
            db.query(DraftNote)
            .filter(DraftNote.project_id == project_id)
            .first()
        )

        if draft is None:
            draft = DraftNote(
                project_id=project_id,
                title="学习草稿",
                content="",
                is_collapsed=True,
            )
            db.add(draft)

        if title is not None:
            draft.title = title

        if content is not None:
            draft.content = content

        if is_collapsed is not None:
            draft.is_collapsed = is_collapsed

        draft.updated_at = datetime.utcnow()

        db.commit()
        db.refresh(draft)

        return serialize_draft(draft)

    finally:
        db.close()