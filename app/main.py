"""FastAPI application entry point."""

from __future__ import annotations

import logging

from fastapi import Depends, FastAPI
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import get_session
from app.generate.llm import LLMClient, OllamaClient
from app.generate.prompts import SYSTEM_PROMPT, render_user_prompt
from app.retrieve.search import search
from app.schemas import AskRequest, AskResponse, Citation

log = logging.getLogger("rag-docs")
_llm: LLMClient = OllamaClient()


def get_llm() -> LLMClient:
    return _llm


app = FastAPI(
    title="rag-docs",
    version="0.1.0",
    description="Ask-your-docs RAG service.",
)


@app.post("/ask", response_model=AskResponse)
async def ask(
    body: AskRequest,
    session: AsyncSession = Depends(get_session),
    llm: LLMClient = Depends(get_llm),
) -> AskResponse:
    hits = await search(session, body.question, top_k=body.top_k)
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
