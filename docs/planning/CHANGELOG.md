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

### Added
- **全站 Markdown 数学公式 KaTeX 原生排版渲染与插件 SSOT (ISSUE-54 & Bug #40)**:
  - 引入 `remark-math`、`rehype-katex` 与自定义 `remarkDisplayMathFromDoubleDollar` 插件，将行间公式 `$$...$$` 与行内公式 `$...$` 转化为 KaTeX HTML 排版，杜绝裸美元符外露；
  - 提炼 `frontend/src/utils/markdownPlugins.js` 作为全库唯一的 Markdown 渲染插件单一点 (SSOT)，聊天气泡与知识档案预览弹窗统一复用；
  - 引入 `katex.min.css` 并对 `.katex-display` 设置横向平滑滚动防撑破。
- **前端【生活/研学】状态胶囊切换器与微课上课引导微卡 (ISSUE-49)**:
  - 在右侧 `StatusPanel` 的【精简/原版】按钮右侧新增同等圆框切换按钮（【生活/研学】），粉色高亮即研学，透明即生活；
  - 采用简洁无括号的系统提示与 `localStorage` 本地存储同步（默认初始为生活模式）；
  - 在生活模式下发送 `/lesson` 微课指令时，聊天流内嵌一键切换微卡，方便用户即刻切换为高校研学水准。
- **【生活/研学】双氛围模式提示词规范与后端全链路路由 (ISSUE-48)**:
  - 在 `prompts.py` 中将 `<pedagogy_and_worldview>` 升级为动静解耦的双模式静态定义：生活模式（家庭温情伴读）与研学模式（中国高中至大学水准现代数理教学、现代真实案例、杜绝牵强土味比喻）；
  - `ChatRequest` 增加 `atmosphere_mode` 参数，并在 `context_manager` 运行时尾部注入生效标签，保持静态 System Prompt 的 KV-Cache 命中率。

### Fixed
- **KV-Cache 前缀稳态分层、多模态先图后文与 `@file` 边界抽离 (Bug #47)**:
  - 在 `backend/services/context_manager.py` 的 `assemble_messages` 内实施 `<system_injection>` 静先动后分层，将 `<agent_execution_protocol>` 前置并把 `<active_atmosphere_mode>`、`<openclaw_gateway_status>`、`<current_time>` 沉底，同时将 `<current_time>` 精度降为分钟级（`%Y-%m-%d %H:%M`），避免重试或重生成触发前缀缓存失效；
  - 在 `backend/routers/chat.py`（`_order_multimodal_images_first`）与 `context_manager.py`（`_order_images_first`、`_merge_message_contents`、`assemble_messages`）严格规范多模态数组顺序，确保所有 `image_url` 永远位于 `text` 之前，适配端侧推理 `strata-poly` / `kvmem` 的 bounded Query 校验；
  - 在 `chat.py`（`_attach_file_into_last_user_msg`）统一收口 `@current_file` 与 `@path` 文件展开，并在 `context_manager.py` 新增 `_extract_file_contents` 将 `<file_content>` 锚定前移至 `</current_session_history>` 之前，保证动态尾部收敛在 8192 QueryMaxTokens 上限内；
  - 同步补充 `ADR-009` 架构演进补丁。
- **全链路测试与生产记忆库/ChromaDB 物理隔离与硬熔断守卫 (Bug #46)**:
  - `ChatRequest` 新增 `dry_run` 只读演练参数，`backend/services/response_pipeline.py` 增加持久化熔断守卫（命中 `dry_run` 或生产 DB 下的测试会话前缀时旁路跳过 `memory_logs` 与 ChromaDB 写入）；
  - `backend/services/chroma_client.py` 改为动态解析 `get_chroma_persist_dir()`（支持 `CHROMA_PERSIST_DIR` 覆盖），并新增 `_check_mutation_safety()` 硬阻断 pytest 对生产目录 `DEFAULT_CHROMA_DIR` 的增删改；
  - `backend/tests/conftest.py` 增设 `isolate_chroma_db`（autouse 临时目录重定向）与 `mock_rag_client`，精简对齐 `AGENTS.md` 与 `docs/01_dev_and_test_guide.md` 防污染红线，并同步补充 `ADR-003`、`ADR-005` 架构演进补丁。
- **右侧状态面板加宽与顶部胶囊按钮防挤压 (ISSUE-55 & Bug #41)**:
  - 将 `.right-panel-container` 宽度由 `300px` 提至 `344px` 确立为宽度单一点 (SSOT)，`.right-panel` 改为 `width: 100%`，彻底解决胶囊按钮挤成两行与字词折行问题；
  - 提炼 `pillStyle` 统一按钮内联样式，施加 `whiteSpace: 'nowrap'`、`flexShrink: 0` 与 `lineHeight: 1`，清除多余边距与重叠挤压源。
- **PolyStrata 推理引擎 Tool Calling 400 根治与 Tool Calls Dict 规范化 (ISSUE-50)**:
  - 针对底层端侧 PolyStrata / Jinja 模板校验触发 `TemplateRequestError` 导致 HTTP 400 的问题，在 `backend/services/agent_executor.py` 实施参数类型规范化；
  - 对原生与 XML 解析提取的 `tool_calls` 参数执行深拷贝与 `json.loads` 反序列化为 Python Dict，兼容根层级与 `function` 层级字段；
  - 在单轮 Agent 工具调用循环（Tool Calling Loop）内保持严格的 Append-Only 追加语义与缓存命中。

### Changed
- **上下文双层场域隔离与 KV Cache 静态基石前缀加速理顺 (ISSUE-51)**:
  - 明确业务红线：保留 `<current_session_history>`（防 RAG 记忆召回幻觉的认知屏障）与动态 `<current_time>`（作息与好感度演化的时间脉搏），回执归档于 `docs/reports/receipt_to_poly_engine_agent.md`；
  - 保证 `formatted_messages[0]`（System Prompt）纯净且单会话字节级恒定，锁定长上下文前缀 KV-Cache 命中；
  - 固化历史轮次时序标尺 `[YYYY-MM-DD HH:MM]`，动态尾部协议单向挂载在最新的 User 消息中。
- **通用人设压缩提取元结构与调色盘三元组解耦 (ISSUE-47)**:
  - 在 `prompts.py` 中重构 `SUMMARIZATION_SYSTEM_PROMPT`，将具体角色字段替换为通用 `[Concise summary]` 占位符，支持跨角色迁移；
  - 性格调色盘与 NSFW 调色盘采用 `底色 / 主色调 / 点缀` 三元组方法论，解除硬编码并动态提取原卡性格标签；
  - 维持 `内心的拧巴与纠结` 与 `数值绑定` 双槽位结构，将自我认同统一纳入演化绑定，并在亲密总结中聚焦心理动机与事后温存（aftercare）。
- **交互式测验 (Quiz) 静态 Schema 统一定义、选项随机轮换分布与微课指令解耦 (ISSUE-46)**:
  - 在静态提示词层（`prompts.py`）确立微卡、讲义卡、交互题单卡三大内容规范并实现规则与示例解耦；
  - 引入答案位置随机轮换分布（0, 1, 2, 3）并补充带 `<quiz>` 的单回合完整示范，防止漏掉 `<monologue>` 与 `<property_update>`；
  - 剥离 `slash_handler.py` 中重复的 15 行 JSON 模板与出题规则，节省约 300 动态 Token，并在 `/lesson`（ZPD 三阶梯度 0.5-1.0 / 1.1-2.0 / 2.1-3.0）与 `/lesson_continue` 建立自适应心流闭环。

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


