# Contributing

Thanks for taking the time to look at this repo.

## Local setup

```bash
git clone https://github.com/KassieIII/rag-docs.git
cd rag-docs

# create the schema + start db, ollama, api
cp .env.example .env
docker compose up -d --build
docker compose exec ollama ollama pull llama3.2:3b

# Python tooling for tests / lint outside Docker
pip install -e ".[dev]"
```

## Tests and lint

Tests stub out Postgres and Ollama via FastAPI dependency overrides, so
they run without any infrastructure:

```bash
pytest --cov=app          # 10 tests, ~2 s
ruff check .              # lint, must be clean
mypy app                  # optional, no errors expected
```

CI runs the same three commands plus a Docker image build on every push
and pull request. PRs that don't pass CI will not be merged.

## Commits

Use [Conventional Commits](https://www.conventionalcommits.org/):

- `feat:` user-visible new behavior
- `fix:` bug fixes
- `docs:` README, ARCHITECTURE, CHANGELOG only
- `test:`, `refactor:`, `chore:`, `style:`, `perf:`
- scope is optional but appreciated, e.g. `feat(eval): ...`

## Pull requests

1. One focused change per PR. If you find an unrelated bug, open a
   second PR.
2. Keep the diff small. Refactors that touch many files should be
   squashed into one "no behavior change" commit.
3. Update `CHANGELOG.md` under `## [Unreleased]` for any user-visible
   change.
4. If the PR changes retrieval, embeddings, prompts or chunking, run
   `make eval` and paste the metrics into the PR description.

## Releasing (maintainers)

1. Move entries under `## [Unreleased]` to a new `## [x.y.z] - YYYY-MM-DD`
   section, update the comparison links at the bottom.
2. Bump `version` in `pyproject.toml`.
3. `git tag -a vX.Y.Z -m "vX.Y.Z" && git push --tags`.
4. `gh release create vX.Y.Z --generate-notes` (then edit the body).
