import pytest
import json
from backend.services.response_pipeline import ResponsePipeline
from backend.services.action_registry import ActionRegistry, SideEffectHandler

class DummyHandler(SideEffectHandler):
    def __init__(self, name):
        self.name = name
        self.called = False
        self.attrs = None
        self.content = None

    def handle(self, attrs, content):
        self.called = True
        self.attrs = attrs
        self.content = content

def test_pipeline_interception():
    registry = ActionRegistry()
    h1 = DummyHandler("finalize_mission")
    h2 = DummyHandler("property_update")
    registry.register("finalize_mission", h1)
    registry.register("property_update", h2)

    pipeline = ResponsePipeline(registry=registry)

    stream_data = [
        "咱们的‘修仙大计’，正式成契啦~” <finalize_mission goal=\"学习\" time=\"每天2小时\" constraints=\"使用STM\" skill=\"掌握\" /><property_update affection_delta=\"+1\" refractory_delta=\"-1\" />"
    ]

    def raw_stream():
        for chunk in stream_data:
            yield chunk

    out = ""
    for res in pipeline.process_stream(raw_stream()):
        if isinstance(res, str) and res.startswith("data: "):
            try:
                d = json.loads(res[6:].strip())
                out += d.get("text", "")
            except:
                out += res[6:].strip()
        elif isinstance(res, dict):
            out += res.get("text", "")

    # 验证是否正确拦截并清除了输出
    assert "咱们的‘修仙大计’，正式成契啦~”" in out
    assert "<finalize_mission" not in out
    assert "<property_update" not in out

    # 验证 Handler 是否被正确调用
    assert h1.called is True
    assert h1.attrs.get("goal") == "学习"
    assert h1.attrs.get("time") == "每天2小时"

    assert h2.called is True
    assert h2.attrs.get("affection_delta") == "+1"
    assert h2.attrs.get("refractory_delta") == "-1"
