# rag-docs

Ask-your-docs RAG service. Ingest Markdown / HTML / PDF, retrieve with
**pgvector**, answer with a **local LLM** (Ollama). ~700 LOC of typed
Python, single `docker compose up`, no vendor lock-in, no API keys
required.

[![CI](https://github.com/KassieIII/rag-docs/actions/workflows/ci.yml/badge.svg)](https://github.com/KassieIII/rag-docs/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/python-3.13-3776ab)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688)
![pgvector](https://img.shields.io/badge/pgvector-HNSW-4169e1)
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

Ingested: FastAPI tutorial pages (16 documents, 412 chunks).
Hardware: laptop, no GPU. Model: `llama3.2:3b` via Ollama.

| metric            |  base  | + rerank |
|-------------------|:------:|:--------:|
| recall@5          |  0.71  |  **0.84** |
| citation accuracy |  0.88  |  **0.91** |
| keyword coverage  |  0.62  |  **0.68** |
| latency p50       |  92 ms |   142 ms  |
| latency p95       | 188 ms |   274 ms  |

Reproduce:

```bash
make eval                               # base
RERANK_ENABLED=true make eval           # rerank
```

The numbers are honest baselines, not best-of. Variance run-to-run is
~±2pp on recall.

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

---

## License

MIT — see [LICENSE](./LICENSE).
