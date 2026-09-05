.PHONY: dev api web build test check

api:            ## backend on :8000
	cd backend && uvicorn app.main:app --reload --port 8000

web:            ## frontend dev server on :5173 (proxies /api to :8000)
	cd frontend && npm run dev

build:          ## production frontend build (served by the API from /)
	cd frontend && npm run build

test:           ## backend tests
	cd backend && python -m pytest

check:          ## lint + format + tests
	cd backend && ruff check . && ruff format --check . && python -m pytest

docker:         ## build and run the single-container app on :8000
	docker build -t paddock-planner . && docker run --rm -p 8000:8000 paddock-planner
