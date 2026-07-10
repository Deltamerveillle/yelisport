.PHONY: bootstrap up down build logs test lint format

bootstrap:
	./scripts/bootstrap.sh

up:
	docker compose up -d

down:
	docker compose down

build:
	docker compose build

logs:
	docker compose logs -f

test:
	./scripts/test.sh

lint:
	./scripts/lint.sh

format:
	docker compose run --rm api ruff format .
	docker compose run --rm ai ruff format .
