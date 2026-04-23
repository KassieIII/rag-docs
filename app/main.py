"""FastAPI application entry point."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.deps import get_session
from app.generate.llm import LLMClient, OllamaClient
from app.generate.prompts import SYSTEM_PROMPT, render_user_prompt
from app.ingest.loader import load_url
from app.ingest.pipeline import ingest_document
from app.models import Chunk, Document
from app.retrieve.rerank import rerank
from app.retrieve.search import search
from app.schemas import (
    AskRequest,
    AskResponse,
    Citation,
    DocumentSummary,
    HealthResponse,
    IngestRequest,
    IngestResponse,
)

log = logging.getLogger("rag-docs")
_llm: LLMClient = OllamaClient()


def get_llm() -> LLMClient:
    return _llm


@asynccontextmanager
async def lifespan(_: FastAPI):
    log.info("rag-docs starting; model=%s", get_settings().embed_model)
    yield


app = FastAPI(
    title="rag-docs",
    version="0.1.0",
    description="Ask-your-docs RAG service.",
    lifespan=lifespan,
)


@app.post("/ingest", response_model=IngestResponse)
async def ingest(
    body: IngestRequest,
    session: AsyncSession = Depends(get_session),
) -> IngestResponse:
    loaded = await load_url(str(body.url))
    if body.title:
        loaded = loaded.__class__(
            source=loaded.source,
            title=body.title,
            content_type=loaded.content_type,
            text=loaded.text,
        )
    try:
        result = await ingest_document(session, loaded)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return IngestResponse(
        document_id=result.document_id,
        chunks=result.chunk_count,
        replaced=result.replaced,
    )


@app.post("/ask", response_model=AskResponse)
async def ask(
    body: AskRequest,
    session: AsyncSession = Depends(get_session),
    llm: LLMClient = Depends(get_llm),
) -> AskResponse:
    settings = get_settings()
    over_fetch = body.top_k * 4 if settings.rerank_enabled else body.top_k
    hits = await search(session, body.question, top_k=over_fetch)
    if settings.rerank_enabled and hits:
        hits = rerank(body.question, hits, top_k=body.top_k)
    if not hits:
        return AskResponse(
            answer="I don't know based on the provided documentation.",
            citations=[],
        )
    user_prompt = render_user_prompt(body.question, hits)
    answer = await llm.generate(system=SYSTEM_PROMPT, user=user_prompt)
    return AskResponse(
        answer=answer,
        citations=[
            Citation(
                chunk_id=h.chunk_id,
                document_id=h.document_id,
                source=h.source,
                heading=h.heading,
                score=round(h.score, 4),
                text=h.text,
            )
            for h in hits
        ],
    )


@app.get("/documents", response_model=list[DocumentSummary])
async def list_documents(
    session: AsyncSession = Depends(get_session),
) -> list[DocumentSummary]:
    stmt = (
        select(
            Document.id,
            Document.source,
            Document.title,
            Document.content_type,
            func.count(Chunk.id).label("chunks"),
        )
        .join(Chunk, Chunk.document_id == Document.id, isouter=True)
        .group_by(Document.id)
        .order_by(Document.id.desc())
    )
    result = await session.execute(stmt)
    return [
        DocumentSummary(
            id=row.id,
            source=row.source,
            title=row.title,
            content_type=row.content_type,
            chunks=row.chunks,
        )
        for row in result
    ]


@app.get("/health", response_model=HealthResponse)
async def health(
    session: AsyncSession = Depends(get_session),
    llm: LLMClient = Depends(get_llm),
) -> HealthResponse:
    db_ok = True
    try:
        await session.execute(select(1))
    except Exception:
        db_ok = False
    # Embedder check is intentionally cheap: don't load the model on /health.
    embedder_ok = bool(get_settings().embed_model)
    llm_ok = await llm.health()
    return HealthResponse(db=db_ok, embedder=embedder_ok, llm=llm_ok)
