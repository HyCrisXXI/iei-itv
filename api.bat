@echo off
call .venv\Scripts\activate.bat
uvicorn src.api.main:app --reload
pause
