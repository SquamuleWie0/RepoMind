from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import declarative_base, relationship


Base = declarative_base()


class Project(Base):
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, index=True)

    repo_url = Column(String, unique=True, index=True, nullable=False)
    project_name = Column(String, nullable=False)
    tech_stack = Column(String, default="")

    repo_path = Column(String, default="")
    file_tree = Column(Text, default="")
    analysis_result_json = Column(Text, default="{}")

    ai_report = Column(Text, default="")
    basic_report = Column(Text, default="")

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)

    messages = relationship(
        "ProjectMessage",
        back_populates="project",
        cascade="all, delete-orphan",
    )

    draft_note = relationship(
        "DraftNote",
        back_populates="project",
        cascade="all, delete-orphan",
        uselist=False,
    )

    learning_notes = relationship(
        "LearningNote",
        back_populates="project",
        cascade="all, delete-orphan",
    )


class ProjectMessage(Base):
    __tablename__ = "project_messages"

    id = Column(Integer, primary_key=True, index=True)

    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)

    question = Column(Text, nullable=False)
    answer = Column(Text, nullable=False)

    timestamp = Column(DateTime, default=datetime.utcnow)

    project = relationship("Project", back_populates="messages")


class DraftNote(Base):
    """
    每个项目对应一个草稿便签。
    content 存 Markdown 原文。
    is_collapsed 记录前端展开 / 收起状态。
    """

    __tablename__ = "draft_notes"

    id = Column(Integer, primary_key=True, index=True)

    project_id = Column(
        Integer,
        ForeignKey("projects.id"),
        unique=True,
        nullable=False,
        index=True,
    )

    title = Column(String, default="学习草稿")
    content = Column(Text, default="")
    is_collapsed = Column(Boolean, default=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)

    project = relationship("Project", back_populates="draft_note")


class LearningNote(Base):
    """
    AI 整理生成的学习记录初稿。
    可以基于项目导读、历史问答、草稿便签生成。
    """

    __tablename__ = "learning_notes"

    id = Column(Integer, primary_key=True, index=True)

    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False, index=True)

    title = Column(String, default="项目学习记录")
    content = Column(Text, default="")
    sources_json = Column(Text, default="[]")

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)

    project = relationship("Project", back_populates="learning_notes")