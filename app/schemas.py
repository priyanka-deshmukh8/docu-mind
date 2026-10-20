from pydantic import BaseModel, Field


class DocumentOut(BaseModel):
    id: str
    document_id: str
    name: str
    owner_id: str
    allowed_users: list[str]
    version: int
    status: str
    error_message: str | None = None

    model_config = {"from_attributes": True}


class QARequest(BaseModel):
    question: str = Field(min_length=3, max_length=4000)
    top_k: int = Field(default=5, ge=1, le=15)


class Citation(BaseModel):
    document_id: str
    document_name: str
    version: int
    page: int | None = None
    excerpt: str


class QAResponse(BaseModel):
    answer: str
    citations: list[Citation]


class RetrievalTestCase(BaseModel):
    question: str
    relevant_document_ids: list[str]


class RetrievalEvaluationRequest(BaseModel):
    cases: list[RetrievalTestCase] = Field(min_length=1, max_length=100)
    top_k: int = Field(default=5, ge=1, le=20)
