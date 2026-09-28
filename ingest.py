import os
from pypdf import PdfReader
from google import genai
from google.genai import types

client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

EMBEDDING_MODEL = "gemini-embedding-001"
EMBEDDING_DIM = 768
CHUNK_SIZE = 800       # characters per chunk — small enough for focused retrieval,
CHUNK_OVERLAP = 150    # large enough for a sentence or two of context. Overlap avoids
                        # cutting a relevant sentence exactly at a chunk boundary.


def extract_text(filepath):
    """Pull raw text out of a PDF. Extend this if you want to support .txt/.md too."""
    reader = PdfReader(filepath)
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def chunk_text(text, chunk_size=CHUNK_SIZE, overlap=CHUNK_OVERLAP):
    """Simple fixed-size sliding-window chunking.

    This is the naive approach on purpose — it's easy to reason about and good
    enough to prove the pipeline works. A more sophisticated version would chunk
    on sentence/paragraph boundaries instead of a raw character count; worth
    revisiting once retrieval quality is something you can actually evaluate.
    """
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        start = end - overlap
    return [c.strip() for c in chunks if c.strip()]


def embed_text(text):
    """Get a single embedding vector for a piece of text via Gemini."""
    result = client.models.embed_content(
        model=EMBEDDING_MODEL,
        contents=text,
        config=types.EmbedContentConfig(
            task_type="RETRIEVAL_DOCUMENT",
            output_dimensionality=EMBEDDING_DIM,
        ),
    )
    return result.embeddings[0].values


def ingest_document(filepath, filename, db, Document, Chunk):
    """Full pipeline: extract -> chunk -> embed -> store. Returns the Document row."""
    text = extract_text(filepath)
    if not text.strip():
        raise ValueError("No extractable text found in this file.")

    pieces = chunk_text(text)

    doc = Document(filename=filename)
    db.session.add(doc)
    db.session.flush()  # get doc.id before creating chunks

    for i, piece in enumerate(pieces):
        embedding = embed_text(piece)
        chunk = Chunk(
            document_id=doc.id,
            content=piece,
            chunk_index=i,
            embedding=embedding,
        )
        db.session.add(chunk)

    db.session.commit()
    return doc, len(pieces)