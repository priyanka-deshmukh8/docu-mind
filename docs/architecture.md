# Architecture

```text
Client / UI
    |
    v
FastAPI routes ---- identity dependency (dev header; replace with OIDC/JWT)
    |                           |
    v                           v
PostgreSQL metadata        access policy: owner / allowed users
    |
    +--> async ingestion task --> PDF/TXT/MD parser --> LlamaIndex chunking/embeddings
                                                        |
                                                        v
                                                PostgreSQL + pgvector
                                                        |
Question --> access-filtered retrieval --> LLM synthesis --> answer + citations
                                                        |
                                                        v
                                              retrieval evaluation metrics
```

## Security invariants
1. A caller may query only documents where they are the owner or appear in `allowed_users`.
2. Retrieval filters are built from the caller's visible, ready document IDs.
3. Citation payloads are derived from retrieved nodes and include source document/version metadata.
4. The `X-User-Id` header is development-only and must not be trusted in production.

## Next production steps
- Replace `Base.metadata.create_all` with Alembic migrations.
- Replace `BackgroundTasks` with a durable queue and retry/dead-letter policy.
- Add tenant IDs to every row and enforce tenant-aware filters.
- Implement delete/re-index workflows for superseded vector chunks.
- Add malware scanning, OCR for scanned PDFs, audit logs, rate limits, and structured telemetry.
- Add authorization tests for cross-user retrieval.
