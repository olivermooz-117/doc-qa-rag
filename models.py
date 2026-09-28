from datetime import datetime, timezone

from flask_sqlalchemy import SQLAlchemy
from pgvector.sqlalchemy import Vector


db = SQLAlchemy()


class Document(db.Model):
    __tablename__ = "documents"

    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(255), nullable=False)
    uploaded_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    chunks = db.relationship(
        "Chunk",
        back_populates="document",
        cascade="all, delete-orphan",
        lazy=True,
    )


class Chunk(db.Model):
    __tablename__ = "chunks"

    id = db.Column(db.Integer, primary_key=True)
    document_id = db.Column(
        db.Integer,
        db.ForeignKey("documents.id"),
        nullable=False,
        index=True,
    )
    content = db.Column(db.Text, nullable=False)
    chunk_index = db.Column(db.Integer, nullable=False)
    page_number = db.Column(db.Integer, nullable=True)
    embedding = db.Column(Vector(768), nullable=False)

    document = db.relationship(
        "Document",
        back_populates="chunks",
    )

    __table_args__ = (
        db.UniqueConstraint(
            "document_id",
            "chunk_index",
            name="uq_chunk_document_index",
        ),
    )