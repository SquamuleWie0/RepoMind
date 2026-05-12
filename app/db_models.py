from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
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


class ProjectMessage(Base):
    __tablename__ = "project_messages"

    id = Column(Integer, primary_key=True, index=True)

    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)

    question = Column(Text, nullable=False)
    answer = Column(Text, nullable=False)

    timestamp = Column(DateTime, default=datetime.utcnow)

    project = relationship("Project", back_populates="messages")