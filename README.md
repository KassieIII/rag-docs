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

Ingested: FastAPI documentation pages (16 documents, 4 042 chunks).
Hardware: laptop CPU, no GPU. Embedder: `bge-small-en-v1.5` (384-dim).
LLM: `llama3.2:3b` via Ollama. Eval set: 25 hand-written Q&A pairs in
[`eval/golden.json`](eval/golden.json), see raw output in
[`eval/results_baseline.txt`](eval/results_baseline.txt).

| metric            |  base   | + rerank |
|-------------------|:-------:|:--------:|
| recall@5          |  1.00   | _pending_ |
| citation accuracy |  0.52   | _pending_ |
| keyword coverage  |  0.64   | _pending_ |
| latency p50       | 141.7 s | _pending_ |
| latency p95       | 203.7 s | _pending_ |

Notes on the honest read:

- `recall@5 = 1.00` is high because the corpus is small and topical;
  on a wider corpus we expect this to drop into the 0.7–0.9 range.
- `citation_acc = 0.52` is the weak spot: `llama3.2:3b` frequently
  paraphrases without emitting `[chunk:N]` markers. A larger model or a
  stricter system prompt would lift this.
- Latency is dominated by the local 3B LLM on CPU (~140–200 s per
  answer). Retrieval itself is sub-second.

Reproduce:

```bash
make eval                               # base
RERANK_ENABLED=true make eval           # cross-encoder rerank
```

The rerank column will be filled in by a follow-up commit once the
second eval run finishes (it shares the same hardware budget).

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
