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
- **记忆工具家族原子化拆分、`calendar` 日程目录、渐进式日期引导与四类正交高信噪比路由 (PLAN-03 v1.1 / ISSUE-66, ISSUE-67, ISSUE-68)**:
  - **解除循环深度与步数上限 (`ISSUE-66`)**：移除 `AgentExecutor.MAX_MEMORY_SEARCH_STEPS = 3` 拦截及 `model_router.py` `max_iterations=5` 硬编码上限（改为默认 `max_iterations=None` 无上限探索，由 `_sanitize_tool_output` 与前端停止控制器保底）；
  - **四原子工具拆分与渐进日期导航 (`ISSUE-67`)**：将原单一复合 `search_memory(mode=...)` 拆分为 4 个零 `mode`、带显式 `required` 约束的单职责工具（按渐进漏斗顺序：`get_memory_calendar`、`get_memory_timeline`、`search_memory`、`expand_memory`）；在 `MemorySearchEngine` 补齐 `'YYYY'` / `'all'` 范围、`start_date`/`end_date` 闭区间、`order` (`newest`/`oldest`) 方向控制与截断时的 `earliest_active_day` 锚点、`calendar`（支持 `target`/`order`/`limit`）每日会话段/标题/日记汇总统计及空日期渐进活跃索引（查天为空返回同月活跃日期及条数 -> 整月空返回同年活跃月份 -> 全年空返回有记录年份）；同步更新 `StreamParser`、`ToolExecutionEngine._format_command_str` 及前端 `ChatPanel.jsx`（`MEMORY_TOOL_NAMES` 使跨子工具连续调用收敛折叠为单张 `Remembering...` 多步卡片）；
  - **四类正交工具标签与小模型高信噪比路由 (`ISSUE-68`)**：`TOOL_REGISTRY` 全量 12 工具 `description` 首词统一挂 `[Memory]` / `[Workspace]` / `[Web]` / `[Collab]` 标签，彻底移除 `SearchMemoryTool` 家族中的 `chat_messages`/`memory_logs` SQL 表名诱因并为 `[Workspace]` 工具注入负向排除后缀；将 `context_manager.py` `<environment_constraints>` 规则折叠为 4 行 `TOOL ROUTING` 对照表，消除 Step 2 句首 OpenClaw 全局先验偏置，并在 `<retrieved_past_memory_archives>` 与 `<recent_journal_summaries>` 末尾补充 1 句就地 `[Memory]` 指引（保持 `get_static_system_prompt()` 零改动）。
