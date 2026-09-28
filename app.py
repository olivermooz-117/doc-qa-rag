import logging
import os
import tempfile
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, jsonify, request
from flask_cors import CORS
from sqlalchemy import text
from werkzeug.exceptions import HTTPException
from werkzeug.utils import secure_filename

from ingest import ingest_document
from models import Chunk, Document, db
from retrieve import ask_question


load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "10"))
MAX_UPLOAD_SIZE = MAX_UPLOAD_MB * 1024 * 1024
MAX_QUESTION_LENGTH = 4000
ALLOWED_EXTENSION = ".pdf"


def create_app():
    app = Flask(__name__)

    app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv(
        "DATABASE_URL",
        "postgresql://postgres:postgres@localhost:5432/docqa",
    )
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_SIZE

    db.init_app(app)

    cors_origins = [
        origin.strip()
        for origin in os.getenv(
            "CORS_ORIGINS",
            "http://localhost:5173,http://127.0.0.1:5173",
        ).split(",")
        if origin.strip()
    ]

    CORS(
        app,
        resources={
            r"/api/*": {
                "origins": cors_origins,
            }
        },
    )

    with app.app_context():
        db.create_all()

    @app.errorhandler(413)
    def request_too_large(error):
        return jsonify(
            {
                "error": "file_too_large",
                "message": f"Uploaded file exceeds the {MAX_UPLOAD_MB} MB limit.",
            }
        ), 413

    @app.errorhandler(404)
    def not_found(error):
        return jsonify(
            {
                "error": "not_found",
                "message": "The requested resource was not found.",
            }
        ), 404

    @app.errorhandler(405)
    def method_not_allowed(error):
        return jsonify(
            {
                "error": "method_not_allowed",
                "message": "The HTTP method is not allowed for this endpoint.",
            }
        ), 405

    @app.errorhandler(Exception)
    def handle_unexpected_error(error):
        if isinstance(error, HTTPException):
            raise error

        logger.exception("Unhandled application error")

        return jsonify(
            {
                "error": "internal_server_error",
                "message": "An unexpected error occurred.",
            }
        ), 500

    @app.get("/health")
    def health():
        return jsonify({"status": "ok"}), 200

    @app.get("/ready")
    def readiness():
        try:
            db.session.execute(text("SELECT 1"))
            return jsonify(
                {
                    "status": "ready",
                    "database": "ok",
                }
            ), 200
        except Exception:
            logger.exception("Readiness check failed")
            return jsonify(
                {
                    "status": "not_ready",
                    "database": "error",
                }
            ), 503

    @app.get("/api/documents")
    def list_documents():
        documents = (
            Document.query
            .order_by(Document.uploaded_at.desc())
            .all()
        )

        return jsonify(
            {
                "documents": [
                    {
                        "id": document.id,
                        "filename": document.filename,
                        "uploaded_at": (
                            document.uploaded_at.isoformat()
                            if document.uploaded_at
                            else None
                        ),
                        "chunk_count": len(document.chunks),
                    }
                    for document in documents
                ]
            }
        ), 200

    @app.post("/api/upload")
    def upload():
        if "file" not in request.files:
            return jsonify(
                {
                    "error": "missing_file",
                    "message": "No file was provided.",
                }
            ), 400

        file = request.files["file"]

        if not file.filename:
            return jsonify(
                {
                    "error": "empty_filename",
                    "message": "The uploaded file has no filename.",
                }
            ), 400

        filename = secure_filename(file.filename)

        if not filename:
            return jsonify(
                {
                    "error": "invalid_filename",
                    "message": "The uploaded filename is invalid.",
                }
            ), 400

        if Path(filename).suffix.lower() != ALLOWED_EXTENSION:
            return jsonify(
                {
                    "error": "invalid_file_type",
                    "message": "Only PDF files are supported.",
                }
            ), 400

        try:
            header = file.stream.read(5)
            file.stream.seek(0)

            if header != b"%PDF-":
                return jsonify(
                    {
                        "error": "invalid_pdf",
                        "message": "The uploaded file is not a valid PDF.",
                    }
                ), 400

            temp_path = None

            try:
                with tempfile.NamedTemporaryFile(
                    suffix=".pdf",
                    delete=False,
                ) as temp_file:
                    temp_path = temp_file.name
                    file.save(temp_file)

                document, chunk_count = ingest_document(
                    temp_path,
                    filename,
                    db,
                    Document,
                    Chunk,
                )

                return jsonify(
                    {
                        "id": document.id,
                        "filename": document.filename,
                        "uploaded_at": (
                            document.uploaded_at.isoformat()
                            if document.uploaded_at
                            else None
                        ),
                        "chunk_count": chunk_count,
                        "chunks_created": chunk_count,
                    }
                ), 201

            finally:
                if temp_path:
                    try:
                        os.unlink(temp_path)
                    except FileNotFoundError:
                        pass

        except ValueError as exc:
            db.session.rollback()

            return jsonify(
                {
                    "error": "invalid_document",
                    "message": str(exc),
                }
            ), 400

        except Exception:
            db.session.rollback()
            logger.exception("PDF ingestion failed")

            return jsonify(
                {
                    "error": "ingestion_failed",
                    "message": "The PDF could not be processed.",
                }
            ), 500

    @app.post("/api/ask")
    def ask():
        if not request.is_json:
            return jsonify(
                {
                    "error": "invalid_request",
                    "message": "Request body must be JSON.",
                }
            ), 400

        payload = request.get_json(silent=True) or {}
        question = payload.get("question")

        if not isinstance(question, str):
            return jsonify(
                {
                    "error": "missing_question",
                    "message": "A question is required.",
                }
            ), 400

        question = question.strip()

        if not question:
            return jsonify(
                {
                    "error": "empty_question",
                    "message": "Question cannot be empty.",
                }
            ), 400

        if len(question) > MAX_QUESTION_LENGTH:
            return jsonify(
                {
                    "error": "question_too_long",
                    "message": (
                        f"Question must be at most "
                        f"{MAX_QUESTION_LENGTH} characters."
                    ),
                }
            ), 400

        try:
            result = ask_question(question)

            return jsonify(result), 200

        except ValueError as exc:
            return jsonify(
                {
                    "error": "invalid_question",
                    "message": str(exc),
                }
            ), 400

        except Exception:
            logger.exception("Question answering failed")

            return jsonify(
                {
                    "error": "question_failed",
                    "message": "The question could not be answered.",
                }
            ), 500

    return app


app = create_app()


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.getenv("PORT", "5000")),
        debug=False,
    )
