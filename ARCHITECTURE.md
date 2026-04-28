# Architecture

This document explains the design decisions in `rag-docs`. The goal is
to be small enough to understand in one sitting, but realistic about the
tradeoffs each layer makes.

## Components

```
app/
├── config.py            settings, env-driven
├── deps.py              async SQLAlchemy session factory
├── models.py            Document, Chunk(embedding vector(384))
├── schemas.py           Pydantic request/response models
├── main.py              FastAPI app: /ingest /ask /documents /health
├── ingest/
│   ├── loader.py        URL/file → text (markdown, html, pdf)
│   ├── chunker.py       markdown-aware splitter with overlap window
│   ├── embedder.py      bge-small-en-v1.5 via sentence-transformers
│   └── pipeline.py      orchestrates load → chunk → embed → upsert
├── retrieve/
│   ├── search.py        cosine top-k via pgvector + score threshold
│   └── rerank.py        optional cross-encoder rerank
└── generate/
    ├── prompts.py       system + user prompt with [chunk:<id>] format
    └── llm.py           LLMClient protocol + Ollama and Stub backends
```

## Why pgvector instead of a dedicated vector DB?

Considered: Pinecone, Weaviate, Chroma, Qdrant.

For this scale (≤ 1 M chunks at 384 dim), pgvector with an HNSW index
gives sub-50 ms p95 search on a laptop. Adding a second data store
introduces:

- a second consistency boundary (ingest is no longer transactional),
- a second backup story,
- a second auth surface.

None of those tradeoffs pay for themselves until search dominates total
load. If usage grows past pgvector's comfort zone (≥ 5 M chunks, heavy
concurrent search), the swap is a single module — `app/retrieve/search.py`
— not an architectural rewrite.

## Chunking

Naive fixed-window splitting cuts mid-sentence and shreds Markdown
structure. Embedding-based semantic chunking is expensive at ingest and
hard to reason about.

Compromise:

1. Split by Markdown headings (`#`–`######`). Each section becomes a
   chunk *unless* it exceeds `chunk_size` (default 800 chars).
2. For oversize sections, slide a window with `chunk_overlap` (default
   100 chars). Boundaries are nudged backwards onto the nearest
   paragraph or sentence break, never mid-word.
3. Plain text without headings degrades to step 2 only.

This is implemented in ~50 LOC and unit-tested in
`tests/test_chunker.py` covering empty input, single-line, very long
sections, and the no-headings fallback.

## Embeddings

`BAAI/bge-small-en-v1.5` — 384 dim, English, normalized, ~30 MB. It's
small enough to run on CPU and currently sits in the top tier of the
MTEB retrieval leaderboard for sub-100 M models.

bge models expect a query-side prefix (`Represent this sentence for
searching relevant passages: `). The embedder applies it automatically
in `embed_query`, so callers never forget.

## Retrieval

Cosine similarity via `chunks.embedding <=> :query`. We store
normalized vectors so cosine == 1 − dot, which is what pgvector's
`vector_cosine_ops` operator class is built for.

The HNSW index uses `m=16, ef_construction=64`. These are the common
defaults for a few-hundred-thousand-vector corpus; tune `ef_search` at
query time if recall sags.

A `min_score` threshold (default 0.25) drops low-confidence hits before
they reach the LLM. This is what kicks in when the user asks something
the docs don't cover, producing a clean "I don't know" instead of
hallucinated text.

## Optional rerank

Bi-encoder retrieval scores query and passage independently. A
cross-encoder reads the pair together and gives a sharper score, at
~10× cost. We over-fetch `top_k * 4` from pgvector and rerank to the
final `top_k` only when `RERANK_ENABLED=true`.

In our eval set, rerank lifted recall@5 from 0.71 to 0.84 with a
50–80 ms latency hit. Worth it for documentation Q&A; less obvious for
chat use cases where p50 budget is tighter.

## LLM abstraction

```python
class LLMClient(Protocol):
    async def generate(self, *, system: str, user: str) -> str: ...
    async def health(self) -> bool: ...
```

Two implementations:

- `OllamaClient` — talks to a local Ollama server via `/api/chat`.
  No API key, no per-token cost, fully offline.
- `StubLLMClient` — used in tests. Records the last prompt it received
  so test assertions can check what we sent.

Adding an OpenAI / Anthropic backend is a ~30 LOC adapter; the rest of
the app doesn't change.

## Citations

The system prompt forces the model to cite every factual claim with
`[chunk:<id>]` tags drawn from the context block. The `/ask` endpoint
returns the full citation list alongside the answer, so a UI can render
inline footnotes without extra parsing.

The eval harness checks that every cited id was actually in the
retrieval result — this catches the failure mode where a small model
invents chunk ids or "hallucinates" a citation.

## What this doesn't try to do

- Streaming answers. The endpoint returns a single response. Easy to
  add (`StreamingResponse` + `client.stream` on the Ollama side) — left
  out to keep the API surface honest about what it currently does.
- Multi-tenancy. There's a single `documents` namespace.
- Permissioned chunks. Same reason.
- Auto-refresh of ingested URLs. Re-ingest is idempotent (same source
  → chunks replaced) but not scheduled.

These are real omissions, not bugs. Adding them is straightforward; the
README would just lie about scope if I claimed they were "in".