- **智能体自主记忆检索工具 (`search_memory`) 与前端 `Remembering...` 多步折叠卡片 (PLAN-03 / ISSUE-52 & ISSUE-53)**:
  - 新增 `backend/services/memory_search_engine.py`（`MemorySearchEngine`）并在 `backend/services/agent_tools.py` 注册安全工具 `SearchMemoryTool`，支持 `search` / `timeline` 短摘要浏览（~150 字，默认 5 条、上限 15 条，SQL LIKE 通配符转义与日期范围筛选）与 `expand` 完整日记/同会话上下文窗口展开（自动剥离历史 `<think>` / `<monologue>` / `<property_update>` 控制标签）；
  - 在 `backend/services/agent_executor.py` 加入单轮记忆检索硬上限保护（`MAX_MEMORY_SEARCH_STEPS = 3`），超限后跳过查库直接返回纯客观收敛提示；同步完善 `stream_parser.py` 已知工具正则识别、`tool_engine.py` 可读命令格式化及 `context_manager.py` 动态尾部纯客观英文工具协议指引（零人设台词干预、不动 `static_system_prompt`）；
  - 在 `frontend/src/components/ChatPanel.jsx`（`TOOL_FRIENDLY_NAMES` 与 `groupConsecutiveMemoryTools`）与 `frontend/src/index.css` 实现 `Remembering...` 状态卡片：支持紫色脉冲呼吸运行态、同轮连续 `search_memory` 调用收敛折叠为单张可展开多步卡片，并修正 `mergedBlocks` 传递 `msg.streaming` 以保证流式 `running` 态正确生效。
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
- **学习目标契约卡片 `<finalize_mission />` 渲染、用户消息原样保真与双系统文案隔离 (Bug #53)**:
  - 在 [`frontend/src/utils/blockParser.js`](file:///d:/MeiWenfeng-Classroom/frontend/src/utils/blockParser.js) 与 [`frontend/src/utils/markdownPlugins.js`](file:///d:/MeiWenfeng-Classroom/frontend/src/utils/markdownPlugins.js) 中为导师回复解析 `<finalize_mission ... />`（兼容跨行 `/>` 与 `&quot;`）及 `<mission_proposal>` 的 `course_id`；同时引入 `rawUserMessage` 与 `userRemarkPlugins`，确保用户气泡彻底保留原文（不运行 `stripControlTags`、不触发 AI 卡片与 `<glossary>` 改写）；
  - 在 [`frontend/src/components/MissionProposalCard.jsx`](file:///d:/MeiWenfeng-Classroom/frontend/src/components/MissionProposalCard.jsx) 与 [`frontend/src/components/ChatPanel.jsx`](file:///d:/MeiWenfeng-Classroom/frontend/src/components/ChatPanel.jsx) 保持 `course_id` 确认透传，将确认发送前缀去角色扮演化改为中性教学句式 `我已确定学习目标`，并渲染只读“学习契约已立项”卡片（`.mission-finalized-card`，配 [`frontend/src/index.css`](file:///d:/MeiWenfeng-Classroom/frontend/src/index.css) 亮暗双主题样式）；
  - 在 [`backend/services/memory_search_engine.py`](file:///d:/MeiWenfeng-Classroom/backend/services/memory_search_engine.py) 扩展 `STRIP_INTERNAL_TAGS_RE`（清理 `<finalize_mission>`、`<new_course>`、`<memory_decay>`、`<system_pass>`），并新增共享的 `format_message_for_memory(role, text)`，使记忆搜索/展开与 [`backend/services/compact_service.py`](file:///d:/MeiWenfeng-Classroom/backend/services/compact_service.py) 上下文压缩仅清洗 `assistant` 与 `journals` 记录、`user` 原文保持完整，同时维持 `ResponsePipeline` SSE 透传契约不变。
- **聊天区流式“蹦字”智能粘性滚动与悬浮回底按钮修复 (Bug #52)**:
  - 移除 [`frontend/src/App.jsx`](file:///d:/MeiWenfeng-Classroom/frontend/src/App.jsx) 中全局无条件监听 `messages` 的 `scrollIntoView({ behavior: 'smooth' })`，改为在会话切换、新建会话及发送/重发指令时通过显式信号重置贴底；
  - 在 [`frontend/src/components/ChatPanel.jsx`](file:///d:/MeiWenfeng-Classroom/frontend/src/components/ChatPanel.jsx) 提取 `useStickyChatScroll` 与 [`frontend/src/index.css`](file:///d:/MeiWenfeng-Classroom/frontend/src/index.css) 悬浮 `.scroll-to-bottom-btn`：流式跟随使用瞬时贴底告别滚轮打架，上滑脱离底部（`> 48px`）即刻暂停自动拉底，超过 `120px` 在右下角显示紧凑圆形向下箭头按钮（流式期带提示微点），手动滚回底部或切回新提问自动恢复跟随。
- **历史对话弹出框视口限高、搜索与分页修复 (Bug #51)**:
  - 在 [`frontend/src/components/ChatPanel.jsx`](file:///d:/MeiWenfeng-Classroom/frontend/src/components/ChatPanel.jsx) 提取 `SessionListPopover` 组件，引入每页 8 条分页、`openclaw_trio_chat` 首页置顶、自动跳转当前活跃会话页、标题关键词搜索、页码越界自动夹紧以及点击外部 / `Escape` 键自动关闭；
  - 在 [`frontend/src/index.css`](file:///d:/MeiWenfeng-Classroom/frontend/src/index.css) 为 `.session-list-popover` 增加 `max-height: min(440px, calc(100vh - 96px))`、`max-width: min(300px, calc(100vw - 24px))` 与 `.session-list-body` 内部独立纵向滚动区，避免会话较多时撑破屏幕底边。
- **全站 Markdown `<glossary>` 行内术语微卡渲染修复 (Bug #50)**:
  - 在全站渲染 SSOT [`frontend/src/utils/markdownPlugins.js`](file:///d:/MeiWenfeng-Classroom/frontend/src/utils/markdownPlugins.js) 新增纯 mdast 插件 `remarkGlossaryTags`，不启用 `rehype-raw` 即可把 `<explainer>` 讲义卡、列表加粗句内与档案预览弹窗中的 `<glossary term="...">...</glossary>`（含流式未闭合与内嵌 KaTeX 公式）安全渲染为 `.glossary-inline-badge` 术语徽标 + `.glossary-inline-def`（自动复位粗体继承）；
  - 修正 [`frontend/src/utils/blockParser.js`](file:///d:/MeiWenfeng-Classroom/frontend/src/utils/blockParser.js) 仅对独占整行的 `<glossary>` 拆分顶层 `GlossaryBlock` 卡片并对 `**<glossary>...</glossary>**` 执行成对剥离，避免破坏行内/列表 Markdown 排版，同步补充 [`frontend/src/index.css`](file:///d:/MeiWenfeng-Classroom/frontend/src/index.css) 亮暗双主题样式。
- **`search_memory` 关键词检索时间戳决胜排序加固 (ISSUE-69)**:
  - 加固 [`backend/services/memory_search_engine.py`](file:///d:/MeiWenfeng-Classroom/backend/services/memory_search_engine.py) `_fetch_target_hits` 的关键词查询排序键，统一在 `id DESC` 之前优先使用标准化时间戳 `_sql_norm_ts() DESC`，避免主键非严格递增或同分场景下早年记录顶替近期记忆。
- **`[Memory]` 多词空格检索、跨源空结果提示与已回滚日记隔离 (Bug #49)**:
  - 在 `backend/services/memory_search_engine.py` 提取 `JOURNAL_VISIBLE_SQL = "COALESCE(status, 'active') NOT IN ('archived', 'rolled_back')"` 统一剔除已归档与已回滚日记；为 `search_memory` 补齐空格分词、SQL `LIKE` 通配符转义及多关键词打分排序；当单侧 `target`（`journals` / `conversations`）查询为空且对端表存在记录时附加跨源提示，并在 `backend/services/tool_engine.py`（`_format_command_str`）显式展示非默认 `target`；
  - 将 `backend/services/response_pipeline.py`（`clean_memory_text`）与 `backend/services/compact_service.py`（`call_llm_for_summary`）的内联推理/状态/工具标签剥离统一收口至 `memory_search_engine.strip_internal_tags` SSOT，并同步更新 `ADR-014` 架构决策。
- **OpenAI 标准 Tool Calls 字符串协议恢复与离线截断单测重构 (Bug #48)**:
  - 废止原 `ISSUE-50` 为迁就旧模板将 `tool_calls` 强转为 Python `dict` 及附加顶层 `arguments` 的临时适配，恢复 `backend/services/agent_executor.py` 为标准 OpenAI Chat Completions JSON 字符串契约（`function.arguments` 恒定输出 `str`，移除顶层 `arguments`），解决第三方 OpenAI 兼容网关在多轮工具回调时返回 HTTP 400 `invalid_json` 的问题；
  - 更新 `backend/tests/test_agent_executor.py` 断言并补充 `dict` 参数归一化回归测试；将 `backend/tests/test_simulation_and_truncation.py` 中早年未 Mock 的 `test_truncation_logic` 改为纯本地 `OpenAILLMClient` Mock 离线验证。
- **KV-Cache 前缀稳态分层、多模态先图后文与 `@file` 边界抽离 (Bug #47)**:
  - 在 `backend/services/context_manager.py` 的 `assemble_messages` 内实施 `<system_injection>` 静先动后分层，将 `<agent_execution_protocol>` 前置并把 `<active_atmosphere_mode>`、`<openclaw_gateway_status>`、`<current_time>` 沉底，同时将 `<current_time>` 精度降为分钟级（`%Y-%m-%d %H:%M`），避免重试或重生成触发前缀缓存失效；
  - 在 `backend/routers/chat.py`（`_order_multimodal_images_first`）与 `context_manager.py`（`_order_images_first`、`_merge_message_contents`、`assemble_messages`）严格规范多模态数组顺序，确保所有 `image_url` 永远位于 `text` 之前；
  - 在 `chat.py`（`_attach_file_into_last_user_msg`）统一收口 `@current_file` 与 `@path` 文件展开，并在 `context_manager.py` 新增 `_extract_file_contents` 将 `<file_content>` 锚定前移至 `</current_session_history>` 之前，防止动态尾部超过 8192 Token 上限；
  - 同步补充 `ADR-009` 架构演进补丁。
- **全链路测试与生产记忆库/ChromaDB 物理隔离与硬熔断守卫 (Bug #46)**:
  - `ChatRequest` 新增 `dry_run` 只读演练参数，`backend/services/response_pipeline.py` 增加持久化熔断守卫（命中 `dry_run` 或生产 DB 下的测试会话前缀时旁路跳过 `memory_logs` 与 ChromaDB 写入）；
  - `backend/services/chroma_client.py` 改为动态解析 `get_chroma_persist_dir()`（支持 `CHROMA_PERSIST_DIR` 覆盖），并新增 `_check_mutation_safety()` 硬阻断 pytest 对生产目录 `DEFAULT_CHROMA_DIR` 的增删改；
  - `backend/tests/conftest.py` 增设 `isolate_chroma_db`（autouse 临时目录重定向）与 `mock_rag_client`，精简对齐 `AGENTS.md` 与 `docs/01_dev_and_test_guide.md` 防污染红线，并同步补充 `ADR-003`、`ADR-005` 架构演进补丁。
- **右侧状态面板加宽与顶部胶囊按钮防挤压 (ISSUE-55 & Bug #41)**:
  - 将 `.right-panel-container` 宽度由 `300px` 提至 `344px` 确立为宽度单一点 (SSOT)，`.right-panel` 改为 `width: 100%`，彻底解决胶囊按钮挤成两行与字词折行问题；
  - 提炼 `pillStyle` 统一按钮内联样式，施加 `whiteSpace: 'nowrap'`、`flexShrink: 0` 与 `lineHeight: 1`，清除多余边距与重叠挤压源。

### Changed
- **斜杠指令分发器策略模式拆分 (Bug #15)**:
  - 在 `backend/services/slash_handler.py` 提炼 `SlashCommandContext`、`CommandStrategy(ABC)` 与 `CommandRegistry`，将原有巨型 `if/elif` 链拆分为 13 个独立策略类与 `DefaultFallbackCommandStrategy` 兜底策略，并通过 `_sse_response` / `_resolve_course_context` 消除重复样板；
  - 新增 `backend/tests/test_slash_handler_registry.py` 验证注册路由、未知指令兜底与策略增删隔离。
- **上下文双层场域隔离与 KV Cache 静态基石前缀加速理顺 (ISSUE-51)**:
  - 明确业务红线：保留 `<current_session_history>`（防 RAG 记忆召回幻觉的认知屏障）与动态 `<current_time>`（作息与好感度演化的时间脉搏）；
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


