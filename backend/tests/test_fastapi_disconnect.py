import pytest
import asyncio
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from fastapi.testclient import TestClient

app = FastAPI()

def sync_generator():
    try:
        for i in range(5):
            yield f"data: {i}\n\n"
    except Exception as e:
        # In a real scenario, this catches GeneratorExit if the client disconnects
        pass
    finally:
        pass

@app.get("/stream")
def stream():
    return StreamingResponse(sync_generator(), media_type="text/event-stream")

def test_fastapi_streaming_response():
    """
    Test that StreamingResponse works and can be consumed correctly.
    (This is an automated version of the manual disconnect script, ensuring SSE flows normally).
    """
    client = TestClient(app)
    with client.stream("GET", "/stream") as response:
        assert response.status_code == 200
        content = list(response.iter_lines())
        
        # There are empty lines due to \n\n in SSE
        events = [line for line in content if line.startswith("data: ")]
        assert len(events) == 5
        assert events[0] == "data: 0"
        assert events[-1] == "data: 4"
