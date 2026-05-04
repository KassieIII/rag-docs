"""Prometheus metrics for rag-docs.

Exposed at ``GET /metrics`` in the standard Prometheus text format.
We deliberately keep the metric set small — observability is about
asking the *right* questions, not collecting every possible number.
"""

from __future__ import annotations

from prometheus_client import (
    CONTENT_TYPE_LATEST,
    CollectorRegistry,
    Counter,
    Histogram,
    generate_latest,
    multiprocess,
)

# Single registry for the process. We avoid the default global registry so
# tests can swap in a clean one and so we don't leak metrics from other libs.
REGISTRY = CollectorRegistry()


# --- Request counters ---------------------------------------------------

ASK_REQUESTS = Counter(
    "rag_ask_requests_total",
    "Total /ask requests, labelled by HTTP status and whether rerank was used.",
    labelnames=("status", "rerank"),
    registry=REGISTRY,
)

INGEST_REQUESTS = Counter(
    "rag_ingest_requests_total",
    "Total /ingest requests, labelled by HTTP status.",
    labelnames=("status",),
    registry=REGISTRY,
)

# --- Latency histograms (seconds) ---------------------------------------
# Buckets chosen for a CPU-bound local RAG: retrieval is sub-second, the
# LLM is the long tail (small models on CPU can easily take 10 s+).

_LATENCY_BUCKETS = (0.05, 0.1, 0.25, 0.5, 1, 2, 5, 10, 30, 60, 120)

ASK_LATENCY = Histogram(
    "rag_ask_latency_seconds",
    "End-to-end /ask latency.",
    buckets=_LATENCY_BUCKETS,
    registry=REGISTRY,
)

RETRIEVE_LATENCY = Histogram(
    "rag_retrieve_latency_seconds",
    "Time spent in retrieval (excluding rerank), labelled by mode.",
    labelnames=("mode",),
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2, 5),
    registry=REGISTRY,
)

RERANK_LATENCY = Histogram(
    "rag_rerank_latency_seconds",
    "Time spent in cross-encoder rerank, when enabled.",
    buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1, 2),
    registry=REGISTRY,
)

LLM_LATENCY = Histogram(
    "rag_llm_latency_seconds",
    "Time spent waiting for the LLM (Ollama) to produce an answer.",
    buckets=_LATENCY_BUCKETS,
    registry=REGISTRY,
)

# --- Quality counters ---------------------------------------------------

ASK_NO_HITS = Counter(
    "rag_ask_no_hits_total",
    "Total /ask requests that returned 'I don't know' because retrieval was empty.",
    registry=REGISTRY,
)


def render() -> tuple[bytes, str]:
    """Return the Prometheus exposition payload and content-type header.

    Supports multi-process gunicorn workers if ``PROMETHEUS_MULTIPROC_DIR``
    is set; otherwise falls back to the single-process registry.
    """
    import os

    if os.environ.get("PROMETHEUS_MULTIPROC_DIR"):
        registry = CollectorRegistry()
        multiprocess.MultiProcessCollector(registry)
        return generate_latest(registry), CONTENT_TYPE_LATEST
    return generate_latest(REGISTRY), CONTENT_TYPE_LATEST
