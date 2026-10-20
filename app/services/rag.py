from functools import lru_cache
from typing import Any
from llama_index.core import VectorStoreIndex
from llama_index.core.vector_stores import MetadataFilters, MetadataFilter, FilterOperator
from llama_index.core.storage.storage_context import StorageContext
from llama_index.embeddings.openai import OpenAIEmbedding
from llama_index.llms.openai import OpenAI
from llama_index.vector_stores.postgres import PGVectorStore
from app.config import settings
from sqlalchemy.engine import make_url


@lru_cache(maxsize=1)
def get_vector_store():
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY is missing. Set it in .env before ingestion or QA.")
    url = make_url(settings.database_url)
    return PGVectorStore.from_params(
        database=url.database or "documind",
        host=url.host or "localhost",
        password=url.password or "",
        port=url.port or 5432,
        user=url.username or "documind",
        table_name=settings.vector_table,
        embed_dim=1536,
        hybrid_search=False,
        text_search_config="english",
    )

def _components():
    embedding = OpenAIEmbedding(model=settings.embedding_model, api_key=settings.openai_api_key)
    llm = OpenAI(model=settings.openai_model, api_key=settings.openai_api_key, temperature=0)
    return embedding, llm


def ingest_documents(documents: list[Any]) -> None:
    embedding, _ = _components()
    vector_store = get_vector_store()
    storage_context = StorageContext.from_defaults(vector_store=vector_store)
    index = VectorStoreIndex.from_documents(
        documents,
        storage_context=storage_context,
        embed_model=embedding,
        show_progress=False,
    )
    # Index construction persists chunks through the configured vector store.
    return None


def answer_question(question: str, visible_doc_ids: list[str], top_k: int) -> tuple[str, list[dict]]:
    if not visible_doc_ids:
        return "I couldn't find any documents you have permission to access.", []
    embedding, llm = _components()
    index = VectorStoreIndex.from_vector_store(get_vector_store(), embed_model=embedding)
    filters = MetadataFilters(filters=[
        MetadataFilter(key="document_id", value=doc_id, operator=FilterOperator.EQ)
        for doc_id in visible_doc_ids
    ])
    # Use OR semantics across allowed document IDs where supported by the installed LlamaIndex version.
    try:
        from llama_index.core.vector_stores import FilterCondition
        filters.condition = FilterCondition.OR
    except Exception:
        pass
    retriever = index.as_retriever(similarity_top_k=top_k, filters=filters)
    nodes = retriever.retrieve(question)
    if not nodes:
        return "I couldn't find a relevant answer in the documents you can access.", []
    from llama_index.core.query_engine import RetrieverQueryEngine
    from llama_index.core.response_synthesizers import get_response_synthesizer
    engine = RetrieverQueryEngine(
        retriever=retriever,
        response_synthesizer=get_response_synthesizer(llm=llm, response_mode="compact"),
    )
    response = engine.query(question)
    citations = []
    seen = set()
    for node in nodes:
        meta = node.node.metadata or {}
        key = (str(meta.get("document_id", "")), int(meta.get("version", 1)), node.node_id)
        if key in seen:
            continue
        seen.add(key)
        citations.append({
            "document_id": str(meta.get("document_id", "")),
            "document_name": str(meta.get("document_name", "Unknown document")),
            "version": int(meta.get("version", 1)),
            "page": meta.get("page_label") or meta.get("page"),
            "excerpt": node.node.get_text()[:500],
        })
    return str(response), citations


def retrieve_document_ids(question: str, visible_doc_ids: list[str], top_k: int) -> list[str]:
    if not visible_doc_ids:
        return []
    embedding, _ = _components()
    index = VectorStoreIndex.from_vector_store(get_vector_store(), embed_model=embedding)
    from llama_index.core.vector_stores import FilterCondition
    filters = MetadataFilters(
        filters=[MetadataFilter(key="document_id", value=x, operator=FilterOperator.EQ) for x in visible_doc_ids],
        condition=FilterCondition.OR,
    )
    nodes = index.as_retriever(similarity_top_k=top_k, filters=filters).retrieve(question)
    return [str(n.node.metadata.get("document_id")) for n in nodes if n.node.metadata.get("document_id")]
