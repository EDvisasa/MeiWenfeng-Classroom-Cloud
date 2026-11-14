import asyncio
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from fastapi.responses import StreamingResponse

from backend.services.slash_handler import (
    CommandRegistry,
    CommandStrategy,
    SlashCommandContext,
    SlashHandler,
    command_registry,
    handle_slash_command,
)


def _dummy_payload(**kwargs):
    defaults = {"current_file_path": None, "persona_type": "simplified", "session_id": "sess_test"}
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def test_default_registry_resolves_all_expected_commands_and_aliases():
    expected_commands = [
        "/update_persona",
        "update_persona",
        "/更新人设",
        "/summarize",
        "/compact",
        "/prepare",
        "/reward",
        "/cooldown",
        "cooldown",
        "/cancel_mission",
        "/end_lesson",
        "/下课",
        "/recess",
        "/dismiss",
        "/lesson_continue",
        "/submit",
    ]
    for cmd in expected_commands:
        assert command_registry.resolve(cmd) is not None

    assert command_registry.resolve("/lesson").__class__.__name__ == "LessonCommandStrategy"
    assert command_registry.resolve("/lesson math_101").__class__.__name__ == "LessonCommandStrategy"
    assert command_registry.resolve("/lesson_continue").__class__.__name__ == "LessonContinueCommandStrategy"
    assert command_registry.resolve("/plan math_101").__class__.__name__ == "PlanCommandStrategy"
    assert command_registry.resolve("/set_mission learn rust").__class__.__name__ == "SetMissionCommandStrategy"
    assert command_registry.resolve("/unknown_cmd").__class__.__name__ == "DefaultFallbackCommandStrategy"


def test_command_registry_supports_custom_strategy_and_deletion_isolation():
    class PingStrategy(CommandStrategy):
        aliases = ("/ping",)

        def execute(self, ctx: SlashCommandContext) -> StreamingResponse:
            return StreamingResponse(iter(["pong"]), media_type="text/event-stream")

    class FallbackStrategy(CommandStrategy):
        def execute(self, ctx: SlashCommandContext) -> StreamingResponse:
            return StreamingResponse(iter(["fallback"]), media_type="text/event-stream")

    registry = CommandRegistry()
    registry.register(PingStrategy())
    registry.register(FallbackStrategy(), fallback=True)

    ping_ctx = SlashCommandContext.from_request("/PING", _dummy_payload(), "/PING", [])
    unknown_ctx = SlashCommandContext.from_request("/missing", _dummy_payload(), "/missing", [])

    async def _collect(resp: StreamingResponse):
        return [chunk async for chunk in resp.body_iterator]

    assert asyncio.run(_collect(registry.dispatch(ping_ctx))) == ["pong"]
    assert asyncio.run(_collect(registry.dispatch(unknown_ctx))) == ["fallback"]


def test_unknown_command_uses_fallback_strategy_and_empty_injection():
    with patch("backend.services.slash_handler._stream_normal_chat_with_injection") as mock_stream:
        mock_stream.return_value = MagicMock()
        handle_slash_command("/nonexistent_cmd", _dummy_payload(), "/nonexistent_cmd", [])

        assert mock_stream.called
        assert mock_stream.call_args[0][3] == ""


def test_slash_handler_static_proxy_delegates_to_registry():
    with patch("backend.services.slash_handler._stream_normal_chat_with_injection") as mock_stream:
        mock_stream.return_value = StreamingResponse(iter(["ok"]), media_type="text/event-stream")
        iterator = SlashHandler.handle("/submit", session_id="sess_proxy")

        assert iterator is not None
        assert mock_stream.called


def test_submit_strategy_dispatches_socratic_directive():
    with patch("backend.services.slash_handler._stream_normal_chat_with_injection") as mock_stream:
        mock_stream.return_value = MagicMock()
        handle_slash_command("/submit", _dummy_payload(), "/submit", [])

        assert mock_stream.called
        injection = mock_stream.call_args[0][3]
        assert 'mode="socratic_strict_mentor"' in injection
        assert "/submit" in injection


def test_cancel_mission_strategy_cancels_draft_and_injects_directive():
    with patch("backend.services.mission_manager.MissionManager.cancel_draft") as mock_cancel, \
         patch("backend.services.slash_handler._stream_normal_chat_with_injection") as mock_stream:
        mock_stream.return_value = MagicMock()
        handle_slash_command("/cancel_mission", _dummy_payload(), "/cancel_mission", [])

        mock_cancel.assert_called_once()
        assert mock_stream.called
        assert "/cancel_mission" in mock_stream.call_args[0][3]
