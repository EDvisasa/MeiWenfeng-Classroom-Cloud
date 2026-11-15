---
id: PLAN-03
title: 智能体自主记忆检索与日记查看工具 (Active Memory Search Tool & Remembering Experience)
status: active
created: 2026-11-13
updated: 2026-11-15
domain: project-planning
---

# 智能体自主记忆检索与日记查看工具 (PRD)

> **文档定位**：需求与系统设计规范 (Product Requirements Document & Architecture Specification)  
> **所属规划**：`docs/planning/01_sprint_tasks.md` (v1 已交付: `ISSUE-52`, `ISSUE-53` | v1.1 已交付: `ISSUE-66`, `ISSUE-67`, `ISSUE-68`) / `docs/planning/00_project_roadmap.md`<br>
> **通用语言对齐**：严格遵照 [`docs/GLOSSARY.md`](file:///d:/MeiWenfeng-Classroom/docs/GLOSSARY.md) 的双系统物理隔离铁律，技术底层与工具设计使用现代工程规范。

---

## 1. Problem Statement (问题陈述)

目前媚吻峰随身课堂的长期记忆检索属于**单一的被动前置语义召回（Passive Pre-flight Semantic RAG）**：
1. **精准召回失效（Keyword & Timestamp Blindspot）**：
   在会话发包前，后端仅根据用户最新的一句输入调用 ChromaDB 做向量相似度计算，提取 3-4 条切片和 5 条近期日记摘要。但向量检索在处理**具体代码片段、专用技术术语、特定日期/时间戳、数字约定、久远具体原话**时，存在严重的语义平滑与关键词盲区，核心记忆极易被泛化的相似内容挤占；
2. **信息密度不足与缺乏二次深挖探针（No Active Deep Retrieval）**：
   当预置的记忆切片信息量不足或上下文不全时，大模型在思考（`<think>`）过程中即便察觉到记忆缺失，**没有任何工具可以主动翻看数据库历史**。导致模型要么生成似是而非的幻觉，要么无力地回复“我不记得了”；
3. **交互感知割裂（Lacking Remembering Experience）**：
   在前端用户界面中，用户无法感知 AI 是否在“努力回溯过往记忆”，缺乏类似“沉思翻阅回忆”的生动状态反馈，弱化了伴读导师的拟真陪伴感。

---

## 2. Solution (解决方案)

构建并列装**智能体自主记忆探针与日记翻阅工具 (`search_memory`)**，并在前端打造 **`Remembering...` 回想状态卡片**：

1. **两跳渐进式主动记忆探针 (Two-Hop Bounded Memory Probe)**：
   将 `search_memory` 作为一级安全工具接入 `TOOL_REGISTRY`。大模型发现前置召回线索不足时，按**先浏览索引、再按需展开**的两跳策略调用：
   - **第一跳（索引/时间线浏览：`mode="search" | "timeline"`）**：按关键词、检索范围（`journals` / `conversations` / `all`）或时间区间返回高信噪比短预览（每条 ~150 字干净摘要 + `source_type` / `record_id` / `timestamp`）；
   - **第二跳（精准上下文展开：`mode="expand"`）**：针对命中预览的 `record_id`，按需展开完整日记条目或选中消息前后 `±2~3` 轮完整对话上下文（自动剥离历史 `<think>` 等内部控制标签）。
2. **探索步数硬边界与纯粹工具契约 (Bounded Exploration & Neutral Tool Output)**：
   - **受限探索 Loop**：在 `AgentExecutor`（`max_iterations=5`）内为 `search_memory` 施加单轮最多 **3 次**探索上限（`MAX_MEMORY_SEARCH_STEPS = 3`），防止模型无休止空转；
   - **客观纯事实反馈与人设隔离**：工具本身及 `<environment_constraints>` 仅提供**客观检索参数与纯事实返回**（包含未命中时的客观空状态提示），绝不写入任何台词模板、撒娇提示或情绪引导；角色如何面对“记起/记不起”完全交由既有的 `<character_persona>` 与 `<dynamic_attributes>` 自然流露。
3. **混合存储检索引擎 (Hybrid SQLite Storage Engine)**：
   直连本地 `classroom.db` 的 `memory_logs`（日记摘要与正文）和 `chat_messages`（历史对话实录），执行参数化查询与时间筛选，生成结构化纯客观检索输出。
4. **沉浸式状态卡片 (`Remembering...` UI Card)**：
   前端 `ChatPanel.jsx` 将 `search_memory` 映射为 `Remembering...`，传达“她正在翻阅往昔聊天记录与日记本查看”的日常陪伴氛围；一轮中连续的多次 `search_memory` 探索收敛折叠为单张可展开的 `Remembering...` 卡片，运行态呈现柔和呼吸脉冲点，展开可查看每步 `IN`/`OUT` 检索轨迹。
5. **安全护栏与标准 OpenAI 工具协议兼容**：
   严格受 `_sanitize_tool_output` 40,000 字符全局上限保护；工具回调参数严格遵循 OpenAI Chat Completions 标准 JSON 字符串契约（`function.arguments` 为 `str`），兼容主流云端与本地推理网关。

---

## 3. User Stories (详尽用户故事清单)

1. **US-01 (精确约定回溯)**: As a learner/user, I want the AI tutor to recall exact technical decisions, hardware model numbers, or promises made weeks ago, so that I don't have to repeatedly re-explain historical context.
2. **US-02 (沉浸式回忆感知)**: As a learner/user, I want to see a calm `Remembering...` status card with an animated breathing indicator when the AI is flipping through past chats and diaries, so that I feel the companion is genuinely checking shared history.
3. **US-03 (受控两跳检索)**: As an AI tutor agent, I want to browse concise matching previews (`search`/`timeline`) first and selectively expand only promising entries (`expand`), so that I find exact context cleanly without flooding my context window.
4. **US-04 (探索次数封顶防空转)**: As a system engineer, I want memory exploration per turn to be capped (max 3 calls), so that the agent does not loop endlessly searching for nonexistent memories or waste inference budget.
5. **US-05 (工具与人设边界清晰)**: As a character designer, I want `search_memory` prompts and tool outputs to stay strictly factual and neutral without scripted emotional cues, so that the character reacts organically according to her existing persona and dynamic affection/refractory state.
6. **US-06 (历史清洗防泄露)**: As a system engineer, I want expanded conversation snippets to strip historical `<think>` blocks and internal control tags, so that old reasoning traces do not pollute current turn reasoning.
7. **US-07 (日记摘要与正文多维检索)**: As an AI tutor agent, I want to query `memory_logs` by keyword and date range (e.g. `2026-10` or `recent_7d`), so that I can quickly review high-level milestones and full diary text.
8. **US-08 (无损原始对话回查)**: As an AI tutor agent, I want to locate verbatim user/assistant exchanges in `chat_messages` and inspect `±2` surrounding turns around a hit, so that I understand both what was said and its conversational context.
9. **US-09 (防爆与毫秒级查询)**: As a performance engineer, I want parameterized SQLite queries to return previews within ~50ms, capped at default 5 / hard max 15 items per preview call, and governed by `_sanitize_tool_output` (40,000 chars).
10. **US-10 (连续检索卡片收敛折叠)**: As a front-end user, I want consecutive `search_memory` steps in one turn to collapse into a single clean `Remembering...` card that still expands to show each step's `IN`/`OUT`, avoiding visual clutter.
11. **US-11 (标准工具回调兼容)**: As an inference engineer, I want tool call arguments to strictly follow the OpenAI JSON string contract (`function.arguments` as `str`), ensuring zero HTTP 400 errors across OpenAI-compatible proxies and local inference backends.
12. **US-12 (客观空结果兜底)**: As an AI tutor agent, I want empty queries and budget exhaustion to return clear factual notices instead of errors, so that the model handles memory gaps without hallucination.

---

## 4. Implementation Decisions (实施与技术架构决策)

### 4.1 工具模块与参数规范 (`backend/services/agent_tools.py`)
- **类名**: `SearchMemoryTool(AgentTool)`
- **注册键**: `TOOL_REGISTRY["search_memory"]`
- **安全属性**: `is_safe = True`（纯只读操作，无需 HITL 用户弹窗审批）
- **参数契约 (`parameters_schema`)**:
  ```json
  {
    "type": "object",
    "properties": {
      "mode": {
        "type": "string",
        "enum": ["search", "timeline", "expand"],
        "description": "Operation mode: 'search' (keyword lookup returning concise previews), 'timeline' (browse records in date_range without a keyword), or 'expand' (fetch full diary or surrounding chat turns for a specific hit)."
      },
      "query": {
        "type": "string",
        "description": "Keywords or exact phrase to search (required when mode='search')."
      },
      "target": {
        "type": "string",
        "enum": ["all", "journals", "conversations"],
        "description": "Source filter for search/timeline: 'journals' (memory_logs), 'conversations' (chat_messages), or 'all'. Default is 'all'."
      },
      "date_range": {
        "type": "string",
        "description": "Optional date filter: exact date ('2026-10-15'), month ('2026-10'), or relative ('recent_7d', 'recent_30d')."
      },
      "limit": {
        "type": "integer",
        "description": "Max preview records for search/timeline. Default is 5, hard ceiling is 15."
      },
      "source_type": {
        "type": "string",
        "enum": ["journal", "conversation"],
        "description": "Required when mode='expand': whether record_id refers to 'journal' (memory_logs.id) or 'conversation' (chat_messages.id)."
      },
      "record_id": {
        "type": "integer",
        "description": "Target record ID returned by search/timeline preview (required when mode='expand')."
      },
      "context_turns": {
        "type": "integer",
        "description": "For mode='expand' with source_type='conversation': number of messages before/after record_id within the same session. Default 4 (approx ±2 turns), hard ceiling 8."
      }
    }
  }
  ```

### 4.2 探索次数硬边界 (`backend/services/agent_executor.py`)
- 在 `AgentExecutor.run` 的单轮执行循环（`max_iterations = 5`）内，统计本轮 `search_memory` 累计调用次数（常量 `MAX_MEMORY_SEARCH_STEPS = 3`）；
- 当同一轮用户提问内累计调用达到 3 次后，再触发 `search_memory` 时**跳过数据库查询**，直接向模型返回纯客观系统边界提示：
  `[Memory search limit reached (3/3 calls for this turn). Do not invoke search_memory again; respond directly using the information already available.]`
- 不单独硬编码复杂多状态机，完全复用既有 `AgentExecutor` 循环并确保至少保留迭代余量生成最终回复。

### 4.3 底层数据检索引擎 (`backend/services/memory_search_engine.py`)
- **Seam**: 独立纯服务模块 `MemorySearchEngine`，负责参数化 SQL 查询、控制标签清洗与结构化文本生成：
- **内容清洗规则 (`strip_internal_tags`)**：对 `chat_messages.content` 剥离 `<think>...</think>`、`<monologue>...</monologue>`、`<property_update .../>` 等内部控制标签，避免历史推演思维污染当前轮次上下文；
- **三模式检索行为**：
  1. `mode="search"`：
     - `memory_logs`: `SELECT id, timestamp, level, summary, content FROM memory_logs WHERE status != 'archived' AND (summary LIKE ? OR content LIKE ?)`（附加时间筛选，按 `id DESC`）；
     - `chat_messages`: `SELECT id, session_id, role, content, timestamp FROM chat_messages WHERE content LIKE ? AND role IN ('user', 'assistant')`（附加时间筛选，按 `id DESC`）；
     - 每条返回 ~150 字预览，显式标注 `source_type` 与 `record_id`（及对话 `session_id`），供二次 `expand` 锚定。
  2. `mode="timeline"`：按时间倒序浏览 `date_range` 范围内的 `memory_logs` 与 `chat_messages`（无需 `query`），每条同样输出 ~150 字预览及 ID。
  3. `mode="expand"`：
     - `source_type="journal"`：返回对应 `memory_logs.id` 的完整 `summary` 与 `content`（仅限非 `archived` 记录）；
     - `source_type="conversation"`：按目标 `chat_messages.id` 所属 `session_id`，取出 `[id - context_turns .. id + context_turns]` 区间内按时间正序排列的清洗后对白窗口。
- **纯客观输出示例**:
  ```markdown
  [Memory Search Results | mode: search | query: "I2C 上拉电阻" | target: all | hits: 2]
  - [journal #12 | 2026-10-15 20:05] 论述了开漏输出模式下外部上拉电阻的计算，标准模式建议使用 4.7kΩ……
  - [conversation #341 | session:4 | 2026-10-15 20:06 | user] "为什么我们板子上的 I2C 总是通信超时？……"
  Note: Use mode="expand" with source_type and record_id to inspect full details if needed.
  ```
- **空结果输出**:
  `[No memory records found matching the given criteria.]`

### 4.4 流式解析与工具调度兼容
1. **`stream_parser.py`**:
   - 在 `StreamParser.KNOWN_TOOL_NAMES` 集合中加入 `"search_memory"`；
   - 在 `pattern_direct` 正则表达式中追加 `search_memory`，防止回退伪 XML 泄漏到流式打字机正文中。
2. **`tool_engine.py`**:
   - 在 `ToolExecutionEngine._format_command_str` 中扩展按模式格式化：
     - `expand` -> `f"Remembering detail: {t_param.get('source_type', '')}#{t_param.get('record_id', '')}"`
     - `timeline` -> `f"Remembering timeline: {t_param.get('date_range', 'recent')}"`
     - 默认 `search` -> `f"Remembering: '{t_param.get('query', '')}'"`

### 4.5 前端 UI 状态机与连续折叠 (`frontend/src/components/ChatPanel.jsx`)
- **Friendly Name 映射**:
  `block.tool_name === 'search_memory' ? 'Remembering...' : ...`
- **连续检索收敛分组**：
  当同一条 assistant 消息流中出现相邻的多个 `search_memory` tool block（例如第 1 步 `search`、第 2 步 `expand`），在渲染层合并收敛为**单张 `Remembering...` 卡片**：
  - 任一步仍在 `running` 时卡片保持脉冲呼吸态；全部完成后转为平静完成态；
  - 卡片默认折叠，点击展开后按顺序展示每一步的 `IN` / `OUT` 记录（单次调用与现有 `ToolBlock` 交互完全一致）。
- **状态视觉隐喻**:
  - `running` 状态：柔和脉冲呼吸指示（浅紫色/暖光点，区分于文件读取与命令行执行）；
  - `done` 状态：柔和完成指示与可折叠箭头。

### 4.6 提示词工具说明 (`backend/services/context_manager.py`)
- 在 `get_cross_reference_protocol()`（动态尾部挂载，绝不改动 `static_system_prompt`，保证 KV-Cache 前缀稳定性）中更新两处纯客观工程指引：
  1. 在 `<environment_constraints>` 中追加记忆检索条目（明确区分工具边界：本地课程文件/代码用 `grep_search` / `read_file`，仅历史对话与日记用 `search_memory`，并限定每轮最多 2–3 次探索）：
     ```text
     - MEMORY SEARCH: You have access to `search_memory` strictly for recalling past conversations (`chat_messages`) and diary entries (`memory_logs`) when pre-loaded context lacks exact details (do NOT confuse with `grep_search`/`read_file` for local workspace files). Use `mode="search"` or `"timeline"` for concise previews, then `mode="expand"` only on relevant hits. Limit exploration to at most 2-3 `search_memory` calls per turn; once sufficient context is found or nothing matches, stop searching and answer directly.
     ```
  2. 在 `<execution_framework>` 的 `[PHASE 1: INTERNAL REASONING]` Step 2 (`Tool Selection`) 中补入 `search_memory`，使其进入原生工具决策清单。
- *(约束：严禁在上述协议或工具返回体中添加“若未找到则撒娇/掩饰”等任何表演指示，确保角色反应纯由 `prompts.py` 中的 `<character_persona>` 与 `<dynamic_attributes>` 自主驱动。)*

---

## 5. Testing Decisions (测试决策与验收规范)

遵循 **“仅测试外部行为契约与边界，不测试内部 SQL 语法拼接”** 的原则：

| 测试用例设计 | 验证模块 | 断言行为与验收标准 |
| :--- | :--- | :--- |
| **`test_search_memory_tool_schema`** | `agent_tools.py` | 验证 `SearchMemoryTool` 正确注册在 `TOOL_REGISTRY`，支持 `search`/`timeline`/`expand` 参数 Schema 并符合 OpenAI Tool 格式规范； |
| **`test_search_memory_search_and_timeline`** | `memory_search_engine.py` | 使用隔离 SQLite 库，断言 `search` 返回 ~150 字短摘要（含 `record_id` 与 `source_type`），`timeline` 支持无关键词按日期浏览，且预览自动剥离 `<think>` 等控制标签； |
| **`test_search_memory_expand_journal_and_conversation`** | `memory_search_engine.py` | 验证 `expand` 对 `journal` 返回完整条目，对 `conversation` 返回同会话前后 `±context_turns` 清洗后对话窗口且不跨 `session_id` 越界； |
| **`test_search_memory_empty_and_safety_limit`** | `agent_tools.py` | 验证无匹配结果返回客观文本 `[No memory records found...]`，`limit=100` 时强制收敛至 15 条以内； |
| **`test_agent_executor_memory_search_budget`** | `agent_executor.py` | 模拟模型在一轮内连续发起 >3 次 `search_memory` 调用，断言第 4 次触发硬上限保护（不穿库，返回超限提示并正常收敛生成回答）； |
| **`test_frontend_remembering_card_render_and_group`** | `ChatPanel.test.jsx` | 验证 `search_memory` 渲染为 `Remembering...`，并验证连续多次 `search_memory` 块收敛合并为单张可展开的多步卡片。 |

---

## 6. Out of Scope (明确非本期范围)

1. **向量嵌入库重构**：不重写 ChromaDB 存储结构或更换嵌入模型，被动向量召回（Layer 1）与主动工具翻阅（Layer 2）互为补充、并存运行；
2. **分布式外部同步**：记忆仅限于本地 `classroom.db` 与当前宿主机，不涉及跨网络设备漫游；
3. **前端全局独立记忆搜索面板**：本次交付重点是**智能体自主调用与聊天流内的动态卡片**，不包含在顶部菜单额外增加独立的全局记忆搜索大弹窗（该功能已由 `DatabaseViewer.jsx` 覆盖）。

---

## 7. Further Notes (演进展望)

本功能上线后，媚吻峰随身课堂将正式迈入 **双层记忆架构（Dual-Tier Memory System）**：
- **Layer 1 (被动潜意识感知)**：ChromaDB 向量相似度在用户发包时秒级注入背景日记；
- **Layer 2 (主动显意识回溯)**：大模型通过 `[Memory]` 原子记忆检索工具族，像人类翻阅笔记一样自主检索细节。这不仅从根本上治愈了长周期伴读过程中的“健忘症”，更为后续演化出多智能体知识溯源与自省总结提供了强有力的基石工具。

---

## 8. v1.1 演进迭代规范 (`DONE`: `ISSUE-66` ~ `ISSUE-68`)

> 以下三项已在 2026-11-15 按 TDD 完成实施并通过全栈自动化回归测试，正式替代上文 §4.1 复合 Schema、§4.2 3 次硬上限与 §4.6 旧版规则 8 描述：

### 8.1 解除探索次数硬限制与循环深度适配 (`ISSUE-66`)
- **取消 3 次短路锁**：移除 `AgentExecutor` 中 `MAX_MEMORY_SEARCH_STEPS = 3` 的计数限制，允许单轮跨多个日期、多段对话连续探索（由 `_sanitize_tool_output` 单次 40,000 字符上限与前端停止开关 `stream_controller` 兜底）；
- **放宽执行器循环天花板**：解除 [`backend/services/model_router.py`](file:///d:/MeiWenfeng-Classroom/backend/services/model_router.py#L78) 硬编码的 `max_iterations=5` 对多步记忆检索的提前阻断，并在接近极端防护阈值时优雅收口生成最终回复。

### 8.2 `[Memory]` 四原子工具拆分（方案 A）与渐进式日期/日程检索 (`ISSUE-67`)
针对本地小模型在面对多 `mode` 条件可选参数时易发生“复合格式套用失败”或 XML 回退解析错位的问题，将原单一复合工具 `search_memory` 拆分为 **4 个无 `mode`、带显式 `required` 约束的单职责工具**（底层复用 [`MemorySearchEngine`](file:///d:/MeiWenfeng-Classroom/backend/services/memory_search_engine.py)）：

| 工具名 | 职责 | 必填参数 (`required`) | 可选参数 |
| :--- | :--- | :--- | :--- |
| **`search_memory`** | 关键字全文搜索（返回短摘要 + `#record_id`） | `query` | `target`, `date_range`, `start_date`, `end_date`, `limit` |
| **`get_memory_timeline`** | 按时间范围按序浏览摘要与 `#record_id` | — | `date_range`, `start_date`, `end_date`, `target`, `limit` |
| **`get_memory_calendar`** | 按起止日期汇总每天独立对话段数、会话标题与日记数 | — | `start_date`, `end_date`, `date_range` |
| **`expand_memory`** | 根据 `#record_id` 展开完整日记或同会话上下文对白 | `source_type`, `record_id` | `context_turns` |

- **空日期渐进式客观提示（`memory_search_engine.py`）**：
  - 指定单日 `YYYY-MM-DD` 命中 0 条时，自动附带同月 `YYYY-MM` 存在非归档记录的活跃日期及条数（整月空则退一级返回同年 `YYYY` 活跃月份）；
  - 指定月份 `YYYY-MM` 命中 0 条时，自动附带同年 `YYYY` 活跃月份（全年空则提示全库有记录年份）。
- **流式解析与前端折叠对齐**：
  - `StreamParser`（`KNOWN_TOOL_NAMES` / `_DIRECT_TOOL_REGEX` / `param_map`）与 `ToolExecutionEngine._format_command_str` 全面适配 4 个原子工具；
  - 前端 `ChatPanel.jsx` 通过 `MEMORY_TOOL_NAMES` 集合识别全部 4 个工具为 `'Remembering...'`，同轮连续跨工具翻查仍无缝收敛为单张可展开的多步 `Remembering...` 卡片。

### 8.3 本地小模型四类正交工具标签（12 工具）与高信噪比路由 (`ISSUE-68`)
- **全量 12 工具首词分类打标 + 去表名诱因（`agent_tools.py`）**：
  - 保留原工具 ID，不增加多一轮推理的元工具分层，在全部 12 个注册工具 `description` 最前端注入正交类目标签（`[Memory]` / `[Workspace]` / `[Web]` / `[Collab]`）：
    1. `[Memory]`（4 个记忆原子工具）：清除 `description` 与参数 Schema（`target`）中的 `chat_messages`/`memory_logs` 表名暗示，声明记忆非本地磁盘文件、只能经 `[Memory]` 工具回忆；
    2. `[Workspace]`（`read_file`, `grep_search`, `replace_file_content`, `create_file`, `execute_bash`）：首词 `[Workspace]` 并在读/搜/终端工具末尾附加 <10 词互斥后缀（`Workspace/sandbox only; NEVER for past chats/diaries (use [Memory] tools).`）；
    3. `[Web]`（`web_search`, `read_url_content`）：首词 `[Web]`；
    4. `[Collab]`（`call_openclaw_agent`）：首词 `[Collab]`。
- **规则折叠与 Step 2 去偏置（`context_manager.py`）**：
  - 将 `<environment_constraints>` 散落的第 4/7/8/9 条折叠为 4 行 `TOOL ROUTING` 分类对照表（`[Memory]` 与 `[Workspace]` 贴身置顶互斥）；
  - 重写 `[PHASE 1]` Step 2 `Tool Selection`：删除句首强迫全局检查 `<openclaw_gateway_status>` 的偏置句，改为先 4 选 1 定类、再选原子工具（仅选 `[Collab]` 时核对 OpenClaw 在线状态）。
- **潜意识召回区就地指针**：在 `<retrieved_past_memory_archives>` 与 `<recent_journal_summaries>` 既有 `[CRITICAL ... NOTICE]` 末尾各追加 1 句超短指引（``Partial slices only — if missing details, use `[Memory]` tools (`search_memory`, etc.), not disk files.``），`get_static_system_prompt()` 保持零污染。
