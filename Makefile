.PHONY: help up down logs ingest ask eval test lint typecheck format migrate model-pull

PY ?= python
URL ?= https://raw.githubusercontent.com/tiangolo/fastapi/master/docs/en/docs/tutorial/first-steps.md
QUESTION ?= What is FastAPI?
MODEL ?= llama3.2:3b

help:
	@echo "rag-docs targets:"
	@echo "  up           docker compose up -d (db + ollama + api)"
	@echo "  down         docker compose down"
	@echo "  logs         tail api logs"
	@echo "  migrate      alembic upgrade head"
	@echo "  model-pull   ollama pull \$$MODEL (default: $(MODEL))"
	@echo "  ingest URL=  POST /ingest with the given URL"
	@echo "  ask          POST /ask with QUESTION=..."
	@echo "  eval         python eval/run_eval.py"
	@echo "  test         pytest"
	@echo "  lint         ruff check ."
	@echo "  format       ruff format ."
	@echo "  typecheck    mypy app"

up:
	docker compose up -d --build

down:
	docker compose down

logs:
	docker compose logs -f api

migrate:
	docker compose exec api alembic upgrade head

model-pull:
	docker compose exec ollama ollama pull $(MODEL)

ingest:
	curl -fsS -X POST http://localhost:8000/ingest \
	  -H 'Content-Type: application/json' \
	  -d '{"url":"$(URL)"}' | $(PY) -m json.tool

ask:
	curl -fsS -X POST http://localhost:8000/ask \
	  -H 'Content-Type: application/json' \
	  -d '{"question":"$(QUESTION)","top_k":5}' | $(PY) -m json.tool

eval:
	$(PY) eval/run_eval.py --base-url http://localhost:8000

test:
	pytest

lint:
	ruff check .

format:
	ruff format .

typecheck:
	mypy app
