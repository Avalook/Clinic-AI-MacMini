.PHONY: install test lint format run docker-up docker-down clean

install:
	poetry install

test:
	poetry run pytest src/tests/ -v --cov=src/clinicai --cov-report=term-missing

lint:
	poetry run ruff check src/

format:
	poetry run ruff format src/

run:
	poetry run uvicorn clinicai.main:app --reload --host 0.0.0.0 --port 8000

docker-up:
	docker-compose up -d

docker-down:
	docker-compose down

clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
