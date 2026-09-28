# Doc QA RAG

A full-stack Retrieval-Augmented Generation (RAG) application for asking questions about uploaded PDF documents.

The application extracts text from PDFs, splits it into page-aware chunks, generates vector embeddings with Gemini, stores them in PostgreSQL with pgvector, retrieves relevant passages for a question, and generates a grounded answer with source citations.

## Architecture

```text
                    ┌──────────────────┐
                    │   React + TypeScript
                    │     Frontend      │
                    └────────┬─────────┘
                             │ HTTP
                             ▼
                    ┌──────────────────┐
                    │   Flask REST API │
                    └────────┬─────────┘
                             │
              ┌──────────────┴──────────────┐
              │                             │
              ▼                             ▼
       ┌──────────────┐              ┌──────────────┐
       │ PDF Ingestion│              │ RAG Retrieval│
       └──────┬───────┘              └──────┬───────┘
              │                             │
              ▼                             ▼
       ┌──────────────┐              ┌──────────────┐
       │ Page-aware   │              │ Gemini Query │
       │ Chunking     │              │ Embedding    │
       └──────┬───────┘              └──────┬───────┘
              │                             │
              ▼                             ▼
       ┌────────────────────────────────────────────┐
       │          PostgreSQL + pgvector             │
       └────────────────────┬───────────────────────┘
                            │
                            ▼
                    ┌──────────────┐
                    │ Gemini       │
                    │ Generation   │
                    └──────────────┘
```

## Features

* PDF document uploads
* Upload size restrictions
* PDF extension and file-signature validation
* Secure filenames
* Temporary-file handling
* Page-aware PDF extraction
* Overlapping text chunking
* Gemini embeddings
* PostgreSQL + pgvector vector search
* Grounded RAG responses
* Page-aware source citations
* Structured JSON API errors
* Health and readiness endpoints
* Database transaction rollback on ingestion failures
* CORS configuration
* Automated pytest tests
* PostgreSQL/pgvector integration tests
* GitHub Actions CI
* Coverage reporting

## Technology Stack

### Backend

* Python
* Flask
* SQLAlchemy
* PostgreSQL
* pgvector
* PyPDF
* Google Gemini API

### Frontend

* React
* TypeScript
* Vite

### Testing / CI

* pytest
* pytest-cov
* GitHub Actions
* PostgreSQL + pgvector

## Project Structure

```text
doc-qa-rag/
│
├── app.py
├── ingest.py
├── models.py
├── retrieve.py
├── requirements.txt
├── .env.example
├── .gitignore
├── pytest.ini
├── README.md
│
├── tests/
│   ├── conftest.py
│   ├── test_app.py
│   ├── test_ingest.py
│   ├── test_ingest_integration.py
│   └── test_retrieve.py
│
└── .github/
    └── workflows/
        └── ci.yml
```

## Requirements

Before running the application, install:

* Python 3.12+
* PostgreSQL 16+
* pgvector PostgreSQL extension
* Node.js 20+ for the frontend
* A Gemini API key

## Environment Variables

Create a local `.env` file from `.env.example`.

```dotenv
GEMINI_API_KEY=your_gemini_api_key
GEMINI_GENERATION_MODEL=gemini-2.5-flash

DATABASE_URL=postgresql://username:password@localhost:5432/docqa

FLASK_ENV=development
SECRET_KEY=change-this-in-production

MAX_UPLOAD_MB=10

CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
```

Never commit `.env` or API keys to Git.

## Database Setup

Create a PostgreSQL database:

```sql
CREATE DATABASE docqa;
```

Enable pgvector:

