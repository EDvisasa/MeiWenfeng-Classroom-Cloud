---
id: PLAN-BUG
title: 当前缺陷与Bug追踪
status: active
created: 2026-06-27
domain: project-planning
---
# 04 - 当前缺陷与Bug追踪

> **目标**：集中记录当前系统已发现的缺陷（Bugs）及需要修正的项点，便于后续进行调查分析与逐一修复。严禁未经调研盲目修改代码。

## 🔴 待修复 Bug 列表 (Current Bugs)

### 1. 数据目录写入与存储机制异常
- **现象描述**：系统目前对于如何对 `data/` 文件夹进行合法的写入操作、以及如何标准地存储教学文档，缺乏明确的工作流。
- **调查方向**：
  - 需要分析现有的 `AgentExecutor` 与沙盒 (`Sandbox`) 工具流中，如何才能合法向 `data/materials/` 等受保护的目录写入数据。
  - 需要排查后端安全机制（如防注入护栏和路径穿越防御）是否过度拦截了正常的教学文档保存动作。

### 2. [已解决] 前端 `.md` 文件渲染导致白屏崩溃
- **现象描述**：在网页前端的导师状态栏或资源树中，一旦点击 `@data/materials` 目录下的任意 `.md` 文件，不会正常展示文本内容，而是导致整个 React 界面直接变白屏（前端应用崩溃）。
- **调查方向**：
  - 检查前端文件预览组件或 Markdown 渲染组件（如使用了 `react-markdown` 等库）是否存在解析异常或未捕获的渲染错误。
  - 检查后端拉取文件内容的 API（如 `GET /api/files/...`）返回的数据结构是否符合前端预期。
  - 修复前必须先查看浏览器的 Developer Console 报错堆栈以精准定位崩溃点。
