from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    JSON,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


json_value = JSON().with_variant(JSONB(), "postgresql")


class Base(DeclarativeBase):
    pass


class ResearchRunTable(Base):
    __tablename__ = "research_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    thread_id: Mapped[str] = mapped_column(String(128), index=True)
    status: Mapped[str] = mapped_column(String(32), index=True)
    original_question: Mapped[str] = mapped_column(Text)
    selected_question: Mapped[str | None] = mapped_column(Text, nullable=True)
    subquestions: Mapped[list[dict[str, Any]]] = mapped_column(
        json_value, default=list
    )
    search_plan: Mapped[dict[str, Any] | None] = mapped_column(
        json_value, nullable=True
    )
    search_errors: Mapped[list[str]] = mapped_column(json_value, default=list)
    paper_count: Mapped[int] = mapped_column(Integer, default=0)
    top_relevance_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, index=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class WorkflowEventTable(Base):
    __tablename__ = "workflow_events"
    __table_args__ = (
        UniqueConstraint("run_id", "sequence", name="uq_workflow_event_sequence"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(
        ForeignKey("research_runs.id", ondelete="CASCADE"), index=True
    )
    sequence: Mapped[int] = mapped_column(Integer)
    node: Mapped[str] = mapped_column(String(64), index=True)
    message: Mapped[str] = mapped_column(Text)
    details: Mapped[dict[str, Any]] = mapped_column(json_value, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now
    )


class PaperTable(Base):
    __tablename__ = "papers"

    arxiv_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    title: Mapped[str] = mapped_column(Text)
    authors: Mapped[list[str]] = mapped_column(json_value, default=list)
    abstract: Mapped[str] = mapped_column(Text)
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    categories: Mapped[list[str]] = mapped_column(json_value, default=list)
    abs_url: Mapped[str] = mapped_column(Text)
    pdf_url: Mapped[str] = mapped_column(Text)
    metadata_updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now
    )


class RunPaperTable(Base):
    __tablename__ = "run_papers"
    __table_args__ = (
        CheckConstraint(
            "relevance_score >= 0 AND relevance_score <= 100",
            name="ck_run_papers_relevance_score",
        ),
        Index("ix_run_papers_score", "run_id", "relevance_score"),
    )

    run_id: Mapped[str] = mapped_column(
        ForeignKey("research_runs.id", ondelete="CASCADE"), primary_key=True
    )
    arxiv_id: Mapped[str] = mapped_column(
        ForeignKey("papers.arxiv_id", ondelete="CASCADE"), primary_key=True
    )
    display_order: Mapped[int] = mapped_column(Integer)
    source_rank: Mapped[int] = mapped_column(Integer)
    relevance_score: Mapped[int] = mapped_column(Integer)
    matched_keywords: Mapped[list[str]] = mapped_column(json_value, default=list)
    matched_queries: Mapped[list[str]] = mapped_column(json_value, default=list)


class LLMCallTable(Base):
    __tablename__ = "llm_calls"
    __table_args__ = (
        UniqueConstraint("run_id", "sequence", name="uq_llm_call_sequence"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    run_id: Mapped[str] = mapped_column(
        ForeignKey("research_runs.id", ondelete="CASCADE"), index=True
    )
    sequence: Mapped[int] = mapped_column(Integer)
    operation: Mapped[str] = mapped_column(String(64))
    provider: Mapped[str] = mapped_column(String(64))
    model: Mapped[str] = mapped_column(String(128))
    prompt_tokens: Mapped[int] = mapped_column(Integer, default=0)
    completion_tokens: Mapped[int] = mapped_column(Integer, default=0)
    total_tokens: Mapped[int] = mapped_column(Integer, default=0)
    prompt_cache_hit_tokens: Mapped[int] = mapped_column(Integer, default=0)
    prompt_cache_miss_tokens: Mapped[int] = mapped_column(Integer, default=0)
    reasoning_tokens: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now
    )
