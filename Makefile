.PHONY: run stop test lint format

run:
	docker compose up -d --build

stop:
	docker compose down -v

test:
	./scripts/test.sh

lint:
	poetry run ruff check .

format:
	poetry run ruff check . --fix && poetry run ruff format .
