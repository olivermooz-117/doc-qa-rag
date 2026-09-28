
import logging
import os
from pathlib import Path

from google import genai
from google.genai import types
from pypdf import PdfReader

logger = logging.getLogger(__name__)

EMBEDDING_MODEL = "gemini-embedding-001"
EMBEDDING_DIMENSIONS = 768

CHUNK_SIZE = 800
CHUNK_OVERLAP = 150


def get_gemini_client():
    """Create a Gemini client using the configured API key."""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is not configured")

    return genai.Client(api_key=api_key)


def chunk_text(text, chunk_size=CHUNK_SIZE, overlap=CHUNK_OVERLAP):
    """Split text into overlapping chunks."""
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")

    if overlap < 0 or overlap >= chunk_size:
        raise ValueError("overlap must be between 0 and chunk_size")

    text = " ".join(text.split())
    if not text:
        return []

    chunks = []
    start = 0

    while start < len(text):
        end = min(start + chunk_size, len(text))
        chunk = text[start:end].strip()

        if chunk:
            chunks.append(chunk)

        if end >= len(text):
            break

        start = end - overlap

    return chunks


def extract_pdf_pages(filepath):
    """Extract non-empty text from a PDF, preserving 1-based page numbers."""
    reader = PdfReader(filepath)
    pages = []

    for page_number, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        text = text.strip()

        if text:
            pages.append((page_number, text))

    if not pages:
        raise ValueError(
            "No extractable text was found in the PDF. "
            "Scanned PDFs may require OCR."
        )

    return pages


def embed_text(client, text):
    """Generate a vector embedding for one text chunk."""
    response = client.models.embed_content(
        model=EMBEDDING_MODEL,
        contents=text,
        config=types.EmbedContentConfig(
            output_dimensionality=EMBEDDING_DIMENSIONS
        ),
    )

    if not response.embeddings:
        raise RuntimeError("Gemini returned no embedding")

    values = response.embeddings[0].values

    if not values or len(values) != EMBEDDING_DIMENSIONS:
        raise RuntimeError("Gemini returned an invalid embedding dimension")

    return values


def ingest_document(filepath, filename, db, Document, Chunk):
    """
    Extract, chunk, embed, and persist a PDF.

    The database transaction is rolled back if any step fails.
    Returns the persisted Document instance.
    """
    try:
        if not Path(filepath).is_file():
            raise FileNotFoundError("The uploaded PDF file was not found")

        pages = extract_pdf_pages(filepath)
        client = get_gemini_client()

        document = Document(filename=filename)
        db.session.add(document)
        db.session.flush()

        chunk_index = 0

        for page_number, page_text in pages:
            for content in chunk_text(page_text):
                embedding = embed_text(client, content)

                chunk = Chunk(
                    document_id=document.id,
                    content=content,
                    chunk_index=chunk_index,
                    page_number=page_number,
                    embedding=embedding,
                )

                db.session.add(chunk)
                chunk_index += 1

        if chunk_index == 0:
            raise ValueError("No usable text chunks were created")

        db.session.commit()

        logger.info(
            "Ingested PDF '%s' with %d chunks",
            filename,
            chunk_index,
        )

        return document

    except Exception:
        db.session.rollback()
        logger.exception("PDF ingestion failed for '%s'", filename)
        raise