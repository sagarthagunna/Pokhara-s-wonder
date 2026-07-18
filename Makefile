# -------------------------
# Pokhara's Wonder Makefile
# -------------------------

PYTHON = python
PIP = pip
BACKEND = backend

.PHONY: help install backend frontend run clean docker-build docker-up docker-down lint

help:
	@echo "Available commands:"
	@echo "  make install        Install backend dependencies"
	@echo "  make backend        Run FastAPI backend"
	@echo "  make frontend       Open frontend instructions"
	@echo "  make run            Run backend"
	@echo "  make clean          Remove Python cache"
	@echo "  make docker-build   Build Docker containers"
	@echo "  make docker-up      Start Docker containers"
	@echo "  make docker-down    Stop Docker containers"

install:
	cd $(BACKEND) && $(PIP) install -r requirements.txt

backend:
	cd $(BACKEND) && uvicorn app.main:app --reload

frontend:
	@echo "Open frontend/index.html in your browser"
	@echo "Or use VS Code Live Server."

run: backend

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

docker-build:
	docker compose build

docker-up:
	docker compose up

docker-down:
	docker compose down

lint:
	cd $(BACKEND) && python -m py_compile app/main.py