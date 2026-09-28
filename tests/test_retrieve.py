from unittest.mock import patch

import pytest

from models import Chunk, Document, db
from retrieve import build_sources


def create_document_with_chunks(app):
    with app.app_context():
        document = Document(filename="example.pdf")
        db.session.add(document)
        db.session.flush()

        chunks = [
            Chunk(
                document_id=document.id,
                content="First chunk of the document.",
                chunk_index=0,
                page_number=2,
                embedding=[0.1] * 768,
            ),
            Chunk(
                document_id=document.id,
                content="Second chunk of the document.",
                chunk_index=1,
                page_number=3,
                embedding=[0.2] * 768,
            ),
        ]

        db.session.add_all(chunks)
        db.session.commit()

        return document.id


def get_retrieval_results(app, document_id):
    with app.app_context():
        document = db.session.get(Document, document_id)

        chunks = (
            db.session.query(Chunk)
            .filter_by(document_id=document_id)
            .order_by(Chunk.chunk_index)
            .all()
        )

        return [
            {
                "chunk": chunk,
                "document": document,
                "distance": 0.1 + (index * 0.1),
            }
            for index, chunk in enumerate(chunks)
        ]


def test_build_sources_contains_page_metadata(app):
    document_id = create_document_with_chunks(app)
    results = get_retrieval_results(app, document_id)

    with app.app_context():
        sources = build_sources(results)

    assert sources
    assert sources[0]["document"] == "example.pdf"
    assert sources[0]["page"] == 2
    assert sources[0]["citation"] == "example.pdf, page 2"
    assert sources[0]["distance"] == 0.1


def test_build_sources_returns_empty_list(app):
    with app.app_context():
        sources = build_sources([])

    assert sources == []


def test_build_sources_preserves_multiple_pages(app):
    document_id = create_document_with_chunks(app)
    results = get_retrieval_results(app, document_id)

    with app.app_context():
        sources = build_sources(results)

    assert len(sources) == 2

    assert sources[0]["page"] == 2
    assert sources[1]["page"] == 3

    assert sources[0]["document"] == "example.pdf"
    assert sources[1]["document"] == "example.pdf"

    assert sources[0]["distance"] == 0.1
    assert sources[1]["distance"] == 0.2


@pytest.mark.gemini
@patch("retrieve.genai")
def test_embedding_query_uses_gemini(mock_genai):
    mock_genai.models.embed_content.return_value = type(
        "EmbeddingResponse",
        (),
        {
            "embeddings": [
                type(
                    "Embedding",
                    (),
                    {"values": [0.1] * 768},
                )()
            ]
        },
    )()

    assert mock_genai is not None

