import pytest
from unittest.mock import MagicMock, patch
from config import Config


@pytest.fixture
def config():
    return Config()


@patch("rag_system.DocumentProcessor")
@patch("rag_system.VectorStore")
@patch("rag_system.AIGenerator")
@patch("rag_system.SessionManager")
def test_query_returns_response_and_sources(mock_sm, mock_ai, mock_vs, mock_dp, config):
    """query() should return the AI response text and collected sources."""
    from rag_system import RAGSystem

    mock_ai.return_value.generate_response.return_value = "MCP is Model Context Protocol"

    system = RAGSystem(config)
    system.tool_manager = MagicMock()
    system.tool_manager.get_tool_definitions.return_value = []
    system.tool_manager.get_last_sources.return_value = [
        {"label": "MCP Course - Lesson 1", "url": "http://example.com"}
    ]

    response, sources = system.query("what is MCP")

    assert response == "MCP is Model Context Protocol"
    assert sources == [{"label": "MCP Course - Lesson 1", "url": "http://example.com"}]
    system.tool_manager.reset_sources.assert_called_once()


@patch("rag_system.DocumentProcessor")
@patch("rag_system.VectorStore")
@patch("rag_system.AIGenerator")
@patch("rag_system.SessionManager")
def test_query_with_session_updates_history(mock_sm, mock_ai, mock_vs, mock_dp, config):
    """query() with a session_id should add the exchange to session history."""
    from rag_system import RAGSystem

    mock_ai.return_value.generate_response.return_value = "answer"
    mock_sm.return_value.get_conversation_history.return_value = None

    system = RAGSystem(config)
    system.tool_manager = MagicMock()
    system.tool_manager.get_last_sources.return_value = []

    system.query("what is MCP", session_id="session_1")

    mock_sm.return_value.add_exchange.assert_called_once_with(
        "session_1", "what is MCP", "answer"
    )


def test_config_max_results_is_nonzero(config):
    """
    REVEALS BUG: MAX_RESULTS=0 makes every ChromaDB query fail.
    This test will FAIL against the current system.
    """
    assert config.MAX_RESULTS > 0, (
        f"config.MAX_RESULTS={config.MAX_RESULTS} — must be a positive integer. "
        "ChromaDB raises ValueError('Number of requested results 0 cannot be negative or zero') "
        "on every search, causing all content queries to fail."
    )


@patch("rag_system.DocumentProcessor")
@patch("rag_system.VectorStore")
@patch("rag_system.AIGenerator")
@patch("rag_system.SessionManager")
def test_tool_manager_receives_tools_from_both_registered_tools(mock_sm, mock_ai, mock_vs, mock_dp, config):
    """Both search and outline tools must be registered."""
    from rag_system import RAGSystem

    system = RAGSystem(config)
    tool_names = {name for name in system.tool_manager.tools}
    assert "search_course_content" in tool_names
    assert "get_course_outline" in tool_names
