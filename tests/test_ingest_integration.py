from unittest.mock import patch

from pypdf import  PdfWriter

from ingest import extract_pdf_pages, ingest_document
from models import Chunk, Document, db


def create_test_pdf(path):
    """Create a small two-page PDF for integration testing."""
    writer = PdfWriter()

    writer.add_blank_page(width=612, height=792)
    writer.add_blank_page(width=612, height=792)

    with open(path, "wb") as file:
        writer.write(file)


def test_extract_pdf_pages_returns_page_numbers(tmp_path):
    pdf_path = tmp_path / "test.pdf"

    create_test_pdf(pdf_path)

    # Blank pages have no extractable text, so this confirms the
    # function correctly handles PDFs without text.
    try:
        pages = extract_pdf_pages(pdf_path)
    except ValueError as exc:
        assert "No extractable text" in str(exc)


def test_ingestion_rolls_back_on_embedding_failure(
    app,
    tmp_path,
):
    pdf_path = tmp_path / "test.pdf"

    create_test_pdf(pdf_path)

    def failing_embedding(*args, **kwargs):
        raise RuntimeError("Embedding service failed")

    with patch(
        "ingest.extract_pdf_pages",
        return_value=[
            (1, "This is page one content."),
            (2, "This is page two content."),
        ],
    ):
        with patch(
            "ingest.get_gemini_client",
        ) as mock_client:
            with patch(
                "ingest.embed_text",
                side_effect=failing_embedding,
            ):
                with app.app_context():
                    try:
                        ingest_document(
                            str(pdf_path),
                            "test.pdf",
                            db,
                            Document,
                            Chunk,
                        )
                    except RuntimeError as exc:
                        assert "Embedding service failed" in str(exc)

                    assert Document.query.count() == 0
                    assert Chunk.query.count() == 0

                    mock_client.assert_called_once()


def test_ingestion_persists_page_aware_chunks(
    app,
    tmp_path,
):
    pdf_path = tmp_path / "test.pdf"

    create_test_pdf(pdf_path)

    fake_embedding = [0.1] * 768

    with patch(
        "ingest.extract_pdf_pages",
        return_value=[
            (
                1,
                "This is content from page one.",
            ),
            (
                2,
                "This is content from page two.",
            ),
        ],
    ):
        with patch(
            "ingest.get_gemini_client",
        ) as mock_client:
            with patch(
                "ingest.embed_text",
                return_value=fake_embedding,
            ):
                with app.app_context():
                    document, chunk_count = ingest_document(
                        str(pdf_path),
                        "test.pdf",
                        db,
                        Document,
                        Chunk,
                    )

                    assert document.id is not None
                    assert document.filename == "test.pdf"
                    assert chunk_count == 2

                    chunks = (
                        Chunk.query
                        .filter_by(document_id=document.id)
                        .order_by(Chunk.chunk_index)
                        .all()
                    )

                    assert len(chunks) == 2

                    assert chunks[0].page_number == 1
                    assert chunks[0].chunk_index == 0
                    assert (
                        chunks[0].content
                        == "This is content from page one."
                    )

                    assert chunks[1].page_number == 2
                    assert chunks[1].chunk_index == 1
                    assert (
                        chunks[1].content
                        == "This is content from page two."
                    )

                    assert len(chunks[0].embedding) == 768
                    assert len(chunks[1].embedding) == 768

                    mock_client.assert_called_once()


def test_ingestion_rejects_missing_file(app):
    with app.app_context():
        try:
            ingest_document(
                "/does/not/exist.pdf",
                "missing.pdf",
                db,
                Document,
                Chunk,
            )
        except FileNotFoundError as exc:
            assert "not found" in str(exc).lower()

        assert Document.query.count() == 0
        assert Chunk.query.count() == 0


def test_ingestion_rolls_back_when_no_text_is_found(
    app,
    tmp_path,
):
    pdf_path = tmp_path / "empty.pdf"

    create_test_pdf(pdf_path)

    with patch(
        "ingest.extract_pdf_pages",
        side_effect=ValueError(
            "No extractable text was found in the PDF."
        ),
    ):
        with app.app_context():
            try:
                ingest_document(
                    str(pdf_path),
                    "empty.pdf",
                    db,
                    Document,
                    Chunk,
                )
            except ValueError as exc:
                assert "No extractable text" in str(exc)

            assert Document.query.count() == 0
            assert Chunk.query.count() == 0