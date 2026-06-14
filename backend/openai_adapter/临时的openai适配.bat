@echo off
set AIRP_MODEL_BASE_URL=https://sub2api.214769.icu/v1
set AIRP_MODEL_API_KEY=sk-e654f153b0d91c48e0c22f7d4704a7f19409f6d081793076fe9a101899c76dd1
set AIRP_MODEL_NAME=gpt-5.5
::  set AIRP_MODEL_NAME=gcli-gemini-2.5-pro
set AIRP_ADAPTER_PORT=8765
python -m openai_compatible_adapter.server