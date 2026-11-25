web: cd backend && python -m app.init_db --admin && python scripts/index_knowledge.py && exec uvicorn app.main:app --host 0.0.0.0 --port $PORT --workers 2
