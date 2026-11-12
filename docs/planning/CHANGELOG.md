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
- **前端【生活/研学】状态胶囊切换器与微课上课引导微卡 (ISSUE-49)**:
  - 在右侧 `StatusPanel` 的【精简/原版】按钮右侧新增同等圆框切换按钮（【生活/研学】），粉色高亮即研学，透明即生活；
  - 采用简洁无括号的系统提示与 `localStorage` 本地存储同步（默认初始为生活模式）；
  - 在生活模式下发送 `/lesson` 微课指令时，聊天流内嵌一键切换微卡，方便用户即刻切换为高校研学水准；
  - 全量补齐 `StatusPanel` 与 `ChatPanel` 单元测试，60 项前端测试 100% 绿灯。
- **【生活/研学】双氛围模式提示词规范与后端全链路路由 (ISSUE-48)**:
  - 在 `prompts.py` 中将 `<pedagogy_and_worldview>` 升级为动静解耦的双模式静态定义：生活模式（家庭温情伴读）与研学模式（中国高中至大学水准现代数理教学、现代真实案例、杜绝牵强土味比喻）；
  - `ChatRequest` 增加 `atmosphere_mode` 参数，并在 `context_manager` 运行时尾部注入生效标签，100% 保持静态 System Prompt 的 KV-Cache 命中率；
  - 后端 21 项回归测试 100% 绿灯。
- **通用人设压缩提取元结构与调色盘三元组解耦 (ISSUE-47)**:
  - 在 `prompts.py` 中重构 `SUMMARIZATION_SYSTEM_PROMPT`，将所有具体角色字段替换为通用的 `[Concise summary]` 占位符，支持跨角色（如玄一峰等）无损迁移；
  - 性格调色盘与 NSFW 调色盘全面采用 `底色 / 主色调 / 点缀` 三元组方法论，解除硬编码并动态提取原卡性格标签；
  - 维持 `内心的拧巴与纠结` 与 `数值绑定` 双槽位结构，将自我认同统一纳入演化绑定，消除分类学层级错位；
  - 确立严肃教学/正事场景下的引导陪伴风貌，在亲密总结中聚焦心理动机与事后温存（aftercare），杜绝低俗解剖描写。
- **交互式测验 (Quiz) 静态 Schema 统一定义、选项随机轮换分布与微课指令解耦 (ISSUE-46)**:
  - 建立了静态提示词层（`prompts.py`）的三大内容卡片规范（微卡、讲义卡、交互题单卡），并使规则说明与结构示例完全解耦（ADR-002 高信噪比）；
  - 引入答案位置随机轮换铁律（均匀分布于 0, 1, 2, 3），解除 Schema 中固定为 0 的锚定效应；
  - 补充带 `<quiz>` 的单回合完整闭环示范，杜绝出题后漏掉 `<monologue>` 与 `<property_update>`；
  - 彻底剥离 `slash_handler.py` 中重复的 15 行 JSON 模板与出题规则，节省 ~300 动态 Token；
  - 为 `/lesson` 列装 ZPD 三阶认知梯度（0.5-1.0 基础直观概念 / 1.1-2.0 边界执行流程 / 2.1-3.0 底层组合机制）；
  - 为 `/lesson_continue` 确立自适应进退心流闭环（答对推进/挑战高阶题并触发好感度激励，答错变式题巩固）。
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


