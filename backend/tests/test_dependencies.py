import pytest

def test_litellm_proxy_dependencies():
    """
    Test that the LiteLLM proxy server dependencies (e.g., 'backoff', 'websockets')
    are properly installed. This prevents regressions where `litellm` is installed
    without the `[proxy]` extras, which would cause the gateway to crash on startup.
    """
    try:
        # Import the proxy server module to trigger any missing dependency errors
        import litellm.proxy.proxy_server
    except ImportError as e:
        pytest.fail(f"LiteLLM proxy dependencies are missing. Did you install `litellm[proxy]`? Error: {e}")
    except Exception as e:
        # We only care about ImportErrors here. 
        # Other initialization errors might occur if it expects env vars, but we just want to check imports.
        pass
