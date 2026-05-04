"""FastAPI application entry point."""

from __future__ import annotations

import json
import logging
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException, Response
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app import metrics
from app.config import get_settings
from app.deps import get_session
from app.generate.llm import LLMClient, OllamaClient
from app.generate.prompts import SYSTEM_PROMPT, render_user_prompt
from app.ingest.loader import load_url
from app.ingest.pipeline import ingest_document
from app.models import Chunk, Document
from app.retrieve.rerank import rerank
from app.retrieve.search import Hit, search, search_bm25, search_hybrid
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
        metrics.INGEST_REQUESTS.labels(status="422").inc()
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    metrics.INGEST_REQUESTS.labels(status="200").inc()
    return IngestResponse(
        document_id=result.document_id,
        chunks=result.chunk_count,
        replaced=result.replaced,
    )


async def _retrieve(session: AsyncSession, question: str, top_k: int) -> list[Hit]:
    """Run retrieval (+ optional rerank) with metrics around each step."""
    settings = get_settings()
    # Rerank wants extra candidates; the hybrid path already over-fetches
    # internally so we only over-fetch on the pure vector / bm25 branches.
    over_fetch = top_k * 4 if settings.rerank_enabled else top_k

    t0 = time.perf_counter()
    if settings.retrieve_mode == "hybrid":
        hits = await search_hybrid(
            session,
            question,
            top_k=over_fetch,
            min_score=settings.retrieve_score_threshold,
        )
    elif settings.retrieve_mode == "bm25":
        hits = await search_bm25(session, question, top_k=over_fetch)
    else:
        hits = await search(
            session,
            question,
            top_k=over_fetch,
            min_score=settings.retrieve_score_threshold,
        )
    metrics.RETRIEVE_LATENCY.labels(mode=settings.retrieve_mode).observe(
        time.perf_counter() - t0
    )

    if settings.rerank_enabled and hits:
        t1 = time.perf_counter()
        hits = rerank(question, hits, top_k=top_k)
        metrics.RERANK_LATENCY.observe(time.perf_counter() - t1)
    elif len(hits) > top_k:
        hits = hits[:top_k]
    return hits


def _citations(hits: list[Hit]) -> list[Citation]:
    return [
        Citation(
            chunk_id=h.chunk_id,
            document_id=h.document_id,
            source=h.source,
            heading=h.heading,
            score=round(h.score, 4),
            text=h.text,
        )
        for h in hits
    ]


@app.post("/ask", response_model=AskResponse)
async def ask(
    body: AskRequest,
    session: AsyncSession = Depends(get_session),
    llm: LLMClient = Depends(get_llm),
) -> AskResponse:
    settings = get_settings()
    rerank_label = "on" if settings.rerank_enabled else "off"
    t_start = time.perf_counter()
    try:
        hits = await _retrieve(session, body.question, body.top_k)
        if not hits:
            metrics.ASK_NO_HITS.inc()
            metrics.ASK_REQUESTS.labels(status="200", rerank=rerank_label).inc()
            return AskResponse(
                answer="I don't know based on the provided documentation.",
                citations=[],
            )
        user_prompt = render_user_prompt(body.question, hits)
        t_llm = time.perf_counter()
        answer = await llm.generate(system=SYSTEM_PROMPT, user=user_prompt)
        metrics.LLM_LATENCY.observe(time.perf_counter() - t_llm)
        metrics.ASK_REQUESTS.labels(status="200", rerank=rerank_label).inc()
        return AskResponse(answer=answer, citations=_citations(hits))
    except Exception:
        metrics.ASK_REQUESTS.labels(status="500", rerank=rerank_label).inc()
        raise
    finally:
        metrics.ASK_LATENCY.observe(time.perf_counter() - t_start)


@app.post("/ask/stream")
async def ask_stream(
    body: AskRequest,
    session: AsyncSession = Depends(get_session),
    llm: LLMClient = Depends(get_llm),
) -> StreamingResponse:
    """Server-sent-events variant of /ask.

    Event order:
      1. ``citations`` — the retrieved chunks (so the client can render
         them immediately, before the LLM finishes).
      2. ``token`` (one or more) — incremental answer text.
      3. ``done`` — terminal marker; safe to close the connection.
    """
    settings = get_settings()
    rerank_label = "on" if settings.rerank_enabled else "off"

    async def event_stream() -> AsyncIterator[bytes]:
        t_start = time.perf_counter()
        try:
            hits = await _retrieve(session, body.question, body.top_k)
            citations_payload = [c.model_dump() for c in _citations(hits)]
            yield _sse("citations", {"citations": citations_payload})

            if not hits:
                metrics.ASK_NO_HITS.inc()
                yield _sse(
                    "token",
                    {"text": "I don't know based on the provided documentation."},
                )
                yield _sse("done", {})
                metrics.ASK_REQUESTS.labels(status="200", rerank=rerank_label).inc()
                return

            user_prompt = render_user_prompt(body.question, hits)
            t_llm = time.perf_counter()
            async for piece in llm.stream(system=SYSTEM_PROMPT, user=user_prompt):
                yield _sse("token", {"text": piece})
            metrics.LLM_LATENCY.observe(time.perf_counter() - t_llm)
            yield _sse("done", {})
            metrics.ASK_REQUESTS.labels(status="200", rerank=rerank_label).inc()
        except Exception as exc:
            metrics.ASK_REQUESTS.labels(status="500", rerank=rerank_label).inc()
            yield _sse("error", {"message": str(exc)})
        finally:
            metrics.ASK_LATENCY.observe(time.perf_counter() - t_start)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


def _sse(event: str, data: dict) -> bytes:
    """Format a single SSE message frame."""
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n".encode()


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


@app.get("/metrics")
async def prometheus_metrics() -> Response:
    """Prometheus text-format exposition endpoint."""
    payload, content_type = metrics.render()
    return Response(content=payload, media_type=content_type)
