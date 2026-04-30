<!-- Thanks for the PR. Keep the diff focused and CI green. -->

## Summary

<!-- One paragraph: what this PR changes from a user's perspective. -->

## Why

<!-- Link the issue or describe the motivation. -->

Closes #

## Changes

<!-- Bullet list of the substantive changes. Skip noise. -->

-
-

## Eval impact

<!-- If this PR touches retrieval / prompts / chunking / embeddings,
     paste before/after metrics here. Otherwise write "n/a". -->

| metric            |  before  |  after  |
|-------------------|:--------:|:-------:|
| recall@5          |          |         |
| citation accuracy |          |         |
| keyword coverage  |          |         |
| latency p50       |          |         |

## Checklist

- [ ] `ruff check .` is clean
- [ ] `pytest --cov=app` passes locally
- [ ] `CHANGELOG.md` updated under `## [Unreleased]` if user-visible
- [ ] No secrets, large blobs, or unrelated reformatting in the diff
