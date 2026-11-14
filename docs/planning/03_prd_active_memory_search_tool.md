---
id: PLAN-03
title: 智能体自主记忆检索与日记查看工具 (Active Memory Search Tool & Remembering Experience)
status: draft
created: 2026-11-13
domain: project-planning
---

# 智能体自主记忆检索与日记查看工具 (PRD)

> **文档定位**：需求与系统设计规范 (Product Requirements Document & Architecture Specification)  
> **所属规划**：`docs/planning/01_sprint_tasks.md` (`ISSUE-52`, `ISSUE-53`) / `docs/planning/00_project_roadmap.md`  
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

构建并列装**智能体自主记忆探针与日记翻阅工具 (`search_memory`)**，并在前端打造 **`Remembering...` 沉思回想卡片**：

1. **智能体主动式记忆探针 (Active Memory Probe Tool)**：
   将 `search_memory` 作为一级安全工具接入 `TOOL_REGISTRY`。大模型在 `<think>` 阶段推演发现记忆线索不足时，可自主发起精准工具调用，支持指定关键词（`query`）、检索范围（`target`: `journals` / `conversations` / `all`）、时间区间（`date_range`）及返回条数（`limit`）；
2. **混合存储检索引擎 (Hybrid SQLite Storage Engine)**：
   深度直连本地 `classroom.db` 的 `memory_logs`（日记摘要与内容）和 `chat_messages`（无损历史对话记录），执行高效参数化匹配与多维筛选，生成高信噪比、带时间戳的 Markdown 结构化记忆卡；
3. **生动情感质感卡片 (`Remembering...` UI Card)**：
   前端 `ChatPanel.jsx` 的 `ToolBlock` 将 `search_memory` 映射为 `Remembering...`，在执行期间呈现柔和呼吸灯脉冲点，展示检索词与提取到的记忆片段，让用户直观感受到导师正在记忆殿堂中深潜回忆；
4. **安全护栏与标准 OpenAI 工具协议兼容**：
   严格受 `_sanitize_tool_output` 40,000 字符全局上限保护；工具回调参数严格遵循 OpenAI Chat Completions 标准 JSON 字符串契约（`function.arguments` 为 `str`），兼容主流云端与本地推理网关。

---

## 3. User Stories (详尽用户故事清单)

