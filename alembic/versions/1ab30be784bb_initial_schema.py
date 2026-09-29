"""Initial database schema.

Revision ID: 1ab30be784bb
Revises:
Create Date: 2026-09-29
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector


revision: str = "1ab30be784bb"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create the initial database schema."""

    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "documents",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column(
            "uploaded_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
    )

    op.create_table(
        "chunks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("document_id", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=True),
        sa.Column("embedding", Vector(768), nullable=False),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["documents.id"],
        ),
        sa.UniqueConstraint(
            "document_id",
            "chunk_index",
            name="uq_chunk_document_index",
        ),
    )

    op.create_index(
        "ix_chunks_document_id",
        "chunks",
        ["document_id"],
        unique=False,
    )


def downgrade() -> None:
    """Remove the initial database schema."""

    op.drop_index(
        "ix_chunks_document_id",
        table_name="chunks",
    )

    op.drop_table("chunks")
    op.drop_table("documents")