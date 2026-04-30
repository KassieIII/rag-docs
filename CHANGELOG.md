# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
