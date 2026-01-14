@echo off
call .venv\Scripts\activate.bat
start uvicorn src.api.api_search:app --port 8000 --reload
start uvicorn src.api.api_cat:app --port 8001 --reload
start uvicorn src.api.api_cv:app --port 8002 --reload
start uvicorn src.api.api_gal:app --port 8003 --reload
start uvicorn src.api.api_load:app --port 8004 --reload
exit