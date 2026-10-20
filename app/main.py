import os
import uuid
from pathlib import Path
from fastapi import BackgroundTasks, Depends, FastAPI, File, Form, HTTPException, UploadFile
from sqlalchemy import desc, select
from sqlalchemy.orm import Session
from app.config import settings
from app.db import Base, SessionLocal, engine, get_db
from app.models import Document
from app.schemas import DocumentOut, QARequest, QAResponse, Citation, RetrievalEvaluationRequest
from app.security import current_user_id
from app.services.ingestion import run_ingestion
from app.services.rag import answer_question, retrieve_document_ids

app = FastAPI(title="DocuMind API", version="0.1.0", description="Enterprise knowledge assistant with RAG and source citations")


@app.on_event("startup")
def startup():
    # Simple development bootstrap. Use Alembic migrations for production.
    with engine.begin() as conn:
        conn.exec_driver_sql("CREATE EXTENSION IF NOT EXISTS vector")
    Base.metadata.create_all(bind=engine)
    Path(settings.upload_dir).mkdir(parents=True, exist_ok=True)


def can_access(row: Document, user_id: str) -> bool:
    return row.owner_id == user_id or user_id in (row.allowed_users or [])


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/api/v1/documents", response_model=DocumentOut, status_code=202)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    allowed_users: str = Form(default=""),
    db: Session = Depends(get_db),
    user_id: str = Depends(current_user_id),
):
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in {".pdf", ".txt", ".md"}:
        raise HTTPException(status_code=415, detail="Supported file types: PDF, TXT, MD")
    content = await file.read()
    if len(content) > settings.max_upload_mb * 1024 * 1024:
        raise HTTPException(status_code=413, detail=f"File exceeds {settings.max_upload_mb} MB limit")
    if not content:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")
    safe_name = Path(file.filename or "document").name[:255]
    document_id = str(uuid.uuid4())
    file_path = Path(settings.upload_dir) / f"{document_id}{suffix}"
    file_path.write_bytes(content)
    shared_with = sorted({x.strip() for x in allowed_users.split(",") if x.strip() and x.strip() != user_id})
    row = Document(
        document_id=document_id,
        name=safe_name,
        content_type=file.content_type or "application/octet-stream",
        owner_id=user_id,
        allowed_users=shared_with,
        version=1,
        status="queued",
        file_path=str(file_path),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    background_tasks.add_task(run_ingestion, row.id, SessionLocal)
    return row


@app.get("/api/v1/documents", response_model=list[DocumentOut])
def list_documents(db: Session = Depends(get_db), user_id: str = Depends(current_user_id)):
    rows = db.scalars(select(Document).order_by(desc(Document.created_at))).all()
    return [row for row in rows if can_access(row, user_id)]


@app.get("/api/v1/documents/{row_id}", response_model=DocumentOut)
def get_document(row_id: str, db: Session = Depends(get_db), user_id: str = Depends(current_user_id)):
    row = db.get(Document, row_id)
    if not row or not can_access(row, user_id):
        raise HTTPException(status_code=404, detail="Document not found")
    return row


@app.post("/api/v1/qa", response_model=QAResponse)
def ask_question(request: QARequest, db: Session = Depends(get_db), user_id: str = Depends(current_user_id)):
    rows = db.scalars(select(Document).where(Document.status == "ready")).all()
    visible = [r for r in rows if can_access(r, user_id)]
    if not visible:
        return QAResponse(answer="No ready documents are available to you yet.", citations=[])
    try:
        answer, citations = answer_question(request.question, list({r.document_id for r in visible}), request.top_k)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    return QAResponse(answer=answer, citations=[Citation(**c) for c in citations])


@app.post("/api/v1/evaluation/retrieval")
def evaluate_retrieval(request: RetrievalEvaluationRequest, db: Session = Depends(get_db), user_id: str = Depends(current_user_id)):
    rows = db.scalars(select(Document).where(Document.status == "ready")).all()
    visible = [r for r in rows if can_access(r, user_id)]
    visible_ids = list({r.document_id for r in visible})
    if not visible_ids:
        raise HTTPException(status_code=400, detail="No ready documents available for evaluation")
    hits = 0
    reciprocal_ranks = []
    evaluated = []
    for case in request.cases:
        try:
            retrieved = retrieve_document_ids(case.question, visible_ids, request.top_k)
        except RuntimeError as exc:
            raise HTTPException(status_code=503, detail=str(exc))
        relevant = set(case.relevant_document_ids) & set(visible_ids)
        rank = next((i + 1 for i, doc_id in enumerate(retrieved) if doc_id in relevant), None)
        hit = rank is not None
        hits += int(hit)
        reciprocal_ranks.append(1 / rank if rank else 0.0)
        evaluated.append({"question": case.question, "hit": hit, "first_relevant_rank": rank, "retrieved_document_ids": retrieved})
    n = len(request.cases)
    return {"case_count": n, "hit_rate_at_k": hits / n, "mean_reciprocal_rank": sum(reciprocal_ranks) / n, "results": evaluated}
