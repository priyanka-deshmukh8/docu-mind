from pathlib import Path
from pypdf import PdfReader
from llama_index.core import Document as LlamaDocument
from sqlalchemy.orm import Session
from app.models import Document
from app.services.rag import ingest_documents


def parse_file(path: str, name: str, document_id: str, version: int, owner_id: str, allowed_users: list[str]):
    file_path = Path(path)
    metadata = {
        "document_id": document_id,
        "document_name": name,
        "version": version,
        "owner_id": owner_id,
        "allowed_users": allowed_users,
    }
    if file_path.suffix.lower() == ".pdf":
        reader = PdfReader(str(file_path))
        docs = []
        for page_no, page in enumerate(reader.pages, start=1):
            text = page.extract_text() or ""
            if text.strip():
                docs.append(LlamaDocument(text=text, metadata={**metadata, "page": page_no, "page_label": page_no}))
        return docs
    text = file_path.read_text(encoding="utf-8", errors="replace")
    return [LlamaDocument(text=text, metadata={**metadata, "page": 1})] if text.strip() else []


def run_ingestion(document_row_id: str, session_factory):
    db: Session = session_factory()
    try:
        row = db.get(Document, document_row_id)
        if not row:
            return
        row.status = "processing"
        row.error_message = None
        db.commit()
        docs = parse_file(row.file_path, row.name, row.document_id, row.version, row.owner_id, row.allowed_users)
        if not docs:
            raise ValueError("No extractable text found. For scanned PDFs, add OCR before ingestion.")
        ingest_documents(docs)
        row.status = "ready"
        db.commit()
    except Exception as exc:
        db.rollback()
        row = db.get(Document, document_row_id)
        if row:
            row.status = "failed"
            row.error_message = str(exc)[:2000]
            db.commit()
    finally:
        db.close()
