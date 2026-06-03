#!/bin/bash

# Enforce clean SQLite schema startup and seed default retail records
python scripts/init_db.py

# Run FastAPI backend in the background on port 8000
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 &

# Run Streamlit dashboard in the foreground on Hugging Face's port 7860
streamlit run dashboard/app.py --server.port 7860 --server.address 0.0.0.0
