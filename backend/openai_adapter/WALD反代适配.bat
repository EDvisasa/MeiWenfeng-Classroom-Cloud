@echo off
set AIRP_MODEL_BASE_URL=http://127.0.0.1:18000/v1
set AIRP_MODEL_API_KEY=sk-wald-74c3ad8f21c7cd91
::  set AIRP_MODEL_NAME=gpt-5.2
::  set AIRP_MODEL_NAME=gemini-3-pro
set AIRP_MODEL_NAME=claude-opus-4-5
::  set AIRP_MODEL_NAME=claude-sonnet-4-5
set AIRP_ADAPTER_PORT=8767
python -m openai_compatible_adapter.server
