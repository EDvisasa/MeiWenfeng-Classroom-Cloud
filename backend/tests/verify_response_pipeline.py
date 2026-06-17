import time
import subprocess
import requests
import sqlite3
import json
import os
import signal

def main():
    PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    # 1. Start the server
    print("Starting server...")
    server_process = subprocess.Popen(
        ["python", "backend/main.py"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=PROJECT_ROOT
    )

    # Wait for the server to be healthy
    max_retries = 30
    port = 12701
    health_url = f"http://127.0.0.1:{port}/api/health"
    is_healthy = False
    for i in range(max_retries):
        try:
            resp = requests.get(health_url)
            if resp.status_code == 200:
                is_healthy = True
                break
        except Exception:
            pass
        time.sleep(1)

    if not is_healthy:
        print("Server failed to start or become healthy.")
        server_process.kill()
        return

    print("Server is healthy.")

    # 2. Send POST request to /api/chat/send
    url = f"http://127.0.0.1:{port}/api/chat/send"
    payload = {
        "messages": [{"role": "user", "content": "请给我解释一下什么是量子计算，并用 glossary 标签提取核心术语"}],
        "persona_type": "媚吻锋"
    }

    print("Sending request to chat endpoint...")
    try:
        response = requests.post(url, json=payload, stream=True)
        response.raise_for_status()

        # 3. Observe the SSE stream
        sse_content = ""
        glossary_in_stream = False

        for line in response.iter_lines():
            if line:
                decoded_line = line.decode('utf-8')
                if decoded_line.startswith("data: "):
                    data_str = decoded_line[6:]
                    if data_str == "[DONE]":
                        break
                    try:
                        data = json.loads(data_str)
                        if "text" in data:
                            sse_content += data["text"]
                        elif "delta" in data:
                            sse_content += data["delta"]
                    except json.JSONDecodeError:
                        pass

        print("SSE Stream finished.")
        print("SSE Content:", sse_content)

        # 4. Verify that <glossary> is hidden from stream
        if "<glossary" in sse_content or "</glossary>" in sse_content:
            print("FAILED: <glossary> tag found in SSE stream!")
            glossary_in_stream = True
        else:
            print("SUCCESS: <glossary> tag is completely hidden from SSE stream.")

        # 5. Verify the glossary term was written to the database
        db_path = os.path.join(PROJECT_ROOT, "backend", "classroom.db")
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Let's check glossary for term="量子计算"
        cursor.execute("SELECT * FROM glossary ORDER BY id DESC LIMIT 5")
        memories = cursor.fetchall()
        print("Recent glossary entries:", memories)

        conn.close()

    except Exception as e:
        print("Error during request:", e)
        server_process.terminate()
        stdout, stderr = server_process.communicate()
        print("Server STDOUT:", stdout.decode('utf-8', errors='ignore'))
        print("Server STDERR:", stderr.decode('utf-8', errors='ignore'))

    finally:
        # Stop the server
        print("Stopping server...")
        try:
            server_process.terminate()
            server_process.wait(timeout=2)
        except Exception:
            pass

if __name__ == "__main__":
    main()
