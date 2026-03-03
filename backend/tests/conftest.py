import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from unittest.mock import MagicMock
from typing import List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from pydantic import BaseModel


@pytest.fixture
def mock_rag_system():
    """Shared mock for RAGSystem with sensible defaults."""
    mock = MagicMock()
    mock.query.return_value = (
        "This is a test answer.",
        [{"label": "Test Course - Lesson 1", "url": "http://example.com/lesson1"}],
    )
    mock.get_course_analytics.return_value = {
        "total_courses": 2,
        "course_titles": ["Course A", "Course B"],
    }
    mock.session_manager.create_session.return_value = "generated-session-id"
    return mock


@pytest.fixture
def api_client(mock_rag_system):
    """
    TestClient wrapping a minimal FastAPI app that mirrors the production
    endpoints but uses a mocked RAGSystem to avoid ChromaDB and static-file
    dependencies at import time.
    """

    class QueryRequest(BaseModel):
        query: str
        session_id: Optional[str] = None

    class SourceItem(BaseModel):
        label: str
        url: Optional[str] = None

    class QueryResponse(BaseModel):
        answer: str
        sources: List[SourceItem]
        session_id: str

    class CourseStats(BaseModel):
        total_courses: int
        course_titles: List[str]

    test_app = FastAPI()

    @test_app.post("/api/query", response_model=QueryResponse)
    async def query_documents(request: QueryRequest):
        try:
            session_id = request.session_id
            if not session_id:
                session_id = mock_rag_system.session_manager.create_session()
            answer, sources = mock_rag_system.query(request.query, session_id)
            return QueryResponse(answer=answer, sources=sources, session_id=session_id)
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    @test_app.get("/api/courses", response_model=CourseStats)
    async def get_course_stats():
        try:
            analytics = mock_rag_system.get_course_analytics()
            return CourseStats(
                total_courses=analytics["total_courses"],
                course_titles=analytics["course_titles"],
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))

    return TestClient(test_app)
