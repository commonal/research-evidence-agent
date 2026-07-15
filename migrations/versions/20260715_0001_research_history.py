"""Create research history tables.

Revision ID: 20260715_0001
Revises:
Create Date: 2026-07-15
"""

from typing import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20260715_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

json_value = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")


def upgrade() -> None:
    op.create_table(
        "research_runs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("thread_id", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("original_question", sa.Text(), nullable=False),
        sa.Column("selected_question", sa.Text(), nullable=True),
        sa.Column("subquestions", json_value, nullable=False),
        sa.Column("search_plan", json_value, nullable=True),
        sa.Column("search_errors", json_value, nullable=False),
        sa.Column("paper_count", sa.Integer(), nullable=False),
        sa.Column("top_relevance_score", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_research_runs_thread_id", "research_runs", ["thread_id"])
    op.create_index("ix_research_runs_status", "research_runs", ["status"])
    op.create_index("ix_research_runs_updated_at", "research_runs", ["updated_at"])

    op.create_table(
        "workflow_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("run_id", sa.String(length=36), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("node", sa.String(length=64), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("details", json_value, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["research_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "run_id", "sequence", name="uq_workflow_event_sequence"
        ),
    )
    op.create_index("ix_workflow_events_run_id", "workflow_events", ["run_id"])
    op.create_index("ix_workflow_events_node", "workflow_events", ["node"])

    op.create_table(
        "papers",
        sa.Column("arxiv_id", sa.String(length=32), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("authors", json_value, nullable=False),
        sa.Column("abstract", sa.Text(), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("categories", json_value, nullable=False),
        sa.Column("abs_url", sa.Text(), nullable=False),
        sa.Column("pdf_url", sa.Text(), nullable=False),
        sa.Column("metadata_updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("arxiv_id"),
    )

    op.create_table(
        "llm_calls",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("run_id", sa.String(length=36), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("operation", sa.String(length=64), nullable=False),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("model", sa.String(length=128), nullable=False),
        sa.Column("prompt_tokens", sa.Integer(), nullable=False),
        sa.Column("completion_tokens", sa.Integer(), nullable=False),
        sa.Column("total_tokens", sa.Integer(), nullable=False),
        sa.Column("prompt_cache_hit_tokens", sa.Integer(), nullable=False),
        sa.Column("prompt_cache_miss_tokens", sa.Integer(), nullable=False),
        sa.Column("reasoning_tokens", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["research_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("run_id", "sequence", name="uq_llm_call_sequence"),
    )
    op.create_index("ix_llm_calls_run_id", "llm_calls", ["run_id"])

    op.create_table(
        "run_papers",
        sa.Column("run_id", sa.String(length=36), nullable=False),
        sa.Column("arxiv_id", sa.String(length=32), nullable=False),
        sa.Column("display_order", sa.Integer(), nullable=False),
        sa.Column("source_rank", sa.Integer(), nullable=False),
        sa.Column("relevance_score", sa.Integer(), nullable=False),
        sa.Column("matched_keywords", json_value, nullable=False),
        sa.Column("matched_queries", json_value, nullable=False),
        sa.ForeignKeyConstraint(["arxiv_id"], ["papers.arxiv_id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["run_id"], ["research_runs.id"], ondelete="CASCADE"),
        sa.CheckConstraint(
            "relevance_score >= 0 AND relevance_score <= 100",
            name="ck_run_papers_relevance_score",
        ),
        sa.PrimaryKeyConstraint("run_id", "arxiv_id"),
    )
    op.create_index(
        "ix_run_papers_score", "run_papers", ["run_id", "relevance_score"]
    )


def downgrade() -> None:
    op.drop_index("ix_run_papers_score", table_name="run_papers")
    op.drop_table("run_papers")
    op.drop_index("ix_llm_calls_run_id", table_name="llm_calls")
    op.drop_table("llm_calls")
    op.drop_table("papers")
    op.drop_index("ix_workflow_events_node", table_name="workflow_events")
    op.drop_index("ix_workflow_events_run_id", table_name="workflow_events")
    op.drop_table("workflow_events")
    op.drop_index("ix_research_runs_updated_at", table_name="research_runs")
    op.drop_index("ix_research_runs_status", table_name="research_runs")
    op.drop_index("ix_research_runs_thread_id", table_name="research_runs")
    op.drop_table("research_runs")