- **解决路线**：
  1. 根因定位：在 [ChatPanel.jsx#L706](file:///d:/MeiWenfeng-Classroom/frontend/src/components/ChatPanel.jsx#L706) 处理 `msg.type === 'markdown_doc'` 时，调用了一个在全库中从未定义也未导入的虚构组件 `<ChatBlockParser ... />`，触发 `ReferenceError: ChatBlockParser is not defined` 导致 React 树崩溃。
  2. 代码修复：将其替换为系统标准且高内聚的解析渲染回路 `{renderNormalizedBlocks(parseAndMergeBlocks(msg.content))}`。
  3. 测试验证：在 [ChatPanel.test.jsx](file:///d:/MeiWenfeng-Classroom/frontend/src/components/ChatPanel.test.jsx) 中新增集成测试用例 `TDD 4: renders markdown_doc system_info message without ReferenceError and parses custom cards`，并移除了原先人为简化的 `blockParser` mock 以测试真实解析，全部单元测试与回归测试通过。

### 3. [已解决] 小模型思考链引发正则截断故障（嵌套标签污染）
- **状态更新**：已在前端 `App.jsx` 与 `blockParser.js` 彻底修复。采用“双重隔离屏障”机制：1）在提取独白前强制预先剥离流中尚未闭合或已闭合的 `<think>...</think>` 思考块；2）将提取正则升级为非重叠非贪婪匹配 `/<monologue>((?:(?!<monologue>)[\s\S])*?)(?:<\/monologue>|$)/g`。即便小模型在思考链或正文中打草稿提及 `<monologue>` 标签，绝不会发生跨标签贪婪截断，完美保障 UI 渲染。

### 4. [已解决] 工具执行授权或运行超时后窗口卡死（无法操作）
- **现象描述**：在调用工具（如 Bash）进行授权等待或执行时间超期到头后，当前前端交互窗口处于卡死或无法操作的状态。
- **调查方向**：
  - 排查前端授权弹窗及 WebSocket 接收在请求超时后的状态机重置逻辑。
  - 评估交互优化方案：考虑保留一个醒目的“取消操作 / 强行中断”按钮，或在后台执行超时后自动释放前端 UI 操作锁。
- **状态更新 (2026-07-04)**：通过 TDD [ISSUE-05] 彻底闭环解决：
  1. 前端 `ChatPanel.jsx` 中 `BashApprovalCard` 针对倒计时归零 `timeLeft === 0` 时通过独立 `useEffect` 自动触发 `onReject`；
  2. 前端 `App.jsx` 在处理 SSE 流事件 `tool_end` 时同步执行 `setPendingApproval(null)`，确保工具结束或超时断开时 DOM 卡片被销毁；
  3. 后端 `BashTool` 的授权轮询在超时（默认 60s，支持 `approval_timeout` 动态注入）后自动释放 `PENDING_APPROVALS` 字典锁并返回规范错误提示。前后端与自动化测试已全量绿灯通过。

### 5. [待解决] 单次会话上下文缺乏时序时间戳（时间流逝感知缺失）
- **现象描述**：在单次会话（多轮对话）中，历史消息中没有任何确切的发生时间戳或时间间隔记录。当前系统仅在 [context_manager.py](file:///d:/MeiWenfeng-Classroom/backend/services/context_manager.py) 的尾部三明治注入（Tail Injection）里向最后一条 User 消息追加当前系统时间 `<current_time>`，导致 AI 无法感知历史轮次发生于何年何月几时几分（例如当用户在跨时段对话中提及“早上讨论的那个问题”，AI 失去了时间尺度与时序感知能力）。
- **预期行为**：会话上下文消息在存储与传导至大模型（如 `assemble_messages`）时，每一轮或跨时段的历史对白能附带精简的时序标尺（例如 `[2026-07-05 10:00]`），让 AI 导师在长程对话中拥有准确的时间流逝感和记忆锚点。
- **调查与修复方向**：
  - 排查前端与后端在记录和传递 `messages` 报文数组时，是否已保存 `timestamp` 字段。
  - 在 [context_manager.py](file:///d:/MeiWenfeng-Classroom/backend/services/context_manager.py) 的 `assemble_messages` 组装回路中，对历史对白自动注入精简的时间前缀或跨越时长提示。

## 🏗️ 架构与深模块解耦缺陷 (Architecture Deepening Opportunities)

### 4. [已解决] AgentExecutor 的流解析与工具调度耦合
- **状态更新**：已通过架构重构彻底解耦。抽离出独立的高内聚流式解析适配器 `backend/services/stream_parser.py` (专注于 SSE 流事件切分与 XML 解析) 与独立的工具执行引擎 `backend/services/tool_engine.py` (专注于多工具并发与权限控制)。`AgentExecutor` 仅作为轻量级调度回路，删除了 40 多行冗余旧代码。

### 5. [已解决] Model Router 路由层人设泄漏
- **状态更新**：已在架构解耦重构中彻底解决。网络路由层 `backend/services/model_router.py` 中的 `stream_chat` 函数已移除了长达 30 行的 `perfect_one_shot` 硬编码及所有角色扮演逻辑。该逻辑被收拢迁移至上下文与管线引擎 `backend/services/context_manager.py` 的 `assemble_messages` 方法中进行集中组装。路由层现在只纯粹负责接收并分发完全就绪的报文。

### 6. 斜杠指令 (Slash Commands) 巨石阵结构
- **现象描述**：`slash_handler.py` 内部使用庞大的 `if/elif` 链为每个指令硬塞海量多行 XML 系统指令。难以新增或删除，完全违背删除测试 (Deletion Test)。
- **调查方向**：提炼 `CommandStrategy` 接口，每条指令独立为类，由核心注册器分发。

### 7. [已解决] 长程对话上下文管理与提示词尾部注入 (Tail Injection)
- **状态更新**：已正式抽离并列装高内聚的 `backend/services/context_manager.py` 模块。采用“顶部静态系统预设 (Static Persona) + 尾部三明治动态注入 (Tail Injection)”架构，动态整合 RAG 切片、近期记忆日志与 IDE 状态。同时实现了严格的**分回合工具切断协议 (Turn Separation Protocol)**，在调工具回合静默触发 API 调用不吐独白，彻底解决了长程对话中的格式错乱与 Token 浪费问题。
