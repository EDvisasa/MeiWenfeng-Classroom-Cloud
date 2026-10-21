---
id: PLAN-CHANGELOG
title: Changelog
status: active
created: 2026-06-27
domain: project-planning
---
# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]
- **第三阶段深度融合与架构收敛（进行中）**：
  - 斜杠指令（Slash Commands）巨石阵模块化策略模式重构（Bug #15）
  - 潜在边界 Bug 深入排查与交互式长程闭环测试
  - 教学反馈循环、角色状态机、长期记忆衰减与判题沙盒的深度有机融合
- **第四阶段规划储备**：
  - 独立换肤、后台多任务异步调度、多智能体分布式协同扩展

## [0.3.0] - 2026-10-22 (第三阶段冲刺：课堂引擎基础设施与安全护栏 [进行中])

### Added
- **Auto-Compaction & Memory Decay Local Model Routing Defense (ISSUE-35 & Bugs #31, #32)**: Replaced fragile substring URL overriding with local endpoint whitelist protection (`localhost/127.0.0.1/0.0.0.0`) in `memory_decay.py` and `compact_service.py`, preserving active model ID and preventing hijacking to remote `.env` URLs.
- **Pure System Card Lifecycle for Persona Update (ISSUE-34)**: Streamlined `/update_persona` (`/更新人设`) to a dedicated glowing status card in `ChatPanel.jsx`, parsing SSE JSON packets safely and removing hardcoded mock assistant dialogues.
- **Current Session History Boundary Demarcation (ISSUE-33)**: Wrapped active multi-turn session dialogue strictly within `<current_session_history>`, eliminated synthetic `[USER] 你好` greetings, and isolated past RAG memories and journal archives.
- **Post-Intimacy Cooldown & Tidal Affection Dampening (ADR-011 & ISSUE-32)**: Introduced 3-tier climax physiological recovery ladder (10 -> 18 -> 24), `/cooldown` dual-state adaptive response, and increased daily net gain cap to 4 (`DAILY_GAIN_CAP = 4`).
- **Multimodal Chat Image Pipeline & Vision Awareness (ISSUE-30 & ISSUE-31)**: Added `images` column to `chat_messages`, supported image attachments and clipboard pastes in frontend `ChatPanel`, and integrated model vision modality indicators.
- **Native Document Reading in Sandbox (ISSUE-28)**: Extended `read_file` tool to support native text extraction from `.pdf` and `.docx` documents with line-based pagination.
- **Combinatorial Ambient Greeting Engine (ADR-010 & ISSUE-27)**: 4D Cartesian product ($A \times B \times C \times D$) greeting generation engine extracting 38 original vignettes from 61KB persona, dynamically keyed to physical time slots, affection stages, and reunion status without token cost.
- **Affection Temporal Decay & Reunion Warm-Up (ISSUE-26)**: Realistic affection economic model with stage-specific buffer grace periods (2~7 days), floor guarantees preventing decay beyond one stage, +3 daily net cap, and 2-turn ice-breaking critical bonus.
- **Quiz Mistake Penalty & Attitude Directive (ISSUE-25)**: Atomic affection deduction (-2) and `<slacking_warning>` emotion directive when users trigger 3 consecutive wrong answers on quiz blocks.
- **Dynamic One-Shot Pipeline Hardening**: Preserves dynamic ambient opening greetings in `assemble_messages` without text truncation or static string overwrites, while formatting standardized `<think>`, `<monologue>`, and `<property_update>` in-context demonstration.
- **Conversation Auto-Compact Engine & Cutoff Boundary (ISSUE-24)**: Dynamic model window threshold detection (32K~128K cloud vs 8K local) and `compact_cutoff_id` incremental rolling compaction preventing repeat summarization.
- **Knowledge Modal & RAG Synchronization (ADR-008 & ISSUE-09)**: Built `PreviewEditModal.jsx` and `MaterialsManager.save_material_content()` for safe markdown editing and immediate re-indexing.
- **Web Search & Deep Reading (Browser)**: Integrated `WebSearchTool` (using DuckDuckGo API) and `ReadUrlContentTool` (using `httpx`, `BeautifulSoup4`, and `markdownify`).
- **Agent Scrolling & Pagination**: Implemented an explicit line-based (800 lines max) pagination mechanism for both `read_file` and `read_url_content`, allowing the AI to scroll through massive documents/webpages without context window overflow.
- **UI Title Mapping**: Mapped `web_search` to display as "Web" and `read_url_content` as "Browser" in the frontend `ChatPanel` header.
- **Multi-Tool Concurrency**: Integrated `<tool_batch>` capability allowing the AI agent to execute multiple tools in a single response cycle.
- **Human-In-The-Loop (HITL) execution**: Interactive UI for hazardous tools (`execute_bash`). A `BashApprovalCard` component now floats natively within the `ChatPanel` enabling users to allow or reject system modifications.
- **Enhanced Agent Tools architecture**: Centralized registry for `read_file`, `grep_search`, `execute_bash`, `replace_file_content`, and `create_file` within `agent_tools.py`.
- **System Guardrails**: Injected dynamic real-world time into the AI's persona, preventing time-check hallucinations. Introduced robust safety checks blocking the use of `cat`, `type`, `grep`, and `findstr` in bash, guiding the model to use optimized native implementations.
- **Robust Multi-Turn Loop**: Overhauled `AgentExecutor.run()` to cleanly intercept server-sent events, pause for HITL inputs, and resume generation synchronously without dropping state or chunking issues.

### Fixed
- **Local Model Routing Hijack**: Resolved Bugs #31 and #32 where custom local OpenAI-compatible models (names without the literal string "本地") were hijacked by remote `.env` URLs during memory decay and auto-compaction.
- **UI State Glitches**: Resolved "ghost typing-cursor" blinking artifact that persisted after streaming had logically concluded.
- **Responsive Layout**: Rebuilt `ChatPanel` layout logic so that the input textarea safely coexists with system tool block logs and the absolute-positioned `BashApprovalCard`.
- **Sandbox Boundary Violations**: Upgraded the internal path resolution mechanisms to firmly prevent AI `replace_file_content` out-of-bounds filesystem operations (restricting modifications to `data/materials/Sandbox/`).

### Changed
- **Pipeline Segregation**: Migrated specific `execute_bash` execution loops out of the generic `ResponsePipeline` and moved them directly into the pure agent `OpenAILLMClient` wrapper flow for stronger semantic isolation.
- **Database Safety Guard**: Hardened `test_memory.py` with runtime exception interceptors, blocking any test script from wiping production `classroom.db` memory logs.

## [0.2.0] - 2026-07-04 (第二阶段：知识接入与底层基建)
### Added
- Local ChromaDB vector database integration and RAGFlow synchronization pipelines.
- Local material file tree mount (`@data/materials`) and asynchronous content parsing.
- Dialogue memory logging and multi-level vector indexing.

## [0.1.0] - 2026-06-27 (第一阶段：MVP 最小可用原型)
### Added
- Three-column IDE workspace layout (file tree / central classroom chat / status sidebar).
- FastAPI asynchronous backend with LiteLLM proxy and OpenAI streaming SSE pipeline.
- Character persona prompt mounting and basic dynamic property updates.


