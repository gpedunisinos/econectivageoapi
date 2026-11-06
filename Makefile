.PHONY: install lint migrate migration test run

install:
	python -m pip install -e '.[dev]'

lint:
	ruff check .

migrate:
	alembic upgrade head

migration:
	alembic revision -m "$(message)"

test:
	pytest --cov=app

run:
	uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
