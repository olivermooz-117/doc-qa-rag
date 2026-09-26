import os
import google.generativeai as genai
from sqlalchemy import select

genai.configure(api_key=os.environ["GEMINI_API_KEY"])

EMBEDDING_MODEL = "models/text-embedding-004"
GENERATION_MODEL = "gemini-2.0-flash"
TOP_K = 4  # how many chunks to retrieve per question


def embed_query(text):
    """Embed the user's question. Note task_type differs from ingest.py's
    'retrieval_document' — Gemini's embedding model performs better when you
    tell it which side of the query/document pair a given piece of text is."""
    result = genai.embed_content(
        model=EMBEDDING_MODEL,
        content=text,
        task_type="retrieval_query",
    )
    return result["embedding"]


def retrieve_chunks(question, db, Chunk, top_k=TOP_K):
    """Embed the question, then find the closest stored chunks by cosine distance.

    pgvector's `<=>` operator computes cosine distance directly in SQL, so the
    similarity search happens in the database rather than pulling every chunk
    into Python and comparing vectors by hand.
    """
    query_embedding = embed_query(question)

    stmt = (
        select(Chunk)
        .order_by(Chunk.embedding.cosine_distance(query_embedding))
        .limit(top_k)
    )
    return db.session.execute(stmt).scalars().all()


def generate_answer(question, chunks):
    """Feed retrieved chunks + the question to Gemini, return a grounded answer."""
    if not chunks:
        return "No relevant content found in the uploaded documents.", []

    context = "\n\n---\n\n".join(
        f"[Source {i+1}, from {c.document.filename}]\n{c.content}"
        for i, c in enumerate(chunks)
    )

    prompt = f"""Answer the question using ONLY the sources below. If the sources
don't contain enough information to answer, say so plainly rather than guessing.
Cite which source number(s) you used.

Sources:
{context}

Question: {question}

Answer:"""

    model = genai.GenerativeModel(GENERATION_MODEL)
    response = model.generate_content(prompt)

    sources = [
        {"document": c.document.filename, "chunk_index": c.chunk_index, "content": c.content}
        for c in chunks
    ]
    return response.text, sources


def answer_question(question, db, Chunk):
    """Full pipeline: retrieve -> generate. What the /api/ask route calls."""
    chunks = retrieve_chunks(question, db, Chunk)
    answer, sources = generate_answer(question, chunks)
    return answer, sources