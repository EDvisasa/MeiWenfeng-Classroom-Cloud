import subprocess
import json
import time
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

_STATUS_CACHE = {"timestamp": 0.0, "result": None}

def send_to_openclaw(
    message: str,
    agent: str = "main",
    timeout: int = 60,
    json_output: bool = True,
    wsl_distro: str = "OpenClawGateway",
    wsl_user: str = "openclaw"
) -> Dict[str, Any]:
    """
    Send a message or instruction to an OpenClaw gateway agent via WSL CLI.
    
    Args:
        message: The message text to deliver to the OpenClaw agent.
        agent: The target agent ID in OpenClaw (default: "main").
        timeout: Execution timeout in seconds (default: 60).
        json_output: Whether to request JSON formatted output from openclaw CLI.
        wsl_distro: Name of the WSL distribution hosting OpenClaw.
        wsl_user: Linux user in the WSL distribution.
        
    Returns:
        Dict[str, Any]: Structured execution result containing status, response, or error details.
    """
    if not message or not message.strip():
        return {
            "status": "error",
            "message": "Message content cannot be empty."
        }

    cmd = [
        "wsl", "-d", wsl_distro, "-u", wsl_user, "--",
        "openclaw", "agent", "--agent", agent, "--message", message
    ]
    if json_output:
        cmd.append("--json")

    logger.info(f"Invoking OpenClaw CLI for agent '{agent}' via WSL distribution '{wsl_distro}'")

    try:
        res = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout
        )
        
        stdout_str = res.stdout.strip() if res.stdout else ""
        stderr_str = res.stderr.strip() if res.stderr else ""

        if res.returncode != 0:
            logger.error(f"OpenClaw CLI exited with code {res.returncode}. Stderr: {stderr_str}")
            return {
                "status": "error",
                "code": res.returncode,
                "message": f"CLI execution failed with return code {res.returncode}",
                "stdout": stdout_str,
                "stderr": stderr_str
            }

        if json_output and stdout_str:
            try:
                parsed_json = json.loads(stdout_str)
                return {
                    "status": "success",
                    "data": parsed_json,
                    "raw": stdout_str
                }
            except json.JSONDecodeError:
                # Fallback if output contains non-JSON prefix or formatting issues
                logger.warning("Failed to parse OpenClaw JSON output, returning raw text.")
                return {
                    "status": "success",
                    "data": {"text": stdout_str},
                    "raw": stdout_str
                }
        
        return {
            "status": "success",
            "data": {"text": stdout_str},
            "raw": stdout_str
        }

    except subprocess.TimeoutExpired:
        logger.error(f"OpenClaw CLI execution timed out after {timeout} seconds.")
        return {
            "status": "error",
            "message": f"Execution timed out after {timeout} seconds."
        }
    except Exception as e:
        logger.exception(f"Unexpected error when sending message to OpenClaw: {str(e)}")
        return {
            "status": "error",
            "message": f"Unexpected execution error: {str(e)}"
        }

def clear_openclaw_status_cache():
    """Clear the in-memory TTL status cache."""
    _STATUS_CACHE["timestamp"] = 0.0
    _STATUS_CACHE["result"] = None

def check_openclaw_status(
    timeout: int = 3,
    ttl: float = 5.0,
    wsl_distro: str = "OpenClawGateway",
    wsl_user: str = "openclaw"
) -> Dict[str, Any]:
    """
    Check if the WSL OpenClaw Gateway is reachable and online within `timeout` seconds.
    Results are cached in-memory for `ttl` seconds to avoid overhead.
    """
    now = time.time()
    if _STATUS_CACHE["result"] is not None and (now - _STATUS_CACHE["timestamp"]) < ttl:
        return _STATUS_CACHE["result"]

    cmd = [
        "wsl", "-d", wsl_distro, "-u", wsl_user, "--",
        "openclaw", "--version"
    ]
    try:
        res = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout
        )
        if res.returncode == 0:
            version_str = res.stdout.strip() if res.stdout else "Unknown version"
            status_result = {
                "online": True,
                "status_str": f"ONLINE (WSL OpenClaw Gateway ready: {version_str})",
                "version": version_str
            }
        else:
            err_msg = res.stderr.strip() or res.stdout.strip() or f"exited with code {res.returncode}"
            status_result = {
                "online": False,
                "status_str": f"OFFLINE (WSL OpenClaw Gateway error: {err_msg})",
                "reason": err_msg
            }
    except Exception as e:
        status_result = {
            "online": False,
            "status_str": f"OFFLINE (WSL OpenClaw Gateway unreachable: {str(e)})",
            "reason": str(e)
        }

    _STATUS_CACHE["timestamp"] = now
    _STATUS_CACHE["result"] = status_result
    return status_result

