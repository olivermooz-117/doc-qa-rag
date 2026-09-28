import io
from unittest.mock import patch

from app import MAX_QUESTION_LENGTH, create_app
from models import Document, db


def test_health(client):
    response = client.get("/health")

    assert response.status_code == 200
    assert response.get_json() == {"status": "ok"}


def test_readiness(client):
    response = client.get("/ready")

    assert response.status_code == 200

    data = response.get_json()

    assert data["status"] == "ready"
    assert data["database"] == "ok"


def test_upload_size_limit_uses_environment_setting(
    monkeypatch,
    test_database_url,
):
    monkeypatch.setenv("DATABASE_URL", test_database_url)
    monkeypatch.setenv("MAX_UPLOAD_MB", "1")

    with patch("app.db.create_all"):
        configured_app = create_app()

    assert configured_app.config["MAX_CONTENT_LENGTH"] == 1024 * 1024

    response = configured_app.test_client().post(
        "/api/upload",
        data=b"x" * (1024 * 1024 + 1),
        content_type="application/octet-stream",
    )

    assert response.status_code == 413
    assert response.get_json() == {
        "error": "file_too_large",
        "message": "Uploaded file exceeds the 1 MB limit.",
    }


def test_cors_uses_configured_origins(monkeypatch, test_database_url):
    monkeypatch.setenv("DATABASE_URL", test_database_url)
    monkeypatch.setenv(
        "CORS_ORIGINS",
        "https://docs.example, https://admin.example",
    )

    with patch("app.db.create_all"):
        configured_app = create_app()

    response = configured_app.test_client().options(
        "/api/upload",
        headers={
            "Origin": "https://docs.example",
            "Access-Control-Request-Method": "POST",
        },
    )

    assert response.headers["Access-Control-Allow-Origin"] == (
        "https://docs.example"
    )


def test_documents_returns_empty_list(client):
    response = client.get("/api/documents")

    assert response.status_code == 200
    assert response.get_json() == {"documents": []}


def test_upload_requires_file(client):
    response = client.post("/api/upload")

    assert response.status_code == 400

    data = response.get_json()

    assert data["error"] == "missing_file"


def test_upload_rejects_non_pdf(client):
    response = client.post(
        "/api/upload",
        data={
            "file": (
                io.BytesIO(b"not a pdf"),
                "document.txt",
            )
        },
        content_type="multipart/form-data",
    )

    assert response.status_code == 400

    data = response.get_json()

    assert data["error"] == "invalid_file_type"


def test_upload_rejects_invalid_pdf_signature(client):
    response = client.post(
        "/api/upload",
        data={
            "file": (
                io.BytesIO(b"not really a pdf"),
                "document.pdf",
            )
        },
        content_type="multipart/form-data",
    )

    assert response.status_code == 400

    data = response.get_json()

    assert data["error"] == "invalid_pdf"


def test_upload_rejects_empty_filename(client):
    response = client.post(
        "/api/upload",
        data={
            "file": (
                io.BytesIO(b"%PDF-1.7\n"),
                "",
            )
        },
        content_type="multipart/form-data",
    )

    assert response.status_code == 400


def test_ask_requires_json(client):
    response = client.post(
        "/api/ask",
        data="question=test",
        content_type="application/x-www-form-urlencoded",
    )

    assert response.status_code == 400

    data = response.get_json()

    assert data["error"] == "invalid_request"


def test_ask_requires_question(client):
    response = client.post(
        "/api/ask",
        json={},
    )

    assert response.status_code == 400

    data = response.get_json()

    assert data["error"] == "missing_question"


def test_ask_rejects_empty_question(client):
    response = client.post(
        "/api/ask",
        json={"question": "   "},
    )

    assert response.status_code == 400

    data = response.get_json()

    assert data["error"] == "empty_question"


def test_ask_rejects_question_that_is_too_long(client):
    response = client.post(
        "/api/ask",
        json={
            "question": "x" * (MAX_QUESTION_LENGTH + 1),
        },
    )

    assert response.status_code == 400

    data = response.get_json()

    assert data["error"] == "question_too_long"


def test_unknown_route_returns_json_error(client):
    response = client.get("/does-not-exist")

    assert response.status_code == 404

    data = response.get_json()

    assert data["error"] == "not_found"


def test_method_not_allowed_returns_json_error(client):
    response = client.post("/health")

    assert response.status_code == 405

    data = response.get_json()

    assert data["error"] == "method_not_allowed"


def test_documents_can_be_returned(app, client):
    with app.app_context():
        document = Document(filename="example.pdf")
        db.session.add(document)
        db.session.commit()

    response = client.get("/api/documents")

    assert response.status_code == 200

    data = response.get_json()

    assert len(data["documents"]) == 1
    assert data["documents"][0]["filename"] == "example.pdf"
    assert data["documents"][0]["chunk_count"] == 0
    assert "uploaded_at" in data["documents"][0]


@patch("app.ingest_document")
def test_upload_success(mock_ingest, client):
    """
    Verify that a valid PDF reaches the ingestion pipeline.

    Gemini/PDF ingestion is mocked here because this is an API test,
    not an ingestion integration test.
    """

    class MockDocument:
        id = 1
        filename = "test.pdf"
        uploaded_at = None

    mock_ingest.return_value = (MockDocument(), 1)

    response = client.post(
        "/api/upload",
        data={
            "file": (
                io.BytesIO(
                    b"%PDF-1.7\n"
                    b"1 0 obj\n"
                    b"<< /Type /Catalog >>\n"
                    b"endobj\n"
                ),
                "test.pdf",
            )
        },
        content_type="multipart/form-data",
    )

    assert response.status_code in (200, 201)

    data = response.get_json()

    assert data["id"] == 1
    assert data["filename"] == "test.pdf"
    assert data["chunk_count"] == 1
    assert data["chunks_created"] == 1

    mock_ingest.assert_called_once()


@patch("app.ask_question")
def test_ask_success(mock_ask, client):
    mock_ask.return_value = {
        "answer": "This is the answer.",
        "sources": [
            {
                "document": "example.pdf",
                "page": 2,
                "citation": "example.pdf, page 2",
            }
        ],
    }

    response = client.post(
        "/api/ask",
        json={
            "question": "What is in the document?",
        },
    )

    assert response.status_code == 200

    data = response.get_json()

    assert data["answer"] == "This is the answer."
    assert len(data["sources"]) == 1
    assert data["sources"][0]["document"] == "example.pdf"

    mock_ask.assert_called_once_with(
        "What is in the document?"
    )