1. **US-01 (精确约定回溯)**: As a learner/user, I want the AI tutor to recall the exact technical decisions, hardware model numbers, or promises made in conversations weeks ago, so that I don't have to repeatedly re-explain historical context.
2. **US-02 (沉浸式回忆感知)**: As a learner/user, I want to see a distinct `Remembering...` status card with an animated breathing indicator when the AI is searching its memory, so that I feel the tutor is genuinely pausing to reflect on our shared history.
3. **US-03 (自主触发深挖)**: As an AI tutor agent, I want an autonomous `search_memory` tool available during my `<think>` phase, so that I can look up past journal logs whenever the pre-retrieved RAG context is insufficient.
4. **US-04 (日记摘要与正文多维检索)**: As an AI tutor agent, I want to query `memory_logs` by keyword and date prefix (e.g. `2026-10`), so that I can quickly review high-level progress summaries and emotional milestones.
5. **US-05 (无损原始对话回查)**: As an AI tutor agent, I want to query `chat_messages` for verbatim past dialogue excerpts, so that I can quote the user's original words with 100% precision.
6. **US-06 (高信噪比防爆返回)**: As a system engineer, I want the memory search output to be concise, deduplicated, and capped (default 5, max 15 items), so that tool results do not bloat the model's active context window.
7. **US-07 (端侧毫秒级查询)**: As a performance engineer, I want the SQLite search query to execute within 50ms, so that the total response prefill time during the agent loop remains negligible.
8. **US-08 (全局安全截断)**: As a system architect, I want `search_memory` output to be governed by `_sanitize_tool_output`, preventing runaway results from triggering HTTP 413 or tokenizer memory overflow.
9. **US-09 (前端交互折叠)**: As a front-end user, I want the `Remembering...` card to support click-to-expand details (IN/OUT), so that I can inspect the exact historical records the AI referenced.
10. **US-10 (双系统角色隔离无缝承接)**: As a roleplay designer, I want the AI tutor to seamlessly transition from internal memory inspection to natural dialogue, answering with appropriate warmth and pedagogical accuracy.
11. **US-11 (标准工具回调兼容)**: As an inference engineer, I want the tool call arguments to strictly follow the OpenAI JSON string contract (`function.arguments` as `str`), ensuring zero HTTP 400 errors across OpenAI-compatible proxies and local inference backends.
12. **US-12 (无结果友好兜底)**: As an AI tutor agent, I want the tool to return a clear notice (e.g. `[No memory records found matching '...']`) instead of throwing an error, so that I can gracefully acknowledge memory gaps without hallucinating.

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
      "query": {
        "type": "string",
        "description": "Keywords, exact phrase, technical terms, or person names to search in past memory records."
      },
      "target": {
        "type": "string",
        "enum": ["all", "journals", "conversations"],
        "description": "Target source: 'journals' (memory_logs summaries and lesson insights), 'conversations' (raw chat_messages), or 'all' (search both). Default is 'all'."
      },
      "date_range": {
        "type": "string",
        "description": "Optional date filter: exact date ('2026-10-15'), month ('2026-10'), or relative ('recent_7d', 'recent_30d')."
      },
      "limit": {
        "type": "integer",
        "description": "Maximum number of records to return. Default is 5, hard ceiling is 15."
      }
    },
    "required": ["query"]
  }
  ```

### 4.2 底层数据检索引擎 (`backend/services/memory_search_engine.py`)
- **Seam**: 下沉为独立的纯函数/服务类 `MemorySearchEngine.search(...)`，负责参数化 SQL 拼装与安全执行；
- **查询范围**:
  - `memory_logs`: `SELECT id, timestamp, level, summary, content FROM memory_logs WHERE status != 'archived' AND (summary LIKE ? OR content LIKE ?)`
  - `chat_messages`: `SELECT id, session_id, role, content, timestamp FROM chat_messages WHERE content LIKE ? AND role IN ('user', 'assistant')`
- **输出格式**:
  ```markdown
  [Memory Retrieval Output for query: 'I2C 上拉电阻' (Target: all, Found: 2)]
  ---
  • 【2026-10-15 20:05 | 日记摘要 #12】
    论述了开漏输出模式下外部上拉电阻的计算，标准模式建议使用 4.7kΩ。
  • 【2026-10-15 20:06 | 对话实录 (用户)】
    "师姐，为什么我们板子上的 I2C 总是通信超时？"
  • 【2026-10-15 20:06 | 对话实录 (导师)】
    "检查一下是不是把 4.7k 焊成了 47k，阻值过大会导致上升沿变缓。"
  ---
  ```

### 4.3 流式解析与工具调度兼容
1. **`stream_parser.py`**:
   - 在 `StreamParser.KNOWN_TOOL_NAMES` 集合中加入 `"search_memory"`；
   - 在 `pattern_direct` 正则表达式中追加 `search_memory`，防止伪 XML 泄漏到流式打字机正文中。
2. **`tool_engine.py`**:
   - 在 `ToolExecutionEngine._format_command_str` 中扩展格式化规则：
     `return f"Remembering: '{t_param.get('query', '')}'"`

### 4.4 前端 UI 状态机与视觉设计 (`ChatPanel.jsx`)
- **Friendly Name 映射**:
  `block.tool_name === 'search_memory' ? 'Remembering...' : ...`
- **状态视觉隐喻**:
  - `running` 状态：状态圆点呈现独特的浅紫色/星光脉冲点（`var(--accent-glow)`），区别于 Bash 的橙色与 Read 的蓝色；
  - `done` 状态：转为柔和绿色，右上角提供折叠下箭头；
  - 折叠面板：默认折叠，展开后在 `IN` 栏显示搜索词与筛选范围，在 `OUT` 栏显示结构化记忆 Markdown。

### 4.5 提示词引导 (`backend/services/prompts.py`)
- 在 `<environment_constraints>` 中增加凝练的纯英文使用指南：
  ```text
  - Memory Search Protocol: If the pre-loaded `<retrieved_past_memory_archives>` lacks exact historical details, or when the user references a specific past conversation ("remember when we discussed X?", "what was that code from last week?"), autonomously invoke `<call_tool name="search_memory"><query>keyword</query></call_tool>`.
  ```

---

## 5. Testing Decisions (测试决策与验收规范)

遵循 **“仅测试外部行为契约与边界，不测试内部 SQL 语法拼接”** 的原则：

| 测试用例设计 | 验证模块 | 断言行为与验收标准 |
| :--- | :--- | :--- |
| **`test_search_memory_tool_schema`** | `agent_tools.py` | 验证 `SearchMemoryTool` 正确注册在 `TOOL_REGISTRY`，其 Schema 符合 OpenAI Tool 格式规范； |
| **`test_search_memory_engine_journal_and_chat`** | `memory_search_engine.py` | 使用 mock SQLite 内存数据库，断言给入精确关键词时能够准确召回 `memory_logs` 与 `chat_messages` 对应记录； |
| **`test_search_memory_date_filter`** | `memory_search_engine.py` | 验证按月份（`2026-10`）或具体日期筛选时，严格排除区间外的数据； |
| **`test_search_memory_empty_and_safety_limit`** | `agent_tools.py` | 验证无匹配结果时返回友好文本 `[No memories found...]`，当 `limit=100` 时强制收敛至 15 条以内； |
| **`test_agent_executor_with_search_memory`** | `agent_executor.py` | 模拟大模型发出 `search_memory` 工具调用，验证工具完整执行并在二次迭代中带回记忆结果； |
| **`test_frontend_remembering_card_render`** | `ChatPanel.test.jsx` | 验证前端在接收到 `search_memory` 事件时将标题正确渲染为 `Remembering...`。 |

---

## 6. Out of Scope (明确非本期范围)

1. **向量嵌入库重构**：不重写 ChromaDB 存储结构或更换嵌入模型，被动向量召回（Layer 1）与主动工具翻阅（Layer 2）互为补充、并存运行；
2. **分布式外部同步**：记忆仅限于本地 `classroom.db` 与当前宿主机，不涉及跨网络设备漫游；
3. **前端全局独立记忆搜索面板**：本次交付重点是**智能体自主调用与聊天流内的动态卡片**，不包含在顶部菜单额外增加独立的全局记忆搜索大弹窗（该功能已由 `DatabaseViewer.jsx` 覆盖）。

---

## 7. Further Notes (演进展望)

本功能上线后，媚吻峰随身课堂将正式迈入 **双层记忆架构（Dual-Tier Memory System）**：
- **Layer 1 (被动潜意识感知)**：ChromaDB 向量相似度在用户发包时秒级注入背景日记；
- **Layer 2 (主动显意识回溯)**：大模型通过 `search_memory` 工具，像人类翻阅笔记一样自主检索细节。这不仅从根本上治愈了长周期伴读过程中的“健忘症”，更为后续演化出多智能体知识溯源与自省总结提供了强有力的基石工具。
