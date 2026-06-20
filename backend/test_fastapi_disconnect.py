import time
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
import uvicorn
import asyncio

app = FastAPI()

def sync_generator():
    try:
        print("Generator started")
        for i in range(10):
            print(f"Generator yielding {i}")
            yield f"data: {i}\n\n"
            print(f"Generator yielded {i}, sleeping...")
            time.sleep(1)
    except Exception as e:
        print(f"Generator caught exception: {repr(e)}")
    finally:
        print("Generator finished")

@app.get("/stream")
def stream():
    return StreamingResponse(sync_generator(), media_type="text/event-stream")

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8001)
