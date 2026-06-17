@echo off
set AIRP_MODEL_BASE_URL=http://localhost:8080/v1
set AIRP_MODEL_API_KEY=1
set AIRP_MODEL_NAME=Qwen3.6-35B-A3B-Claude-4.7-Opus-Reasoning-Distilled-APEX-MTP-I-Compact.gguf
::  set AIRP_MODEL_NAME=Qwen3.6-35B-A3B-UD-Q4_K_M.gguf
set AIRP_ADAPTER_PORT=8768
python -m openai_compatible_adapter.server