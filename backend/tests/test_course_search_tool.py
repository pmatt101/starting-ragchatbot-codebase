import pytest
from unittest.mock import MagicMock
from search_tools import CourseSearchTool
from vector_store import SearchResults


@pytest.fixture
def mock_store():
    return MagicMock()


@pytest.fixture
def tool(mock_store):
    return CourseSearchTool(mock_store)


def test_execute_returns_formatted_content_on_success(tool, mock_store):
    """Normal search returns content with course/lesson headers."""
    mock_store.search.return_value = SearchResults(
        documents=["MCP stands for Model Context Protocol"],
        metadata=[{"course_title": "MCP Course", "lesson_number": 1}],
        distances=[0.4],
    )
    mock_store.get_lesson_link.return_value = "http://example.com/lesson1"

    result = tool.execute(query="what is MCP")

    assert "MCP Course" in result
    assert "MCP stands for Model Context Protocol" in result
    mock_store.search.assert_called_once_with(
        query="what is MCP", course_name=None, lesson_number=None
    )


def test_execute_with_course_name_filter(tool, mock_store):
    """course_name and lesson_number are forwarded to the store."""
    mock_store.search.return_value = SearchResults(
        documents=["Content"], metadata=[{"course_title": "MCP Course", "lesson_number": 2}], distances=[0.3]
    )
    mock_store.get_lesson_link.return_value = None

    tool.execute(query="agents", course_name="MCP", lesson_number=2)

    mock_store.search.assert_called_once_with(
        query="agents", course_name="MCP", lesson_number=2
    )


def test_execute_returns_error_string_when_store_returns_error(tool, mock_store):
    """When VectorStore returns an error (e.g., n_results=0), the error is returned."""
    mock_store.search.return_value = SearchResults(
        documents=[], metadata=[], distances=[],
        error="Number of requested results 0 cannot be negative or zero"
    )

    result = tool.execute(query="what is MCP")

    # The error string should be returned directly — Claude receives it as tool output
    assert "0" in result or "negative" in result or "zero" in result


def test_execute_returns_no_content_message_when_empty(tool, mock_store):
    """Empty (but error-free) results produce a human-readable no-content message."""
    mock_store.search.return_value = SearchResults(
        documents=[], metadata=[], distances=[]
    )

    result = tool.execute(query="some topic")

    assert "No relevant content found" in result


def test_config_max_results_is_positive():
    """
    REVEALS BUG: MAX_RESULTS=0 causes ChromaDB to raise ValueError.
    This test will FAIL against the current config, proving the root cause.
    """
    from config import Config
    config = Config()
    assert config.MAX_RESULTS > 0, (
        f"MAX_RESULTS={config.MAX_RESULTS} — ChromaDB requires n_results > 0; "
        "every content search is currently raising ValueError internally"
    )


def test_sources_tracked_after_successful_search(tool, mock_store):
    """last_sources is populated after a successful search."""
    mock_store.search.return_value = SearchResults(
        documents=["content"],
        metadata=[{"course_title": "MCP Course", "lesson_number": 3}],
        distances=[0.2],
    )
    mock_store.get_lesson_link.return_value = "http://example.com/l3"

    tool.execute(query="topic")

    assert len(tool.last_sources) == 1
    assert tool.last_sources[0]["label"] == "MCP Course - Lesson 3"
    assert tool.last_sources[0]["url"] == "http://example.com/l3"
