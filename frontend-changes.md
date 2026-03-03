# Frontend Changes

No frontend changes were made in this session.

This session added backend API testing infrastructure:
- `backend/tests/conftest.py` — shared fixtures (`mock_rag_system`, `api_client`)
- `backend/tests/test_api_endpoints.py` — API endpoint tests for `/api/query` and `/api/courses`
- `pyproject.toml` — added `[tool.pytest.ini_options]` and `httpx` dependency
