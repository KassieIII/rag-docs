# rag-docs

Ask-your-docs RAG service. Ingest Markdown / HTML / PDF, retrieve with
**pgvector**, answer with a **local LLM** (Ollama). ~700 LOC of typed
Python, single `docker compose up`, no vendor lock-in, no API keys
required.

[![CI](https://github.com/KassieIII/rag-docs/actions/workflows/ci.yml/badge.svg)](https://github.com/KassieIII/rag-docs/actions/workflows/ci.yml)
[![Release](https://img.shields.io/github/v/release/KassieIII/rag-docs?display_name=tag&sort=semver)](https://github.com/KassieIII/rag-docs/releases)
[![codecov](https://codecov.io/gh/KassieIII/rag-docs/branch/main/graph/badge.svg)](https://codecov.io/gh/KassieIII/rag-docs)
![Python](https://img.shields.io/badge/python-3.13-3776ab)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688)
![pgvector](https://img.shields.io/badge/pgvector-HNSW-4169e1)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
![License](https://img.shields.io/badge/license-MIT-green)

---

## Why another RAG demo?

Most RAG repos hide quality behind a chatbot UI. This one ships:

- **Eval harness** with 25 golden Q&A pairs and a `run_eval.py` script that
  measures `recall@k`, citation accuracy, keyword coverage, and latency.
- **Honest metrics** in the README — see [Eval results](#eval-results).
- **Pluggable LLM**: production uses Ollama (free, local), tests use a
  `StubLLMClient` so CI runs without a model server.
- **pgvector + HNSW** instead of a separate vector DB — one Postgres,
  transactional ingest, < 50 ms p95 up to ~1 M chunks.
- **Citations are first-class**: every answer references chunks by
  `[chunk:<id>]`, and the API returns the citation list alongside.

---

## Quick start

```bash
git clone https://github.com/KassieIII/rag-docs.git
cd rag-docs

cp .env.example .env
docker compose up -d --build

# pull a small local model (~2 GB, one time)
make model-pull MODEL=llama3.2:3b

# create the schema
make migrate

# ingest a doc
make ingest URL=https://raw.githubusercontent.com/tiangolo/fastapi/master/docs/en/docs/tutorial/first-steps.md

# ask
make ask QUESTION="How do I declare a path parameter?"
```

Sample response:

```json
{
  "answer": "Use a curly-brace placeholder in the path string and accept a parameter of the same name in the function [chunk:14].",
  "citations": [
    {
      "chunk_id": 14,
      "source": ".../path-params.md",
      "heading": "Path parameters",
      "score": 0.78,
      "text": "..."
    }
  ]
}
```

---

## Architecture

```
              ┌──────────────┐    embed      ┌────────────┐
   /ingest ──▶│ load + chunk │──────────────▶│  bge-small │
              └──────────────┘               └─────┬──────┘
                                                   │ vectors
                                                   ▼
                                    ┌────────────────────────┐
                                    │ Postgres + pgvector    │
                                    │  documents · chunks    │
                                    │  HNSW(vector_cosine)   │
                                    └────────┬───────────────┘
                                             │ top-k
                                             ▼
   /ask  ──▶ embed query ──▶ search ──▶ (rerank?) ──▶ Ollama ──▶ cited answer
```

See [ARCHITECTURE.md](./ARCHITECTURE.md) for chunking strategy, prompt
design, and why pgvector beat the alternatives I considered.

---

## API

| Method | Path         | Body                                              | Returns |
|--------|--------------|---------------------------------------------------|---------|
| POST   | `/ingest`    | `{"url": "...", "title": "?"}`                    | `{document_id, chunks, replaced}` |
| POST   | `/ask`       | `{"question": "...", "top_k": 5}`                 | `{answer, citations[]}` |
| GET    | `/documents` | —                                                 | `[{id, source, title, chunks}]` |
| GET    | `/health`    | —                                                 | `{db, embedder, llm}` |

Full OpenAPI at `http://localhost:8000/docs` once the API is up.

---

## Eval results

Ingested: FastAPI documentation pages (16 documents, 4 042 chunks).
Hardware: laptop CPU, no GPU. Embedder: `bge-small-en-v1.5` (384-dim).
LLM: `llama3.2:3b` via Ollama. Rerank: `cross-encoder/ms-marco-MiniLM-L-6-v2`.
Eval set: 25 hand-written Q&A pairs in
[`eval/golden.json`](eval/golden.json), see raw output in
[`eval/results_baseline.txt`](eval/results_baseline.txt) and
[`eval/results_rerank.txt`](eval/results_rerank.txt).

| metric            |  base   |   + rerank   |
|-------------------|:-------:|:------------:|
| recall@5          |  1.00   |   1.00       |
| citation accuracy |  0.52   | **0.60**     |
| keyword coverage  |  0.64   | **0.66**     |
| latency p50       | 141.7 s | **120.1 s**  |
| latency p95       | 203.7 s | **172.7 s**  |

Notes on the honest read:

- `recall@5 = 1.00` is high because the corpus is small and topical;
  on a wider corpus we expect this to drop into the 0.7–0.9 range.
- `citation_acc` is the weak spot: `llama3.2:3b` frequently paraphrases
  without emitting `[chunk:N]` markers. Rerank lifts it from 0.52 to
  0.60 by feeding a tighter context, but a larger model or stricter
  system prompt would push it further.
- Latency is dominated by the local 3B LLM on CPU. Rerank actually
  reduces end-to-end latency here: a cross-encoder over 20 candidates
  costs ~200 ms, but the trimmed top-5 means the LLM ingests fewer
  tokens, saving ~20 s per answer.
- Retrieval itself is sub-second; the wall-clock numbers are the LLM.

Reproduce:

```bash
make eval                               # base
RERANK_ENABLED=true make eval           # cross-encoder rerank
```

---

## Development

```bash
pip install -e ".[dev]"
ruff check .
mypy app
pytest --cov=app
```

Tests don't need Postgres or Ollama — `tests/test_chunker.py` is pure
Python and `tests/test_api.py` injects a stub LLM and a fake search
function via FastAPI dependency overrides.

See [`CONTRIBUTING.md`](./CONTRIBUTING.md) for commit conventions, the
PR checklist, and the release procedure. The full version history is
in [`CHANGELOG.md`](./CHANGELOG.md). Security reports go via
[`SECURITY.md`](./SECURITY.md), not as public issues.

---

## Production deployment

A self-contained recipe to put rag-docs behind HTTPS on a 4 GB VPS,
with Caddy auto-TLS, basic auth on write endpoints, and resource
limits, lives in [`deploy/`](./deploy/README.md). The whole stack
(api + db + ollama + caddy) fits in ~2 GB RAM at rest with the
`llama3.2:1b` model.

---

## License

MIT — see [LICENSE](./LICENSE).
