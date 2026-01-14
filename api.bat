@echo off
call .venv\Scripts\activate.bat
start uvicorn src.api.main:app --port 8000 --reload
start uvicorn src.api.cat:app --port 8001 --reload
start uvicorn src.api.cv:app --port 8002 --reload
start uvicorn src.api.gal:app --port 8003 --reload
pause
