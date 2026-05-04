# v0.2.0 — Hybrid retrieval, SSE streaming, Prometheus metrics

> Paste this into https://github.com/KassieIII/rag-docs/releases/new?tag=v0.2.0

Second release. Focus: production-grade retrieval depth and observability so the API is usable not just as a demo but as a measurable system.

## Highlights

### 🔀 Hybrid retrieval (BM25 + vector + RRF) — new default

Pure dense retrieval misses literal tokens (function names, version
strings, error codes). v0.2.0 adds a Postgres FTS branch and fuses it
with pgvector cosine via **Reciprocal Rank Fusion** (Cormack et al.
2009, k=60).

- New `chunks.text_tsv` generated `tsvector` column with a GIN index
  (alembic `0004_chunks_tsvector`).
- `search_bm25()` via `websearch_to_tsquery` + `ts_rank_cd`.
- Pure `reciprocal_rank_fusion()` — unit-tested without a database.
- Switch with `RETRIEVE_MODE=vector|bm25|hybrid` (default `hybrid`).
- Both branches over-fetch `4 × top_k` before fusion, with graceful
  single-branch fallback if one returns no rows.

### 📡 SSE streaming — `POST /ask/stream`

Server-Sent Events variant of `/ask`:

1. `event: citations` up front so the client can render sources before
   the model finishes.
2. `event: token` chunks streamed from the local LLM (Ollama NDJSON).
3. `event: done` to terminate.

The `LLMClient` Protocol now has a `stream()` method, implemented for
Ollama and the test stub, so CI can assert SSE shape without a model
server.

### 📊 Prometheus `/metrics`

Text-format exposition with multi-process safe registry:

- `rag_ask_requests_total{status, rerank}` — outcome counter.
- `rag_ask_latency_seconds` — end-to-end histogram.
- `rag_retrieve_latency_seconds{mode}` — retrieval per branch
  (vector / bm25 / hybrid).
- `rag_rerank_latency_seconds`, `rag_llm_latency_seconds` — sub-stage
  histograms.
- `rag_ask_no_hits_total` — counts "I don't know" outcomes from empty
  retrieval (a useful eval signal).

### 🛠 Demo script

`scripts/demo.sh` — copy-pasteable end-to-end walk-through of `/health`,
`/ingest`, `/ask`, `/ask/stream`, `/metrics`. `RECORD=1` wraps it in
asciinema. Wired into `make demo`, `make ask-stream`, `make metrics`.

## Tests & quality

- 18/18 pytest green; new RRF unit tests run without a database, so CI
  doesn't need Postgres for the fusion layer.
- ruff clean across the repo.

## Upgrade notes

```bash
git pull
alembic upgrade head      # adds chunks.text_tsv + GIN index
docker compose up -d --build
```

Set `RETRIEVE_MODE=vector` in `.env` if you want to keep the v0.1.x
behaviour exactly.

**Full Changelog**: https://github.com/KassieIII/rag-docs/compare/v0.1.0...v0.2.0
