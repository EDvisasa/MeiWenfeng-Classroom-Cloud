import subprocess
import time
import os
import signal
import sys
import requests

def test_uvicorn_graceful_shutdown_on_windows():
    """
    TDD Test to verify that FastAPI exits gracefully on Windows when CTRL_BREAK_EVENT is sent,
    even if ChromaDB or other background threads are active.
    """
    if os.name != 'nt':
        return  # Only applicable for Windows

    # Start the FastAPI server in a subprocess
    # We use a custom port to avoid interfering with the running server
    port = 12799
    
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "backend.main:app", "--host", "127.0.0.1", "--port", str(port)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
    )

    try:
        # Wait for the server to be healthy
        healthy = False
        for _ in range(30):
            try:
                res = requests.get(f"http://127.0.0.1:{port}/api/health", timeout=1)
                if res.status_code == 200:
                    healthy = True
                    break
            except Exception:
                pass
            time.sleep(0.5)

        assert healthy, "FastAPI server failed to start or become healthy within 15 seconds"

        # Send CTRL_BREAK_EVENT to trigger graceful shutdown
        try:
            proc.send_signal(signal.CTRL_BREAK_EVENT)
        except Exception:
            pass

        # Wait for the process to exit (timeout = 6 seconds, since our patch waits 1 second)
        try:
            # We wait up to 6 seconds for it to exit
            proc.wait(timeout=6)
        except subprocess.TimeoutExpired:
            # If it times out, the zombie process bug is active!
            # We must force kill it to prevent polluting the test environment
            proc.kill()
            proc.wait()
            raise AssertionError("RED STATE: Process failed to terminate gracefully and became a zombie!")
            
    finally:
        # Failsafe kill just in case
        if proc.poll() is None:
            proc.kill()
            proc.wait()
