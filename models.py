from flask_sqlalchemy import SQLAlchemy
from pgvector.sqlalchemy import Vector
import datetime

db = SQLAlchemy()

# Gemini embeddings are requested at 768 dimensions to match the pgvector column.
EMBEDDING_DIM = 768


class Document(db.Model):
    __tablename__ = "documents"

    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(255), nullable=False)
    uploaded_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)

    chunks = db.relationship("Chunk", backref="document", cascade="all, delete-orphan")


class Chunk(db.Model):
    __tablename__ = "chunks"

    id = db.Column(db.Integer, primary_key=True)
    document_id = db.Column(db.Integer, db.ForeignKey("documents.id"), nullable=False)
    content = db.Column(db.Text, nullable=False)
    chunk_index = db.Column(db.Integer, nullable=False)  # position within the document
    embedding = db.Column(Vector(EMBEDDING_DIM), nullable=False)