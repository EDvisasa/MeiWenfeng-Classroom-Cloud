import pytest
from backend.services.stream_parser import StreamParser

def test_stream_parser_xml_tool_call_json():
    parser = StreamParser()
    chunk1 = {"type": "text", "text": "夫君放心，这就帮您发出测试~\n<call_openclaw_agent>{\"task_message\": \"课堂桥接测试成功\"}</call_openclaw_agent>"}
    parser.process_chunk(chunk1)

    assert parser.has_tool_calls() is True
    tools = parser.get_parsed_tool_calls()
    assert len(tools) == 1
    assert tools[0]["name"] == "call_openclaw_agent"
    assert tools[0]["param"] == {"task_message": "课堂桥接测试成功"}
    assert "raw_payload" in tools[0]
    assert tools[0]["raw_payload"]["function"]["name"] == "call_openclaw_agent"

    clean_text = parser.get_clean_content()
    assert "<call_openclaw_agent>" not in clean_text
    assert "夫君放心，这就帮您发出测试~" in clean_text

def test_stream_parser_xml_tool_call_plain_text():
    parser = StreamParser()
    chunk1 = {"type": "text", "text": "<call_openclaw_agent>课堂桥接测试成功</call_openclaw_agent>"}
    parser.process_chunk(chunk1)

    assert parser.has_tool_calls() is True
    tools = parser.get_parsed_tool_calls()
    assert len(tools) == 1
    assert tools[0]["name"] == "call_openclaw_agent"
    assert tools[0]["param"] == {"task_message": "课堂桥接测试成功"}

def test_stream_parser_no_tools():
    parser = StreamParser()
    chunk1 = {"type": "text", "text": "这里没有调用任何工具"}
    parser.process_chunk(chunk1)

    assert parser.has_tool_calls() is False
    assert len(parser.get_parsed_tool_calls()) == 0
    assert parser.get_clean_content() == "这里没有调用任何工具"
