@echo off
set AIRP_MODEL_BASE_URL=https://catiecli.sukaka.top/v1
set AIRP_MODEL_API_KEY=cat-2e736a456a5b9571a4a1dd6625b2f1488f4af114ba903378
set AIRP_MODEL_NAME=gcli-gemini-3.1-pro-preview
::  set AIRP_MODEL_NAME=gcli-gemini-2.5-pro
::  set AIRP_MODEL_NAME=gcli-gemini-3-flash-preview
::  set AIRP_MODEL_NAME=gcli-gemini-3.1-pro-preview-search
set AIRP_ADAPTER_PORT=8766
python -m openai_compatible_adapter.server