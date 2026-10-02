import logging
import os
import time

from google import genai
from google.genai import types

from sqlalchemy import select

from models import db, Chunk, Document

logger = logging.getLogger(__name__)


EMBEDDING_MODEL = os.getenv(
    "GEMINI_EMBEDDING_MODEL",
    "gemini-embedding-001",
)

EMBEDDING_DIMENSIONS = int(
    os.getenv("GEMINI_EMBEDDING_DIMENSIONS", "768")
)

# Primary generation model.
GENERATION_MODEL = os.getenv(
    "GEMINI_GENERATION_MODEL",
    "gemini-2.5-flash",
)

# Optional fallback model.
GENERATION_FALLBACK_MODEL = os.getenv(
    "GEMINI_GENERATION_FALLBACK_MODEL",
    "gemini-2.5-flash-lite",
)

DEFAULT_TOP_K = 5
MAX_TOP_K = 20

GENERATION_MAX_RETRIES = 3
GENERATION_RETRY_DELAY_SECONDS = 2


def get_gemini_client():
    """Create a Gemini client using the configured API key."""
    api_key = os.getenv("GEMINI_API_KEY")

    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY is not configured"
        )

    return genai.Client(api_key=api_key)


def embed_query(client, question):
    """Generate an embedding for the user's question."""
    response = client.models.embed_content(
        model=EMBEDDING_MODEL,
        contents=question,
        config=types.EmbedContentConfig(
            output_dimensionality=EMBEDDING_DIMENSIONS,
        ),
    )

    if not response.embeddings:
        raise RuntimeError(
            "Gemini returned no query embedding"
        )

    embedding = response.embeddings[0].values

    if (
        not embedding
        or len(embedding) != EMBEDDING_DIMENSIONS
    ):
        raise RuntimeError(
            "Gemini returned an invalid query embedding"
        )

    return embedding


def retrieve_chunks(
    question,
    top_k=DEFAULT_TOP_K,
):
    """
    Retrieve the most relevant document chunks
    using pgvector cosine distance.
    """
    if (
        not isinstance(question, str)
        or not question.strip()
    ):
        raise ValueError(
            "Question must not be empty"
        )

    try:
        top_k = int(top_k)
    except (TypeError, ValueError):
        raise ValueError(
            "top_k must be an integer"
        )

    if top_k < 1 or top_k > MAX_TOP_K:
        raise ValueError(
            f"top_k must be between 1 and {MAX_TOP_K}"
        )

    client = get_gemini_client()

    query_embedding = embed_query(
        client,
        question.strip(),
    )

    distance = Chunk.embedding.cosine_distance(
        query_embedding
    )

    stmt = (
        select(
            Chunk,
            Document,
            distance.label("distance"),
        )
        .join(
            Document,
            Chunk.document_id == Document.id,
        )
        .order_by(distance)
        .limit(top_k)
    )

    results = db.session.execute(stmt).all()

    return [
        {
            "chunk": chunk,
            "document": document,
            "distance": float(distance_value),
        }
        for chunk, document, distance_value in results
    ]


def build_context(results):
    """Build a clearly labelled context block for Gemini."""
    context_parts = []

    for index, result in enumerate(
        results,
        start=1,
    ):
        chunk = result["chunk"]
        document = result["document"]

        page = chunk.page_number

        context_parts.append(
            f"[SOURCE {index}]\n"
            f"Document: {document.filename}\n"
            f"Page: {page}\n"
            f"Chunk: {chunk.chunk_index}\n"
            f"Content:\n{chunk.content}"
        )

    return "\n\n".join(context_parts)


def build_sources(results):
    """Return structured source information."""
    sources = []

    for index, result in enumerate(
        results,
        start=1,
    ):
        chunk = result["chunk"]
        document = result["document"]

        sources.append(
            {
                "id": chunk.id,
                "document_id": document.id,
                "document": document.filename,
                "page": chunk.page_number,
                "chunk": chunk.chunk_index,
                "chunk_index": chunk.chunk_index,
                "content": chunk.content,
                "distance": round(
                    result["distance"],
                    6,
                ),
                "citation": (
                    f"{document.filename}, "
                    f"page {chunk.page_number}"
                ),
            }
        )

    return sources


