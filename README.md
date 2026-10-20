# DocuMind — Enterprise Knowledge Assistant

A FastAPI starter for document ingestion and source-cited question answering with LlamaIndex, OpenAI-compatible embeddings, PostgreSQL + pgvector, document-level access controls, versioning, asynchronous ingestion, and retrieval evaluation.

## Features
- Upload PDF/TXT/Markdown documents.
- Background ingestion workflow with status tracking.
- Per-document owner and `allowed_users` access checks.
- Document version records and replacement-safe ingestion.
- LlamaIndex indexing and retrieval.
- Answers include source citations (document name, page/section metadata).
- Evaluation endpoint for retrieval hit-rate / reciprocal rank on supplied test cases.
- Docker Compose for PostgreSQL with pgvector.
- Pytest starter tests.

> This is a development starter, not a production security boundary. Add your organization's identity provider, tenant isolation policy, malware scanning, secrets management, observability, and deployment hardening before production use.

## Quick start

1. Create a virtual environment and install dependencies:

   ```bash
   python -m venv .venv
   # macOS/Linux
   source .venv/bin/activate
   # Windows PowerShell
   .venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   ```

2. Configure environment:

   ```bash
   cp .env.example .env
   ```

   Set `OPENAI_API_KEY`. `OPENAI_MODEL` and `EMBEDDING_MODEL` can be changed to models supported by your provider.

3. Start PostgreSQL + pgvector:

   ```bash
   docker compose up -d db
   ```

4. Run the API:

   ```bash
   uvicorn app.main:app --reload
   ```

5. Open `http://localhost:8000/docs`.

## API overview

- `POST /api/v1/documents` — upload a PDF/TXT/MD file; ingestion runs in the background.
- `GET /api/v1/documents` — list documents visible to the current user.
- `GET /api/v1/documents/{document_id}` — get status and version.
- `POST /api/v1/qa` — ask a question using only documents visible to the current user.
- `POST /api/v1/evaluation/retrieval` — evaluate retrieval over labeled test cases.
- `GET /health` — health check.

For this starter, the caller is identified by `X-User-Id` (default `demo-user`). Replace this development header with validated JWT/OIDC claims before exposing the service.

## Example

```bash
curl -X POST http://localhost:8000/api/v1/documents \
  -H "X-User-Id: demo-user" \
  -F "file=@./handbook.pdf" \
  -F "allowed_users=demo-user,analyst-1"
```

Wait for `status` to become `ready`, then:

```bash
curl -X POST http://localhost:8000/api/v1/qa \
  -H "Content-Type: application/json" \
  -H "X-User-Id: demo-user" \
  -d '{"question":"What is the expense approval policy?","top_k":5}'
```

## Design notes
- PostgreSQL stores document metadata and access policy.
- LlamaIndex uses PostgreSQL/pgvector as the vector store.
- Each chunk is tagged with `document_id`, `version`, `owner_id`, and `allowed_users`.
- Retrieval applies a metadata filter for the caller's visible documents; the API also validates document access before returning citation metadata.
- Ingestion uses FastAPI `BackgroundTasks` for a simple first implementation. For durable workloads, move it to Celery/RQ/Arq or a managed queue.
- Re-ingesting the same filename creates a new document record/version lineage rather than silently overwriting existing source material.
# docu-mind
