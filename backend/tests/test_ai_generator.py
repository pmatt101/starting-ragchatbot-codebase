import pytest
from unittest.mock import MagicMock
from ai_generator import AIGenerator


@pytest.fixture
def generator():
    gen = AIGenerator(api_key="test-key", model="claude-sonnet-4-20250514")
    gen.client = MagicMock()
    return gen


def _make_tool_use_response(tool_name, tool_input, tool_id="toolu_1"):
    block = MagicMock()
    block.type = "tool_use"
    block.name = tool_name
    block.id = tool_id
    block.input = tool_input
    resp = MagicMock()
    resp.stop_reason = "tool_use"
    resp.content = [block]
    return resp


def _make_text_response(text):
    text_block = MagicMock()
    text_block.text = text
    resp = MagicMock()
    resp.stop_reason = "end_turn"
    resp.content = [text_block]
    return resp


def test_tool_use_triggers_two_api_calls(generator):
    """
    When Claude responds with tool_use, a second API call must follow
    with the tool result appended. Two total calls must be made.
    """
    generator.client.messages.create.side_effect = [
        _make_tool_use_response("search_course_content", {"query": "what is MCP"}),
        _make_text_response("MCP is Model Context Protocol"),
    ]
    mock_tm = MagicMock()
    mock_tm.execute_tool.return_value = "Lesson 1 content about MCP..."

    result = generator.generate_response(
        query="what is MCP",
        tools=[{"name": "search_course_content"}],
        tool_manager=mock_tm,
    )

    assert generator.client.messages.create.call_count == 2
    mock_tm.execute_tool.assert_called_once_with(
        "search_course_content", query="what is MCP"
    )
    assert result == "MCP is Model Context Protocol"


def test_no_tool_use_makes_single_api_call(generator):
    """General questions resolve in one API call with no tool execution."""
    generator.client.messages.create.return_value = _make_text_response(
        "Python is a language"
    )
    mock_tm = MagicMock()

    result = generator.generate_response(
        query="what is python",
        tools=[{"name": "search_course_content"}],
        tool_manager=mock_tm,
    )

    assert generator.client.messages.create.call_count == 1
    mock_tm.execute_tool.assert_not_called()
    assert result == "Python is a language"


def test_tool_result_is_included_in_second_call(generator):
    """The tool output must be passed back in the messages of the second API call."""
    generator.client.messages.create.side_effect = [
        _make_tool_use_response("search_course_content", {"query": "agents"}, "toolu_99"),
        _make_text_response("Agents are autonomous AI systems"),
    ]
    mock_tm = MagicMock()
    mock_tm.execute_tool.return_value = "Lesson text about agents"

    generator.generate_response(
        query="tell me about agents",
        tools=[{"name": "search_course_content"}],
        tool_manager=mock_tm,
    )

    second_call_args = generator.client.messages.create.call_args_list[1]
    messages = second_call_args.kwargs.get("messages") or second_call_args.args[0].get("messages", [])
    # The last message should contain the tool result
    tool_result_message = messages[-1]
    assert tool_result_message["role"] == "user"
    content = tool_result_message["content"]
    assert any(
        block.get("type") == "tool_result" and block.get("tool_use_id") == "toolu_99"
        for block in content
    )


def test_conversation_history_included_in_system_prompt(generator):
    """Conversation history is appended to the system prompt."""
    generator.client.messages.create.return_value = _make_text_response("ok")

    generator.generate_response(
        query="follow-up question",
        conversation_history="User: hello\nAssistant: hi",
    )

    call_kwargs = generator.client.messages.create.call_args.kwargs
    system = call_kwargs.get("system", "")
    assert "User: hello" in system
    assert "Assistant: hi" in system
