# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- **Per-request `retrieve_mode` override** on `POST /ask` and
  `POST /ask/stream`. The new optional field on `AskRequest` lets a
  client pick `vector` / `bm25` / `hybrid` for a single call without
  restarting the server, falling back to the `RETRIEVE_MODE` env var
  when omitted.
- **`eval/run_eval_modes.py`** — runs the 25-question golden set three
  times (one per mode) against the same warm corpus and writes a
  markdown table to `eval/results_modes.md`. Wired into `make eval-modes`.
- README "Retrieval modes head-to-head" section explaining when each
  branch wins and how to interpret the numbers.

## [0.2.0] - 2026-05-04

### Added

- **Hybrid retrieval (BM25 + vector + RRF)** — new default. A generated
  `chunks.text_tsv` (`tsvector`, English config) with a GIN index gives
  Postgres-side BM25-style scoring via `ts_rank_cd`; the application
  fuses it with the existing pgvector cosine ranking using Reciprocal
  Rank Fusion (Cormack et al. 2009, k=60). Queries with literal tokens
  (function names, version strings, exception names) that the embedder
  alone tends to miss now surface from the lexical branch.
- New env var `RETRIEVE_MODE` (`vector` | `bm25` | `hybrid`, default
  `hybrid`).
- New SQLAlchemy helpers `search_bm25` and `search_hybrid` plus a pure
  `reciprocal_rank_fusion()` function, unit-tested without a database.
- `rag_retrieve_latency_seconds` Prometheus histogram now carries a
  `mode` label so the three branches can be compared side-by-side.
- Alembic migration `0004_chunks_tsvector` adds the generated column
  and GIN index. Idempotent on re-runs because the rest of the schema
  is untouched.

- `POST /ask/stream` — Server-Sent Events variant of `/ask`. Emits a
  `citations` event up front (so a client can render sources before the
  model finishes), then incremental `token` events from the local LLM,
  then a terminal `done` event.
- `GET /metrics` — Prometheus text-format exposition. Tracks request
  counts (per status × rerank-mode), end-to-end `/ask` latency,
  retrieval / rerank / LLM sub-latencies, and a counter for
  "I don't know" outcomes from empty retrieval.
- New `LLMClient.stream()` protocol method, implemented by the Ollama
  client (NDJSON streaming) and the test stub.
- `scripts/demo.sh` — copy-pasteable end-to-end demo of `/health`,
  `/ingest`, `/ask`, `/ask/stream`, and `/metrics` against a running
  stack; used to record the asciinema clip in the README.

## [0.1.0] - 2026-04-30

First public release.

### Added

- `POST /ingest` endpoint accepting URL or raw body, dispatching to a
  loader chain (Markdown / HTML / PDF) and storing chunks with
  embeddings.
- `POST /ask` endpoint that retrieves top-k chunks via pgvector, builds
  a citation-aware prompt, and calls a pluggable LLM client.
- `GET /documents` and `GET /health` for introspection.
- pgvector schema with HNSW index (cosine, m=16, ef_construction=64),
  managed by Alembic migrations `0001_init`, `0002_hnsw`,
  `0003_created_at_tz`.
- Embedder backed by `bge-small-en-v1.5` (384-dim, normalized) via
  sentence-transformers with the BGE query prefix.
- Optional cross-encoder reranker (`ms-marco-MiniLM-L-6-v2`),
  enabled with `RERANK_ENABLED=true`.
- Eval harness (`eval/run_eval.py`) over 25 hand-written Q&A pairs in
  `eval/golden.json`, measuring `recall@k`, citation accuracy, keyword
  coverage, and latency.
- Multi-stage Dockerfile with CPU-only torch wheel and a non-root
  runtime user; `docker-compose.yml` orchestrating db + ollama + api.
- GitHub Actions CI: ruff, pytest with coverage, docker build.

### Eval results (FastAPI docs corpus, 16 docs / 4 042 chunks, CPU)

| metric            |  base   |   + rerank   |
|-------------------|:-------:|:------------:|
| recall@5          |  1.00   |   1.00       |
| citation accuracy |  0.52   | **0.60**     |
| keyword coverage  |  0.64   | **0.66**     |
| latency p50       | 141.7 s | **120.1 s**  |
| latency p95       | 203.7 s | **172.7 s**  |

[Unreleased]: https://github.com/KassieIII/rag-docs/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/KassieIII/rag-docs/releases/tag/v0.1.0