```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

Then configure:

```dotenv
DATABASE_URL=postgresql://username:password@localhost:5432/docqa
```

## Backend Setup

Create and activate a virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Start the backend:

```bash
python app.py
```

The API will normally be available at:

```text
http://localhost:5000
```

## API

### Health

```http
GET /health
```

Example:

```json
{
  "status": "ok"
}
```

### Readiness

```http
GET /ready
```

The readiness endpoint verifies that the application can communicate with PostgreSQL.

### List Documents

```http
GET /api/documents
```

### Upload PDF

```http
POST /api/upload
Content-Type: multipart/form-data
```

Form field:

```text
file=<PDF>
```

The server validates:

* file presence
* filename
* `.pdf` extension
* PDF file signature
* maximum upload size

### Ask a Question

```http
POST /api/ask
Content-Type: application/json
```

Request:

```json
{
  "question": "What does the document say about the project?"
}
```

Response:

```json
{
  "answer": "The document states ... [SOURCE 1]",
  "sources": [
    {
      "id": 12,
      "document_id": 3,
      "document": "example.pdf",
      "page": 4,
      "chunk": 2,
      "content": "Relevant document content...",
      "distance": 0.123456,
      "citation": "example.pdf, page 4"
    }
  ]
}
```

## RAG Pipeline

### 1. Upload

A PDF is uploaded through the Flask API.

### 2. Validation

The API checks the filename, extension, PDF signature, and upload size.

### 3. Extraction

PyPDF extracts text while preserving the source page number.

### 4. Chunking

Text is divided into overlapping chunks.

Current defaults:

```text
Chunk size: 800 characters
Overlap:    150 characters
```

### 5. Embedding

Each chunk is embedded with:

```text
gemini-embedding-001
```

The application uses 768-dimensional vectors.

### 6. Storage

Documents, chunks, page metadata, and embeddings are stored in PostgreSQL.

pgvector performs similarity search over the embeddings.

### 7. Retrieval

A user's question is embedded using the same embedding model.

The most relevant document chunks are retrieved using cosine distance.

### 8. Generation

The retrieved context is passed to Gemini with instructions to answer only from the supplied document context.

### 9. Citations

The generated answer can reference retrieved passages using:

```text
[SOURCE 1]
[SOURCE 2]
```

The API also returns the document filename and page number for each source.

## Testing

Configure a PostgreSQL test database:

```bash
createdb docqa_test
```

Enable pgvector:

```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

Set:

```bash
export TEST_DATABASE_URL="postgresql://postgres:postgres@localhost:5432/docqa_test"
```

Run tests:

```bash
pytest
```

Run with coverage:

```bash
pytest --cov=. --cov-report=term-missing
```

The test suite includes:

* API validation
* health checks
* readiness checks
* PDF validation
* chunking
* database rollback
* page metadata
* vector retrieval
* RAG generation
* source citations
* PostgreSQL/pgvector integration

Gemini calls are mocked in tests so the test suite does not require a production Gemini API key.

Run frontend tests and checks from the `frontend` directory:

```bash
npm test
npm run lint
npm run build
```

The frontend tests cover API request/response handling and the document upload, question, and source-display workflow.

## CI

GitHub Actions runs automatically on pushes and pull requests.

The CI pipeline:

1. Starts PostgreSQL with pgvector.
2. Installs Python dependencies.
3. Verifies the database connection.
4. Runs pytest.
5. Generates coverage information.
6. Uploads the coverage report.

Workflow:

```text
.github/workflows/ci.yml
```

## Security Considerations

The application includes several basic protections:

* Maximum upload size
* PDF extension validation
* PDF signature validation
* Secure filenames
* Temporary upload files
* Environment-based secrets
* Database rollback on ingestion failure
* CORS configuration
* Structured API errors

For production deployment, additional protections should be considered, including:

* authentication and authorization
* rate limiting
* malware scanning
* persistent object storage
* database migrations
* HTTPS
* stronger request validation
* observability and audit logging

## Deployment

The application can be deployed as separate frontend and backend services.

A typical architecture is:

```text
React / Vite
    │
    │ HTTPS
    ▼
Frontend Hosting
    │
    │ API requests
    ▼
Flask Backend
    │
    ├──────────────► Gemini API
    │
    ▼
PostgreSQL + pgvector
```

The frontend should use an environment variable for the backend API URL rather than hard-coding a production URL.

The backend should receive its secrets through the deployment platform's environment-variable configuration.

## Development Roadmap

Potential future improvements:

* Database migrations with Alembic
* Streaming RAG responses
* Document deletion
* Duplicate-document detection
* OCR for scanned PDFs
* Batch embedding
* Hybrid keyword + vector retrieval
* Reranking
* Retrieval evaluation datasets
* RAGAS or similar evaluation metrics
* Authentication
* Rate limiting
* Background ingestion jobs
* Persistent object storage
* Production observability

## License

Add the project's chosen license here before publishing the application for public reuse.
