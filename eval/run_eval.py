"""Run the golden dataset against a live rag-docs instance and emit metrics.

Metrics computed:
    * recall@k         — fraction of questions where at least one retrieved
                         chunk's source contains ``must_cite_source_contains``.
    * citation_acc     — fraction of answers whose ``[chunk:<id>]`` tags all
                         appear in the returned citation list.
    * keyword_coverage — fraction of expected keywords present in the answer.
    * latency_p50/p95  — wall-clock time per /ask call.

Run:
    python eval/run_eval.py --base-url http://localhost:8000 --top-k 5
"""

from __future__ import annotations

import argparse
import json
import re
import statistics
import sys
import time
from dataclasses import dataclass
from pathlib import Path

import httpx

GOLDEN_PATH = Path(__file__).parent / "golden.jsonl"
CITE_RE = re.compile(r"\[chunk:(\d+)\]")


@dataclass(slots=True)
class Case:
    question: str
    expected_keywords: list[str]
    must_cite_source_contains: str


def load_golden(path: Path = GOLDEN_PATH) -> list[Case]:
    cases: list[Case] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        obj = json.loads(line)
        cases.append(
            Case(
                question=obj["question"],
                expected_keywords=[k.lower() for k in obj["expected_keywords"]],
                must_cite_source_contains=obj["must_cite_source_contains"].lower(),
            )
        )
    return cases


def evaluate(base_url: str, top_k: int) -> dict[str, float]:
    cases = load_golden()
    recall_hits = 0
    citation_ok = 0
    keyword_scores: list[float] = []
    latencies: list[float] = []

    with httpx.Client(timeout=120.0) as client:
        for case in cases:
            t0 = time.perf_counter()
            resp = client.post(
                f"{base_url}/ask",
                json={"question": case.question, "top_k": top_k},
            )
            latencies.append(time.perf_counter() - t0)
            resp.raise_for_status()
            body = resp.json()

            sources = [c["source"].lower() for c in body["citations"]]
            if any(case.must_cite_source_contains in s for s in sources):
                recall_hits += 1

            cited_ids = {int(m) for m in CITE_RE.findall(body["answer"])}
            returned_ids = {c["chunk_id"] for c in body["citations"]}
            if cited_ids and cited_ids.issubset(returned_ids):
                citation_ok += 1
            elif not cited_ids and "i don't know" in body["answer"].lower():
                citation_ok += 1

            ans_lower = body["answer"].lower()
            present = sum(1 for kw in case.expected_keywords if kw in ans_lower)
            keyword_scores.append(present / max(len(case.expected_keywords), 1))

    n = len(cases)
    return {
        f"recall@{top_k}": recall_hits / n,
        "citation_acc": citation_ok / n,
        "keyword_coverage": statistics.mean(keyword_scores),
        "latency_p50_ms": statistics.median(latencies) * 1000,
        "latency_p95_ms": _percentile(latencies, 0.95) * 1000,
        "n": float(n),
    }


def _percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    sorted_vals = sorted(values)
    k = max(int(round(p * (len(sorted_vals) - 1))), 0)
    return sorted_vals[k]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--top-k", type=int, default=5)
    args = parser.parse_args(argv)

    metrics = evaluate(args.base_url, args.top_k)
    width = max(len(k) for k in metrics)
    for key, value in metrics.items():
        print(f"{key:<{width}}  {value:.4f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
