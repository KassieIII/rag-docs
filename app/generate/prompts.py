"""Prompts.

The system prompt forces the model to (a) only answer from provided
context and (b) cite chunks by their ``[chunk:<id>]`` tag. The /ask
endpoint then parses those tags back out for the response.
"""

from __future__ import annotations

from app.retrieve.search import Hit

SYSTEM_PROMPT = """\
You are a documentation assistant. Answer the user's question using ONLY
the context passages below. Each passage has an id like [chunk:42].

Rules:
1. Cite every factual claim with its [chunk:<id>] tag.
2. If the context does not contain the answer, reply exactly:
   "I don't know based on the provided documentation."
3. Be concise. Prefer two sentences over five.
4. Do not invent URLs, function names, or version numbers.
"""


def render_user_prompt(question: str, hits: list[Hit]) -> str:
    blocks = [_render_hit(h) for h in hits]
    context = "\n\n".join(blocks) if blocks else "(no context)"
    return f"Context:\n{context}\n\nQuestion: {question}"


def _render_hit(hit: Hit) -> str:
    head = f"[chunk:{hit.chunk_id}]"
    if hit.heading:
        head += f" ({hit.heading})"
    head += f" source={hit.source}"
    return f"{head}\n{hit.text}"
