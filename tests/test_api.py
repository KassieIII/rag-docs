"""End-to-end test for /ask using a SQLite-friendly in-memory path is
not possible because pgvector is Postgres-only. Instead we mock the
``search`` dependency and the LLM, exercising the wiring of the API
without standing up a database.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.deps import get_session
from app.generate.llm import StubLLMClient
from app.main import app, get_llm
from app.retrieve.search import Hit


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    stub_llm = StubLLMClient(answer="The CLI flag is --reload [chunk:7].")

    async def fake_session():
        yield None

    async def fake_search(_session, query: str, *, top_k: int = 5, min_score: float = 0.0):
        return [
            Hit(
                chunk_id=7,
                document_id=1,
                source="https://fastapi.tiangolo.com/",
                heading="Development - reload",
                text="Use --reload to auto-reload during development.",
                score=0.81,
            )
        ]

    app.dependency_overrides[get_session] = fake_session
    app.dependency_overrides[get_llm] = lambda: stub_llm
    # main.py imports `search` by name, so we patch it on main, not on the
    # source module.
    import app.main as main_module

    monkeypatch.setattr(main_module, "search", fake_search)

    with TestClient(app) as c:
        yield c

    app.dependency_overrides.clear()


def test_ask_returns_answer_and_citations(client: TestClient) -> None:
    resp = client.post("/ask", json={"question": "How do I reload?"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["answer"].startswith("The CLI flag is --reload")
    assert len(body["citations"]) == 1
    cite = body["citations"][0]
    assert cite["chunk_id"] == 7
    assert cite["score"] == pytest.approx(0.81, abs=1e-3)


def test_ask_validates_question(client: TestClient) -> None:
    resp = client.post("/ask", json={"question": ""})
    assert resp.status_code == 422


def test_ask_top_k_bounds(client: TestClient) -> None:
    resp = client.post("/ask", json={"question": "x", "top_k": 999})
    assert resp.status_code == 422


def test_ask_stream_emits_citations_then_tokens_then_done(client: TestClient) -> None:
    import json
    import re

    with client.stream("POST", "/ask/stream", json={"question": "How do I reload?"}) as resp:
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/event-stream")
        body = "".join(resp.iter_text())

    citations_at = body.find("event: citations")
    token_at = body.find("event: token")
    done_at = body.find("event: done")
    assert 0 <= citations_at < token_at < done_at, body

    # Concatenate every streamed token payload — should reproduce the
    # canned stub answer verbatim.
    tokens = [
        json.loads(payload)["text"]
        for payload in re.findall(r"event: token\ndata: (\{.*?\})\n", body)
    ]
    assert "".join(tokens) == "The CLI flag is --reload [chunk:7]."


def test_metrics_endpoint_exposes_prometheus_text(client: TestClient) -> None:
    # Drive at least one /ask so the counter has a sample.
    client.post("/ask", json={"question": "x"})

    resp = client.get("/metrics")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/plain")
    body = resp.text
    assert "rag_ask_requests_total" in body
    assert "rag_ask_latency_seconds" in body
    assert "rag_retrieve_latency_seconds" in body