def build_prompt(question, results):
    """Build the grounded generation prompt."""
    context = build_context(results)

    return f"""
You are a document question-answering assistant.

Answer the user's question using ONLY the information
contained in the supplied document context.

Rules:
1. Do not invent facts.
2. Do not use outside knowledge.
3. If the context does not contain enough information,
   say so clearly.
4. Keep the answer concise but useful.
5. Cite supporting sources using [SOURCE N].
6. Do not cite a source unless it actually supports
   the statement.
7. When multiple sources support an answer, cite all
   relevant sources.

Document context:
{context}

User question:
{question}
""".strip()


def _is_retryable_generation_error(error):
    """
    Identify temporary Gemini availability/rate-limit
    errors that are reasonable to retry.
    """
    status_code = getattr(
        error,
        "status_code",
        None,
    )

    if status_code in {
        429,
        500,
        502,
        503,
        504,
    }:
        return True

    error_text = str(error).upper()

    return any(
        marker in error_text
        for marker in (
            "503",
            "UNAVAILABLE",
            "RESOURCE_EXHAUSTED",
            "429",
            "RATE LIMIT",
            "INTERNAL SERVER ERROR",
            "BAD GATEWAY",
            "GATEWAY TIMEOUT",
        )
    )


def _generate_with_model(
    client,
    model,
    prompt,
):
    """Generate an answer with retry handling."""
    last_error = None

    for attempt in range(
        GENERATION_MAX_RETRIES
    ):
        try:
            logger.info(
                "Generating answer with model=%s attempt=%s",
                model,
                attempt + 1,
            )

            response = (
                client.models.generate_content(
                    model=model,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        temperature=0.1,
                    ),
                )
            )

            answer = getattr(
                response,
                "text",
                None,
            )

            if not answer:
                raise RuntimeError(
                    "Gemini returned an empty answer"
                )

            return answer.strip()

        except Exception as error:
            last_error = error

            if not _is_retryable_generation_error(
                error
            ):
                raise

            if (
                attempt
                >= GENERATION_MAX_RETRIES - 1
            ):
                break

            delay = (
                GENERATION_RETRY_DELAY_SECONDS
                * (attempt + 1)
            )

            logger.warning(
                "Gemini generation failed "
                "(model=%s, attempt=%s/%s): %s. "
                "Retrying in %ss.",
                model,
                attempt + 1,
                GENERATION_MAX_RETRIES,
                error,
                delay,
            )

            time.sleep(delay)

    raise last_error


def generate_answer(question, results):
    """
    Generate a grounded answer using only the
    retrieved context.
    """
    if not results:
        return (
            "I could not find relevant information "
            "in the uploaded documents."
        )

    prompt = build_prompt(
        question,
        results,
    )

    client = get_gemini_client()

    models_to_try = [
        GENERATION_MODEL,
    ]

    if (
        GENERATION_FALLBACK_MODEL
        and GENERATION_FALLBACK_MODEL
        != GENERATION_MODEL
    ):
        models_to_try.append(
            GENERATION_FALLBACK_MODEL
        )

    last_error = None

    for model in models_to_try:
        try:
            return _generate_with_model(
                client,
                model,
                prompt,
            )

        except Exception as error:
            last_error = error

            logger.exception(
                "Gemini generation failed "
                "with model=%s",
                model,
            )

            if not _is_retryable_generation_error(
                error
            ):
                raise

    raise RuntimeError(
        "Gemini is temporarily unavailable. "
        "Please try the question again in a moment."
    ) from last_error


def ask_question(
    question,
    top_k=DEFAULT_TOP_K,
):
    """
    Complete RAG pipeline:

        question
            -> query embedding
            -> vector retrieval
            -> grounded generation
            -> structured sources
    """
    question = (
        question.strip()
        if isinstance(question, str)
        else ""
    )

    if not question:
        raise ValueError(
            "Question must not be empty"
        )

    results = retrieve_chunks(
        question,
        top_k=top_k,
    )

    answer = generate_answer(
        question,
        results,
    )

    return {
        "answer": answer,
        "sources": build_sources(results),
    }