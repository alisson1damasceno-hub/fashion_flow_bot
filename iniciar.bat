@echo off
start "" "http://localhost:8000"
python -m uvicorn app:app --host 0.0.0.0 --port 8000
