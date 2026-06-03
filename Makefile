# ==============================================================================
# STORE INTELLIGENCE SYSTEM BUILD ENGINE - MAKEFILE
# Enforces automated local environments setup, testing, linting, and dockers.
# ==============================================================================

.PHONY: setup run run-dashboard seed stream-mock test lint format docker-up docker-down clean help

# Default target when running 'make'
help:
	@echo "========================================================================"
	@echo "                     🔮 ORACLE BUILD ENGINE SYSTEM                      "
	@echo "========================================================================"
	@echo "make setup          - Build virtual environment & install requirements"
	@echo "make seed           - Initialize schemas and seed database with mock data"
	@echo "make run            - Launch local FastAPI Uvicorn developer server"
	@echo "make run-dashboard  - Launch local Streamlit analytics dashboard"
	@echo "make stream-mock    - Start pipeline CCTV edge ingestion simulator"
	@echo "make test           - Run Pytest test suites (unit + integrations)"
	@echo "make lint           - Evaluate styling lints (Ruff/Black)"
	@echo "make format         - Standardize file formatting layouts"
	@echo "make docker-up      - Compile and boot full compose cluster"
	@echo "make docker-down    - Terminate active docker composed networks"
	@echo "make clean          - Sweep off cache artifacts and temporary dumps"
	@echo "========================================================================"

# Setup local Python developer environment
setup:
	@echo "Creating localized virtual directory (.venv)..."
	python -m venv .venv
	@echo "Upgrading package installer (pip) and locked modules..."
	.venv/Scripts/pip install --upgrade pip
	.venv/Scripts/pip install -r requirements.txt
	@echo "Creating local caching directories..."
	mkdir -p data/videos data/events logs
	@echo "Setup completed successfully. Run 'source .venv/Scripts/activate' on Windows Powershell."

# Run Seed Data
seed:
	@echo "Seeding database with premium mock stores and visitor sessions..."
	python scripts/init_db.py

# Run FastAPI Local REST & WebSockets Server
run:
	@echo "Launching FastAPI Uvicorn engine..."
	uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Run Streamlit Analytics Dashboard Panel
run-dashboard:
	@echo "Launching Streamlit UI portal..."
	streamlit run dashboard/app.py --server.port 8501

# Stream Mock CCTV Stream Events
stream-mock:
	@echo "Streaming continuous edge vision logs to API..."
	python scripts/mock_stream.py

# Run test suites
test:
	@echo "Executing Pytest integration checks..."
	pytest -v --tb=short

# Style evaluations
lint:
	@echo "Evaluating syntax layouts using Ruff rules..."
	ruff check .

# Formatting standardizations
format:
	@echo "Formatting scripts using Black..."
	black .
	@echo "Re-ordering import matrices..."
	ruff check --select I --fix .

# Docker Orchestrations
docker-up:
	@echo "Building docker layers and spawning compose cluster..."
	docker compose up --build -d
	@echo "Services active: API (Port 8000), Postgres (Port 5432), Dashboard (Port 8501)"

docker-down:
	@echo "Tearing down container layers..."
	docker compose down -v

# Cleanup
clean:
	@echo "Sweeping compile caches..."
	rm -rf .pytest_cache
	rm -rf .ruff_cache
	find . -type d -name "__pycache__" -exec rm -r {} +
	rm -f store_intelligence.db
	@echo "System cleaned."
