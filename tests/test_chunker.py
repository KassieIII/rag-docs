"""Tests for the markdown chunker.

These exercise the boundary cases that historically broke naive splitters:
empty input, single line, content before first heading, very long sections.
"""

from __future__ import annotations

import pytest

from app.ingest.chunker import chunk_markdown


def test_empty_returns_empty_list() -> None:
    assert chunk_markdown("") == []
    assert chunk_markdown("   \n  \n") == []


def test_single_short_line() -> None:
    chunks = chunk_markdown("Hello world.")
    assert len(chunks) == 1
    assert chunks[0].text == "Hello world."
    assert chunks[0].heading is None
    assert chunks[0].ordinal == 0


def test_prelude_before_first_heading_is_kept() -> None:
    text = "Intro paragraph.\n\n# First section\n\nbody"
    chunks = chunk_markdown(text)
    assert [c.heading for c in chunks] == [None, "First section"]
    assert chunks[0].text == "Intro paragraph."


def test_each_section_keeps_its_heading() -> None:
    text = "# Alpha\nA body\n\n## Beta\nB body\n\n# Gamma\nC body"
    chunks = chunk_markdown(text)
    headings = [c.heading for c in chunks]
    assert headings == ["Alpha", "Beta", "Gamma"]


def test_long_section_is_windowed_with_overlap() -> None:
    body = ("paragraph one. " * 200).strip()
    text = f"# Big\n\n{body}"
    chunks = chunk_markdown(text, chunk_size=400, chunk_overlap=80)
    assert len(chunks) > 1
    assert all(c.heading == "Big" for c in chunks)
    # ordinals are dense
    assert [c.ordinal for c in chunks] == list(range(len(chunks)))
    # overlap actually overlaps
    tail = chunks[0].text[-40:]
    assert tail in chunks[1].text or chunks[1].text.startswith(tail[:20])


def test_overlap_must_be_smaller_than_size() -> None:
    with pytest.raises(ValueError):
        chunk_markdown("abc", chunk_size=100, chunk_overlap=100)


def test_plain_text_without_headings() -> None:
    text = "Just some prose with no markdown markers at all."
    chunks = chunk_markdown(text)
    assert len(chunks) == 1
    assert chunks[0].heading is None
