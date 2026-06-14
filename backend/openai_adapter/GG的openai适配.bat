@echo off
set AIRP_MODEL_BASE_URL=https://gcli.ggchan.dev/v1
set AIRP_MODEL_API_KEY=gg-gcli-IOKuoaeYqDysQ7V5Jkrf8xbfBg1d3ugZ-gJQWjWZ3nw
set AIRP_MODEL_NAME=gemini-3.1-pro-preview
::  set AIRP_MODEL_NAME=gemini-2.5-pro
::  set AIRP_MODEL_NAME=gemini-3-flash-preview
::  set AIRP_MODEL_NAME=gemini-3.1-pro-preview-search
set AIRP_ADAPTER_PORT=8766
python -m openai_compatible_adapter.server