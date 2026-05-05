"""Pydantic request/response schemas for the HTTP API."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, HttpUrl

RetrieveModeName = Literal["vector", "bm25", "hybrid"]


class IngestRequest(BaseModel):
    url: HttpUrl = Field(description="Public URL of a Markdown, HTML, or PDF document.")
    title: str | None = Field(default=None, max_length=512)


class IngestResponse(BaseModel):
    document_id: int
    chunks: int
    replaced: bool


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    top_k: int = Field(default=5, ge=1, le=20)
    retrieve_mode: RetrieveModeName | None = Field(
        default=None,
        description=(
            "Per-request override for the retrieval strategy. When omitted, "
            "the server falls back to the RETRIEVE_MODE env var. Used by "
            "the eval harness to compare modes against the same corpus."
        ),
    )


class Citation(BaseModel):
    chunk_id: int
    document_id: int
    source: str
    heading: str | None
    score: float
    text: str


class AskResponse(BaseModel):
    answer: str
    citations: list[Citation]


class HealthResponse(BaseModel):
    db: bool
    embedder: bool
    llm: bool

    @property
    def ok(self) -> bool:
        return self.db and self.embedder and self.llm


class DocumentSummary(BaseModel):
    id: int
    source: str
    title: str | None
    content_type: str
    chunks: int
