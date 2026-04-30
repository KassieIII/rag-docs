"""Ingest the FastAPI docs corpus via the running API service.

Reads URLs from eval/corpus_urls.txt, posts each to /ingest, prints summary.
"""
from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

API_URL = "http://localhost:8000/ingest"
CORPUS_FILE = Path(__file__).with_name("corpus_urls.txt")


def post_ingest(url: str, timeout: float = 300.0) -> tuple[int, dict]:
    body = json.dumps({"url": url}).encode("utf-8")
    req = urllib.request.Request(
        API_URL,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")


def main() -> int:
    urls = [
        line.strip()
        for line in CORPUS_FILE.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    ]
    total = len(urls)
    ok = 0
    failed = 0
    t0 = time.perf_counter()
    for i, u in enumerate(urls, 1):
        print(f"[{i}/{total}] {u}", flush=True)
        try:
            status, body = post_ingest(u)
        except Exception as exc:
            print(f"  EXCEPTION: {exc}")
            failed += 1
            continue
        if status == 200:
            print(
                f"  -> doc={body.get('document_id')} chunks={body.get('chunk_count')} "
                f"replaced={body.get('replaced')}"
            )
            ok += 1
        else:
            print(f"  HTTP {status}: {body}")
            failed += 1
    dt = time.perf_counter() - t0
    print(f"\nDone in {dt:.1f}s | ok={ok} failed={failed} total={total}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
