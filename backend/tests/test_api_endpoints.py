"""
API endpoint tests for the RAG chatbot FastAPI application.

Uses the `api_client` fixture from conftest.py, which spins up a minimal
FastAPI app mirroring the production endpoints with a mocked RAGSystem.
This avoids ChromaDB connections and static-file mount issues at import time.
"""
import pytest


# ---------------------------------------------------------------------------
# POST /api/query
# ---------------------------------------------------------------------------

def test_query_returns_answer_and_sources(api_client, mock_rag_system):
    """Successful query returns the AI answer, sources list, and session_id."""
    response = api_client.post(
        "/api/query",
        json={"query": "What is MCP?", "session_id": "existing-session"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["answer"] == "This is a test answer."
    assert data["session_id"] == "existing-session"
    assert isinstance(data["sources"], list)
    assert data["sources"][0]["label"] == "Test Course - Lesson 1"
    assert data["sources"][0]["url"] == "http://example.com/lesson1"


def test_query_creates_session_when_none_provided(api_client, mock_rag_system):
    """When no session_id is sent, create_session is called and the new ID returned."""
    response = api_client.post("/api/query", json={"query": "Tell me about agents"})

    assert response.status_code == 200
    data = response.json()
    assert data["session_id"] == "generated-session-id"
    mock_rag_system.session_manager.create_session.assert_called_once()


def test_query_forwards_query_and_session_to_rag(api_client, mock_rag_system):
    """The query text and session_id are passed through to rag_system.query."""
    api_client.post(
        "/api/query",
        json={"query": "Explain transformers", "session_id": "sess-42"},
    )

    mock_rag_system.query.assert_called_once_with("Explain transformers", "sess-42")


def test_query_returns_500_when_rag_raises(api_client, mock_rag_system):
    """An exception inside the RAG system is surfaced as HTTP 500."""
    mock_rag_system.query.side_effect = RuntimeError("ChromaDB unavailable")

    response = api_client.post(
        "/api/query",
        json={"query": "broken query", "session_id": "sess-1"},
    )

    assert response.status_code == 500
    assert "ChromaDB unavailable" in response.json()["detail"]


def test_query_missing_required_field_returns_422(api_client):
    """Omitting the required `query` field triggers Pydantic validation (HTTP 422)."""
    response = api_client.post("/api/query", json={"session_id": "sess-1"})

    assert response.status_code == 422


def test_query_empty_sources_list_is_valid(api_client, mock_rag_system):
    """A query that matches no course content returns an empty sources list."""
    mock_rag_system.query.return_value = ("General answer.", [])

    response = api_client.post(
        "/api/query",
        json={"query": "What is Python?", "session_id": "sess-gen"},
    )

    assert response.status_code == 200
    assert response.json()["sources"] == []


# ---------------------------------------------------------------------------
# GET /api/courses
# ---------------------------------------------------------------------------

def test_courses_returns_total_and_titles(api_client, mock_rag_system):
    """GET /api/courses returns total_courses count and a list of course titles."""
    response = api_client.get("/api/courses")

    assert response.status_code == 200
    data = response.json()
    assert data["total_courses"] == 2
    assert "Course A" in data["course_titles"]
    assert "Course B" in data["course_titles"]


def test_courses_count_matches_titles_length(api_client, mock_rag_system):
    """total_courses should equal the length of course_titles."""
    response = api_client.get("/api/courses")

    data = response.json()
    assert data["total_courses"] == len(data["course_titles"])


def test_courses_returns_500_when_analytics_raises(api_client, mock_rag_system):
    """An exception from get_course_analytics is surfaced as HTTP 500."""
    mock_rag_system.get_course_analytics.side_effect = RuntimeError("DB error")

    response = api_client.get("/api/courses")

    assert response.status_code == 500
    assert "DB error" in response.json()["detail"]
