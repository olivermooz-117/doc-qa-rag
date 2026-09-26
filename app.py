import os
from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv

load_dotenv()

from models import db, Document, Chunk
from ingest import ingest_document

UPLOAD_DIR = "uploads"


def create_app():
    app = Flask(__name__)
    CORS(app)

    app.config["SQLALCHEMY_DATABASE_URI"] = os.environ["DATABASE_URL"]
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

    db.init_app(app)

    os.makedirs(UPLOAD_DIR, exist_ok=True)

    with app.app_context():
        # Requires the pgvector extension to already exist in the database:
        #   CREATE EXTENSION IF NOT EXISTS vector;
        db.create_all()

    @app.route("/api/documents", methods=["GET"])
    def list_documents():
        docs = Document.query.order_by(Document.uploaded_at.desc()).all()
        return jsonify([
            {
                "id": d.id,
                "filename": d.filename,
                "uploaded_at": d.uploaded_at.isoformat(),
                "chunk_count": len(d.chunks),
            }
            for d in docs
        ])

    @app.route("/api/upload", methods=["POST"])
    def upload():
        if "file" not in request.files:
            return jsonify({"error": "No file provided"}), 400

        file = request.files["file"]
        if file.filename == "":
            return jsonify({"error": "Empty filename"}), 400
        if not file.filename.lower().endswith(".pdf"):
            return jsonify({"error": "Only PDF files are supported right now"}), 400

        filepath = os.path.join(UPLOAD_DIR, file.filename)
        file.save(filepath)

        try:
            doc, chunk_count = ingest_document(filepath, file.filename, db, Document, Chunk)
        except Exception as e:
            return jsonify({"error": str(e)}), 500

        return jsonify({
            "id": doc.id,
            "filename": doc.filename,
            "chunks_created": chunk_count,
        }), 201

    return app


if __name__ == "__main__":
    app = create_app()
    app.run(debug=True, port=5001)