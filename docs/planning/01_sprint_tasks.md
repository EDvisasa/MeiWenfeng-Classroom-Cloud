---
id: PLAN-01
title: 当前开发任务
status: active
created: 2026-06-27
domain: project-planning
---
# 当前开发任务 (Sprint Tracker)

> 本文件仅维护当前开发阶段（第三阶段：课堂引擎）的切实可执行的任务清单。完成的任务请及时勾选，全部完成后归档。
> **架构准则提醒**：所有新增任务、功能开发及文档撰写，必须严格遵循 **`docs/00_doc_guidelines.md`** 中的“双系统用词物理隔离法则”（角色台词归角色，教学与技术底座归现代工程用语）以及“ADR 单文件可运行 HTML 规范”。

## [近期里程碑] 架构规范与双系统隔离治理 [已达成]
- [x] **架构文档单文件化与云同步**：完成 `ADR-000` 深度重构，全量内联 Tailwind 与 CSS 变量，确保单文件独立双击可运行并闭环同步至 `D:\MeiWenfeng-Classroom-Cloud\`。
- [x] **双系统物理隔离全栈审计**：彻底清扫代码库底层，修复 `database.py` 中把术语表写为“修仙辞典”以及 `migrate_memory.py` 提示词中把教学问答强制写为“修仙日记/功法”的严重违规，全量通过 74 项后端单元回归测试。

## [前置基建] Agent 底层能力增强 (高优先级)
- [x] **精准修改能力**：实现 `replace_file_content` 工具，使大模型具备精确的代码行替换能力，这是构建闭环判题的基础。已实现具有最高安全级别护栏（os.path.commonpath）防越权的沙盒替换工具（限定在 `data/materials/Sandbox/`）。
- [x] **高可用退避重试**：在网络请求层（API 调用）引入 Exponential Backoff，防止因弱网或限频导致对话中断。
- [x] **多工具并发与安全执行 (HITL)**：实现 `<tool_batch>` 标签体系，支持多任务并发执行。对于危险工具（如 `execute_bash`）引入 Human-in-the-loop (HITL) 人类审核机制。
- [x] **前端交互式审核卡片**：在 `ChatPanel` 增加悬浮的 `BashApprovalCard` 组件，全局拦截危险操作并等待授权。修复了流式输出完毕后的光标幽灵闪烁 Bug。
- [x] **系统护栏与感知**：在系统提示词中注入真实世界动态时间，物理层面阻断大模型在 Bash 中使用 `cat/grep`，强制规范其使用底层专项工具。
- [x] **联网泛搜与深度精读翻页 (Web & Browser)**：实现 `web_search`（DuckDuckGo 泛搜）与 `read_url_content`（网页清洗为 Markdown 并支持 800 行显式向下翻页引导），前端卡片标题已清晰区分。

## [前置基建] 交互式前端组件 (高优先级)
- [x] **解析大模型标记**：在 `ChatPanel.jsx` 与 `blockParser.js` 中，已完整拦截并解析模型返回的 `<quiz>` 等特定标签。
- [x] **渲染交互组件**：已将解析出的题目动态渲染为 `QuizBlock` React 测验组件（支持单选题、对错判断等），供用户直接在聊天气泡中点击作答并无缝回传判题结果。
- [x] **测验提交路由拦截 (System Prompt Re-injection)**：经代码审核（`chat.py:163`），当用户点击测验提交发送 `<submit_quiz_result>` 时，已无缝映射为 `/lesson_continue` 隐式指令，确保了 AI 批改作业时不会遗忘排版与出题护栏。

## [核心开发] 课堂引擎闭环与沙盒演进 (当前冲刺重心)
- [x] **`/set_mission` 长期目标设定**：已打通前端通信通道（`App.jsx` 的 `fetchStatus` 接收 `data.mission`），并在右侧 `StatusPanel` 实现了常驻的全局学习目标状态与拟定期数据锁定遮罩（`isDrafting`）。
- [x] **`/lesson` 授课微课流**：后端 `slash_handler.py` 已深度注入授课指令，严格规范 AI 导师基于当前论题吐出短篇极简理论，并**强制附带一个 `<quiz>` 测验块**供前端渲染。
- [x] **`/submit` 判题反馈流后端逻辑**：已完成基于 Matt Pocock 理念的后端重构：引入“表扬 -> 询问是否迎接下一阶挑战 -> 提取学情洞察存入记忆 -> 调用 `replace_file_content` 演进沙盒”的完整教学与反馈闭环。
### <a id="issue-00"></a>[ISSUE-00] 双向智能体对话管道 (Bi-directional Agent Bridge)
- **Status**: `DONE` (已完成)
- **User Story**: 作为项目工程底座与分布式 AI 网关的连接纽带，建立从课堂后端至 openclaw 网关（白提子）的双向通信管道，规避命令行转义截断与节点安全策略拦截。
- **What to build**: 
  1. 在 `backend/services/openclaw_client.py` 封装基于 WSL 命令行调用的推流模块；
  2. 在 `backend/routers/openclaw.py` 与 `backend/mcp_server.py` 暴露标准 REST 接口与 MCP 工具（支持对话和沙盒读写护栏）。
- **Affected Files**: [`backend/services/openclaw_client.py`](file:///d:/MeiWenfeng-Classroom/backend/services/openclaw_client.py), [`backend/routers/openclaw.py`](file:///d:/MeiWenfeng-Classroom/backend/routers/openclaw.py), [`backend/mcp_server.py`](file:///d:/MeiWenfeng-Classroom/backend/mcp_server.py), [`backend/main.py`](file:///d:/MeiWenfeng-Classroom/backend/main.py)
- **Acceptance Criteria**: 
  1. openclaw 客户端可通过 `send_to_openclaw` 安全异步/同步发起通知；
  2. `/api/openclaw/talk` 与 MCP `talk_to_meiwenfeng` 能够无乱码互通并受沙盒路径护栏保护。
- **Verification Command**: `pytest backend/tests/test_openclaw_bridge.py`

### <a id="issue-17"></a>[ISSUE-17] 智能体自主调度工具接缝 (`call_openclaw_agent`)、动态尾部夹层网关心跳感知 (`<openclaw_gateway_status>`) 与 `SandboxVFS` 深模块
- **Status**: `DONE` (已完成 / TDD 验证通过)
- **User Story**: 作为后端教学导师引擎，我希望在会话发包前于动态尾部夹层 (`tail_injection`) 严格按照 `docs/GLOSSARY.md` 标准工程术语规范实时注入 `<openclaw_gateway_status>ONLINE/OFFLINE</openclaw_gateway_status>`（附带 5 秒 TTL 缓存防卡顿），让大模型吐字前即可感知白提子在线状态；同时提供标准大模型工具 (`call_openclaw_agent`) 与其 3 秒心跳预检护栏；并下沉文件 IO 至 `SandboxVFS` 深模块保障物理防穿透。
- **What to build**:
  1. 在 `backend/services/openclaw_client.py` 新设 `check_openclaw_status(timeout=3, ttl=5)` 秒级心跳检测与缓存；
  2. 在 `backend/services/context_manager.py` 的 `tail_injection` 管线中规范注入 `<openclaw_gateway_status>` 纯净工程标签；
  3. 在 `backend/services/agent_tools.py` 新设 `OpenClawAgentTool`（内嵌预检护栏）并注册至 `TOOL_REGISTRY`；
  4. 提取 `SandboxVFS` 深模块实现沙盒物理防穿透 SSOT。
- **Affected Files**: [`backend/services/openclaw_client.py`](file:///d:/MeiWenfeng-Classroom/backend/services/openclaw_client.py), [`backend/services/context_manager.py`](file:///d:/MeiWenfeng-Classroom/backend/services/context_manager.py), [`backend/services/agent_tools.py`](file:///d:/MeiWenfeng-Classroom/backend/services/agent_tools.py), [`backend/routers/openclaw.py`](file:///d:/MeiWenfeng-Classroom/backend/routers/openclaw.py), [`backend/services/sandbox_vfs.py`](file:///d:/MeiWenfeng-Classroom/backend/services/sandbox_vfs.py)
- **Acceptance Criteria**:
  1. 每次构建发往大模型的动态尾部夹层 (`tail_injection`) 中准确包含规范的 `<openclaw_gateway_status>`；
  2. `check_openclaw_status()` 能够以 3 秒超时探测并在 5 秒 TTL 内返回在线/离线状态；
  3. `call_openclaw_agent` 在遇离线时秒级回退，在线时顺畅发派任务；
  4. `SandboxVFS` 为所有沙盒读写提供统一安全的越权阻断防御。
- **Verification Command**: `pytest backend/tests/test_sandbox_vfs.py backend/tests/test_openclaw_bridge.py backend/tests/test_context_manager.py`

### <a id="issue-01"></a>[ISSUE-01] `/submit` 判题与沙盒演进的前端深度适配
- **Status**: `TODO` (高优先级)
- **User Story**: 作为前端学习用户，当后台 AI 调用 `replace_file_content` 升级练习关卡或更新代码沙盒时，我希望在聊天卡片中清晰看到美观的高亮 Diff 对比与友好的组件命名，而不是晦涩的原始参数。
- **Affected Files**: [`frontend/src/components/ChatPanel.jsx`](file:///d:/MeiWenfeng-Classroom/frontend/src/components/ChatPanel.jsx), `frontend/src/utils/blockParser.js`
- **Acceptance Criteria**: 
  1. `ToolBlock` 正确捕获 `replace_file_content` 并显示为“🛠️ 演进实操沙盒卡片”；
  2. 点击可展开查看 `Before / After` 差异视图。
- **Verification Command**: `cd frontend && npm run test`

### <a id="issue-02"></a>[ISSUE-02] 学习决策记录 (LDR) 引擎打通与闭环写入
- **Status**: `TODO` (高优先级)
- **User Story**: 作为后端教学引擎，当用户提交正确的题目答案或通过交互实操考核时，系统自动提取证据推论 (`evidence`, `implications`) 并持久化存入 `learning_decision_records` 表。
- **Affected Files**: [`backend/services/slash_handler.py`](file:///d:/MeiWenfeng-Classroom/backend/services/slash_handler.py), [`backend/database.py`](file:///d:/MeiWenfeng-Classroom/backend/database.py)
- **Acceptance Criteria**: 
  1. `/submit` 成功通过后，数据库 `learning_decision_records` 插入一条记录；
  2. 若已存在冲突记录，能够正确关联 `superseded_by` 字段。
- **Verification Command**: `pytest backend/tests/test_slash_handler.py`

### <a id="issue-03"></a>[ISSUE-03] ZPD (最近发展区) 动态难度追踪自适应算法
- **Status**: `TODO` (核心待办)
- **User Story**: 作为出题导师系统，我希望在每次执行 `/lesson` 生成题目前，自动检索 `course_progress` 表中的 ZPD 能力指标，动态感知用户的受挫与顿悟曲线以调整下一题难度。
- **Affected Files**: [`backend/services/slash_handler.py`](file:///d:/MeiWenfeng-Classroom/backend/services/slash_handler.py), [`backend/database.py`](file:///d:/MeiWenfeng-Classroom/backend/database.py)
- **Acceptance Criteria**: 
  1. `/lesson` 响应体包含当前 ZPD 难度系数；
  2. 连对两题后系数上升，连错后自动回退降级。
- **Verification Command**: `pytest backend/tests/test_context_manager.py`

### <a id="issue-04"></a>[ISSUE-04] 信源白名单与参考资料强制附加元注释
- **Status**: `TODO` (低优先级)
- **User Story**: 作为平台合规审查机制，当大模型引用外部链接或检索文档回答问题时，强制附带来源元数据注释以保证可溯源。
- **Affected Files**: [`backend/services/context_manager.py`](file:///d:/MeiWenfeng-Classroom/backend/services/context_manager.py)
- **Acceptance Criteria**: 
  1. 返回气泡末尾包含规范的引用徽章标签；
  2. 非白名单链接直接在中间层过滤拦截。
- **Verification Command**: `pytest backend/tests/test_agent_tools.py`

### <a id="issue-05"></a>[ISSUE-05] `ChatPanel` 与 `App` 的超时授权生命周期闭环及缺陷归档
- **Status**: `DONE` (已完成)
- **Parent**: [Bug #4](file:///d:/MeiWenfeng-Classroom/docs/planning/bug-tracker.md#L30-L35)
- **User Story**: 作为用户，当我暂离电脑导致 Bash 授权等待超时后，前端卡片自动静默平滑收起，既不卡死页面，也不在输入框上方残留废弃的置灰小卡片。
- **What to build**: 
  1. 在 `ChatPanel.jsx` 的 `BashApprovalCard` 组件中，当倒计时 `timeLeft === 0` 时，触发重置/销毁卡片逻辑（静默收回）。
  2. 在 `App.jsx` 的流式解析处理逻辑中，当收到 WebSocket 的 `tool_end` 事件时，同步执行 `setPendingApproval(null)`，防止后发到达或超时结束时残留 UI。
  3. 在 `docs/planning/bug-tracker.md` 中将 Bug #4 标记为 `[已解决]`，记录解决路线与测试用例。
- **Affected Files**: [`frontend/src/components/ChatPanel.jsx`](file:///d:/MeiWenfeng-Classroom/frontend/src/components/ChatPanel.jsx), [`frontend/src/App.jsx`](file:///d:/MeiWenfeng-Classroom/frontend/src/App.jsx), [`docs/planning/bug-tracker.md`](file:///d:/MeiWenfeng-Classroom/docs/planning/bug-tracker.md)
- **Acceptance Criteria**: 
  - [x] 当 `BashApprovalCard` 倒计时归零时，卡片平滑销毁且 `pendingApproval` 重置为 `null`。
  - [x] 当收到 `tool_end` 事件时，前端同步清空授权卡片。
  - [x] 聊天输入框和发送按钮始终不被阻塞，用户可以随时打断或发送新指令。
  - [x] `bug-tracker.md` 中 Bug #4 状态准确归档为已解决。
- **Blocked by**: None - can start immediately
- **Verification Command**: `pytest backend/tests/test_agent_tools.py`

### <a id="issue-06"></a>[ISSUE-06] 修复 `ChatPanel` 知识档案预览中的未定义组件白屏崩溃
- **Status**: `DONE` (已完成)
- **Parent**: [Bug #2](file:///d:/MeiWenfeng-Classroom/docs/planning/bug-tracker.md#L20-L25)
- **User Story**: 作为用户，当我点击右侧导师状态栏 `@data/materials` 目录下的 `.md` 文件时，系统必须在聊天面板中安全、美观地将其解析为规范 Markdown 与交互块，而非报 `ReferenceError` 导致整个界面白屏崩溃。
- **What to build**: 
  1. 将 [`ChatPanel.jsx` L706](file:///d:/MeiWenfeng-Classroom/frontend/src/components/ChatPanel.jsx#L706) 替换为全库统一且安全的高内聚块解析与渲染回路 `renderNormalizedBlocks(parseAndMergeBlocks(msg.content))`。
  2. 移除对不存在组件 `ChatBlockParser` 的调用。
  3. 在 [`ChatPanel.test.jsx`](file:///d:/MeiWenfeng-Classroom/frontend/src/components/ChatPanel.test.jsx) 中添加针对 `msg.type === 'markdown_doc'` 渲染不崩溃且正确渲染文本/标签块的自动化测试用例。
- **Affected Files**: [`frontend/src/components/ChatPanel.jsx`](file:///d:/MeiWenfeng-Classroom/frontend/src/components/ChatPanel.jsx), [`frontend/src/components/ChatPanel.test.jsx`](file:///d:/MeiWenfeng-Classroom/frontend/src/components/ChatPanel.test.jsx)
- **Acceptance Criteria**: 
  - [x] 点击 `.md` 文件预览时，系统不再报错 `ReferenceError: ChatBlockParser is not defined`，前端应用无白屏崩溃。
  - [x] 聊天面板中能够正常渲染 `markdown_doc` 卡片，且 Markdown 语法与标签块正常展示。
  - [x] 新增的自动化前端单元测试通过。
- **Blocked by**: None - can start immediately
- **Verification Command**: `cd frontend && npm run test`

### <a id="issue-08"></a>[ISSUE-08] 后端知识档案写入与安全防穿透沙盒锁及 RAG 异步同步
- **Status**: `DONE` (已完成)
- **Parent**: `ADR-008`
- **User Story**: 作为系统后端，提供安全的 `save_material_content(path, content)` 与 `POST /api/chat/materials/save` 接口，支持对 `Lessons/`、`Sandbox/`、`References/`、`LDRs/` 的 `.md` 文件进行保存并防范目录穿透；同时保存成功后触发后台异步任务调用 RAGFlow 向量库同步。
- **What to build**:
  1. 在 `MaterialsManager` 中新增 `save_material_content`，利用 `os.path.abspath` 防穿透锁与 `.md` 后缀拦截非法写入。
  2. 在 `course.py` 中新增 `POST /api/chat/materials/save` 路由，保存落盘后立即返回 200 OK，并借助后台任务触发 `rag_client.sync_knowledge`。
- **Affected Files**: [`backend/services/materials_manager.py`](file:///d:/MeiWenfeng-Classroom/backend/services/materials_manager.py), [`backend/routers/course.py`](file:///d:/MeiWenfeng-Classroom/backend/routers/course.py)
- **Acceptance Criteria**:
  1. `save_material_content` 能够成功写入合法路径的 `.md` 文件；
  2. 针对非 `.md` 后缀或企图通过 `../` 穿越跳出 `materials` 目录的请求，强行抛出 ValueError / 403 拒绝；
  3. 接口在写入盘后迅速返回 HTTP 200 OK，并通过异步后台调用 `rag_client.sync_knowledge`。
- **Blocked by**: None - can start immediately
- **Verification Command**: `pytest backend/tests/test_materials_save.py`

### <a id="issue-09"></a>[ISSUE-09] 前端知识档案全局 `PreviewEditModal` 弹窗与会话流解耦
- **Status**: `DONE` (已完成)
- **Parent**: `ADR-008`
- **User Story**: 作为学习用户，当我点击右侧文件树或教材引用链接时，系统直接弹出全局居中的 `PreviewEditModal` 浮层，支持在“📖效果预览”与“✏️源码编辑”两态中无缝切换，彻底取消把 markdown 嵌入对话历史流的做法。
- **What to build**:
  1. 创建 `frontend/src/components/PreviewEditModal.jsx`，支持双态切换、卡片解析预览与代码框编辑保存。
  2. 改造 `App.jsx` 的 `onFileClick`，改为触发模态状态 `setPreviewModal`，不再向 `messages` 插入 `markdown_doc` 元素。
- **Affected Files**: [`frontend/src/App.jsx`](file:///d:/MeiWenfeng-Classroom/frontend/src/App.jsx), [`frontend/src/components/PreviewEditModal.jsx`](file:///d:/MeiWenfeng-Classroom/frontend/src/components/PreviewEditModal.jsx), [`frontend/src/components/ChatPanel.jsx`](file:///d:/MeiWenfeng-Classroom/frontend/src/components/ChatPanel.jsx)
- **Acceptance Criteria**:
  1. 点击文件树触发全局 Modal 打开，且 `messages` 数组不会被插入任何 `markdown_doc` 元素；
  2. 在 Modal 的编辑态修改文本并点击保存，发起到 `POST /api/chat/materials/save` 的请求并在成功后更新本地视图。
- **Blocked by**: [ISSUE-08]
- **Verification Command**: `cd frontend && npm run test`

### <a id="issue-10"></a>[ISSUE-10] 上下文管理深模块重构与报文洗净边界建立
- **Status**: `DONE` (已完成 / 2026-07-05)
- **Parent**: `ADR-009` (架构深模块解耦) / `Bug #6`
- **User Story**: 作为系统引擎，通过引入结构化数据契约 (`ContextBundle`) 废除 `=== [DYNAMIC_BOUNDARY] ===` 字符串切割魔法；在 `assemble_messages` 入口建立白名单洗净边界彻底过滤 `system_info` 等 UI 专用报文（解决 Bug #6）；并将 20 行 One-Shot 模板抽离归位至 `prompts.py`，实施标准化三步组装管线，实现高局部性 (Locality) 与“接口即测试表面 (The interface is the test surface)”。
- **What to build**:
  1. 引入 `ContextBundle` 结构化契约，重构 `build_base_system_prompt` 返回值与接口接缝。
  2. 在 `assemble_messages` 入口增加白名单 `{"user", "assistant", "system"}` 报文过滤，彻底拦截 `system_info`。
  3. 将 `perfect_one_shot` 下沉归位至 `prompts.py`，在 `context_manager.py` 实现①洗净与时序、②动态示教、③尾部夹层三步管线编排。
- **Affected Files**: [`backend/services/context_manager.py`](file:///d:/MeiWenfeng-Classroom/backend/services/context_manager.py), [`backend/services/prompts.py`](file:///d:/MeiWenfeng-Classroom/backend/services/prompts.py), [`backend/routers/chat.py`](file:///d:/MeiWenfeng-Classroom/backend/routers/chat.py), [`backend/tests/test_context_manager.py`](file:///d:/MeiWenfeng-Classroom/backend/tests/test_context_manager.py)
- **Acceptance Criteria**:
  1. `assemble_messages` 能够成功拦截并过滤掉 `role == 'system_info'` 等 UI 卡片报文（彻底解决 Bug #6）；
  2. 废除魔法字符串切割，`ContextBundle` 强类型传递静态人设、动态尾部、RAG 知识与近期记忆；
  3. 提示词解耦与三步管线重构后，全量单测绿灯通过，发往大模型的上下文报文 100% 保持结构化纯密。
- **Blocked by**: None - can start immediately
- **Verification Command**: `pytest backend/tests/test_context_manager.py`

### <a id="issue-11"></a>[ISSUE-11] 尾部动态夹层 O(1) 边界断言优化与反向扫描废除
- **Status**: `DONE` (已完成 - 2026-07-05)
- **Parent**: [Bug #12](file:///d:/MeiWenfeng-Classroom/docs/planning/bug-tracker.md#L108-L115) / `ADR-009`
- **User Story**: 作为大模型会话上下文引擎，当在 `assemble_messages` 中执行尾部动态夹层（当前系统时间 `<current_time>` 与底层防错协议）注入时，系统必须通过 O(1) 常数时间边界断言直接操作列表物理最末尾 `[-1]`，彻底废除往回倒序扫描历史 `user` 的循环，既保障对历史对白的绝对零污染与视觉割裂防护，又将组装核心逻辑极简收敛为 4 行清晰代码。
- **What to build**:
  1. 在 `backend/services/context_manager.py` 的 `assemble_messages` 中，删去旧版 11 行倒序 `for` 循环与 `injected` 状态变量。
  2. 落地极简 O(1) 边界条件：
     ```python
     if formatted_messages and formatted_messages[-1]["role"] == "user":
         formatted_messages[-1]["content"] += tail_injection
     else:
         formatted_messages.append({"role": "user", "content": "[下一轮提问等待中 / Waiting for next prompt]" + tail_injection})
     ```
- **Affected Files**: [`backend/services/context_manager.py`](file:///d:/MeiWenfeng-Classroom/backend/services/context_manager.py)
- **Acceptance Criteria**:
  1. 彻底移除倒序查找历史 `user` 的循环与冗余状态变量，时间复杂度从最坏 O(N) 降为 O(1)。
  2. 严格遵循会话三层物理契约：当列表中最后一条消息刚好为 `user` 时，尾部夹层追加于该消息；当最后一条为 `assistant` 待机或仅有 `system` 时，自动追加标准待机容器。
  3. 全量 12 项后端单测无需修改任何断言，100% 绿灯通过。
- **Blocked by**: None - can start immediately
- **Verification Command**: `pytest backend/tests/test_context_manager.py backend/tests/test_rag_retrieval.py`

### <a id="issue-18"></a>[ISSUE-18] 跨智能体调用返回值精简与动态工具轨迹结果打标摘要保留 (Compact Response & Outcome-Tagged Execution Trace)
- **Status**: `DONE` (已完成 - 通过 12 项单测回归验证)
- **Parent**: `ADR-000` / `ISSUE-17`
- **User Story**: 作为大模型协作底座，当调用 `call_openclaw_agent` 与 OpenClaw 网关节点通信完毕后，返回值既不能把数万字的静态工具 Schema 与提示词遥测噪声塞入上下文窗口导致 Token 剧增，同时又应当为主智能体保留 OpenClaw 内部执行过程中的**带统一结果状态打标的动态运行轨迹摘要（Outcome-Tagged Execution Trace）**，实现高透明度、结果明确与极低 Token 消耗的兼顾。
- **What to build**:
  1. 彻底过滤并丢弃 OpenClaw 返回体中的静态 `meta.tools`（38 种内部 Schema）与 `meta.systemPromptReport`（全量系统提示词哈希与声明文件报表）；
  2. 提取有效回复正文 `result.payloads[].text`；
  3. 解析提取 OpenClaw 运行记录中的动态执行轨迹并进行统一格式的结果打标摘要（例如：`exec(...) [PASS]` / `search(...) [Hit: N]` / `read(...) [OK]`）；
  4. 构建紧凑高效的标准结构化输出头：
     ```text
     [OpenClaw Agent 'main' Response | runId: <id> | duration: <ms>ms]
     [Execution Trace: <带结果状态打标的中间工具链摘要, 若纯文本对话则显示 None (Pure reasoning)>]
     
     <payloads_text>
     ```
- **Affected Files**: [`backend/services/agent_tools.py`](file:///d:/MeiWenfeng-Classroom/backend/services/agent_tools.py)
- **Acceptance Criteria**:
  - [x] 返回报文中绝对不包含任何静态 Schema 字样与系统提示词冗余报告，Token 从 ~20000 压降至数百量级；
  - [x] 返回报文头部清晰呈现 `runId`、耗时 `durationMs` 及带统一结果打标的执行轨迹摘要；
  - [x] 自动化单测完整覆盖轨迹保留、结果打标与静态噪声筛除逻辑。
- **Blocked by**: None - can start immediately
- **Verification Command**: `pytest backend/tests/test_openclaw_bridge.py -v`

### <a id="issue-19"></a>[ISSUE-19] 上下文组装末句反转优化：环境协议前置与最新提问物理压轴 (Tail Injection Inversion for Recency Attention)
- **Status**: `DONE` (已完成 - 经 TDD 12 项单测验证通过)
- **Parent**: `ADR-009` / `ISSUE-11`
- **User Story**: 作为报文组装模块，在将最后的动态尾部夹层（RAG 知识、近期日记、当前时间与系统规约）拼装到最后一条 `user` 报文中时，如果将其直接追加到用户文字后方，会造成小模型“注意力近因效应（Recency Bias）”稀释并遗忘真正的用户提问；通过将尾部夹层前置注入、用户真实指令物理压轴的【增强版方案 B】，在不改变任何前缀 KV 缓存命中的前提下，显著提升小模型遵循用户指令的准确率。
- **What to build**:
  1. 在 `backend/services/context_manager.py` 的 `assemble_messages()` 中重构末尾拼接次序；
  2. 当最后一条报文为 `user` 时，将其重新排列为 `f"{tail_injection}\n\n---\n{original_user_content}"`；
  3. 当最后一条非 `user` 报文时，构造标准待机语句压轴于最后：`f"{tail_injection}\n\n---\n[下一轮提问等待中 / Waiting for next prompt]"`；
  4. 确保物理报文最末段落在任何场景下均为最终指令或会话状态锚点。
- **Affected Files**: [`backend/services/context_manager.py`](file:///d:/MeiWenfeng-Classroom/backend/services/context_manager.py)
- **Acceptance Criteria**:
  - [x] 发往大模型的末条 `user` 报文中，动态系统夹层位于上方，用户输入位于最末尾；
  - [x] 全部后端上下文管理相关自动化测试无需改动核心断言或能通过结构化校验 100% 绿灯；
  - [x] KV 缓存命中边界（静态前缀 + 历史轮次）保持绝对无损。
- **Blocked by**: None - can start immediately
- **Verification Command**: `pytest backend/tests/test_context_manager.py -v`

### <a id="issue-20"></a>[ISSUE-20] 动态尾部夹层与最新提问衔接处增加上下文管线过渡指引 (Context Pipeline Transition Directive)
- **Status**: `DONE` (已完成 - 经 TDD 13 项单测验证通过)
- **Parent**: `ISSUE-19`
- **User Story**: 依据提示词工程规范，区分开发者架构领域术语与 AI 提示语；在动态尾部夹层（Dynamic Tail Injection）前置到最后一条 `user` 消息上方后，在与真实提问交界处增设干净、符合角色认知习惯的 AI 引导提示（System Directive），避免向 AI 泄漏“上下文管线”等开发者后端词汇。
- **What to build**:
  1. 在 `backend/services/context_manager.py` 的 `assemble_messages()` 尾部组装区域新增自然语言过渡衔接引导；
  2. 格式为：`"[系统引导 / System Directive: 请依照上述系统规约与参考背景，严格按角色设定对下方用户的最新对话或指令进行回复。]\n\n"`
  3. 放置于 `---\n` 之后、用户原始指令或待机卡片文字之前。
- **Affected Files**: [`backend/services/context_manager.py`](file:///d:/MeiWenfeng-Classroom/backend/services/context_manager.py)
- **Acceptance Criteria**:
  - [x] `assemble_messages` 生成的最末尾 `user` 报文中，包含干净无技术黑话泄漏的 `System Directive` 过渡行；
  - [x] 过渡指引必须严格介于 `<system_injection>` 下方与真实用户提问文字上方；
- **Blocked by**: None - can start immediately
- **Verification Command**: `pytest backend/tests/test_context_manager.py -v`

### <a id="issue-21"></a>[ISSUE-21] 系统引导句纯英文凝练化改造与提示词编排铁律升格入 GLOSSARY (Pure English System Directive & Glossary Elevation)
- **Status**: `DONE` (已完成 - 经 TDD 13 项单测验证通过)
- **Parent**: `ISSUE-20`
- **User Story**: 依照 `docs/01_dev_and_test_guide.md` 中对于“非人设系统指令英文凝练原则 (Concise English for System Instructions)”的要求，将 `assemble_messages` 中衔接动态夹层与真实用户提问的过渡句完全改写为纯英文；同时将三大提示词编排铁律正式升格写入 `docs/GLOSSARY.md` 作为全局单一点权威准则。
- **What to build**:
  1. 在 `backend/services/context_manager.py` 将 transition directive 改造为纯英文：`"[System Directive: Strictly follow the system rules and context above when responding to the user's latest dialogue below.]"`；
  2. 在 `backend/tests/test_context_manager.py` 中同步更新对应单测断言；
  3. 在 `docs/GLOSSARY.md` 第四章节增加“提示词与报文编排三大铁律（Prompt & Context Iron Laws）”。
- **Affected Files**:
  - [`backend/services/context_manager.py`](file:///d:/MeiWenfeng-Classroom/backend/services/context_manager.py)
  - [`backend/tests/test_context_manager.py`](file:///d:/MeiWenfeng-Classroom/backend/tests/test_context_manager.py)
  - [`docs/GLOSSARY.md`](file:///d:/MeiWenfeng-Classroom/docs/GLOSSARY.md)
- **Acceptance Criteria**:
  - [x] `assemble_messages` 注入的过渡句为 100% 纯英文系统引导，零中文元指令；
  - [x] `docs/GLOSSARY.md` 包含零污染铁律、效率铁律与免责保护框铁律；
  - [x] 单测 `test_assemble_messages_context_pipeline_transition_directive_issue_20` 及全部套件 100% 通过。
- **Blocked by**: None - can start immediately
- **Verification Command**: `pytest backend/tests/test_context_manager.py -v`

### <a id="issue-22"></a>[ISSUE-22] 工具调用反伪 XML 标签幻觉与混合发声防线强化 (Anti-XML Tool Hallucination & Mixed Dialogue Defense)
- **Status**: `DONE` (已完成 - 经 TDD 13 项回归单测全通过)
- **Parent**: `ISSUE-21`
- **User Story**: 针对大模型将原生函数调用（`call_openclaw_agent`）幻觉为文本 XML 标签并在同段混搭对白的问题，根据首位注意力权重法则及凝练英文系统指令准则，在 `<environment_constraints>` 第 1 条顶格规则中显式切断“伪 XML 标签输出”与“混合发声”。
- **What to build**:
  1. 优化 `backend/services/context_manager.py` 的 `get_cross_reference_protocol()` 第 1 条规则：`1. You have native function calling tools via the API. Do NOT hallucinate tool results or pseudo-XML tags (<call_openclaw_agent>...), and never mix character dialogue when calling a tool.`；
  2. 在 `backend/tests/test_context_manager.py` 的 `test_get_cross_reference_protocol_structure` 中增加对应断言；
  3. 在 `docs/planning/bug-tracker.md` 中登记第 17 项 Bug 解决记录。
- **Affected Files**:
  - [`backend/services/context_manager.py`](file:///d:/MeiWenfeng-Classroom/backend/services/context_manager.py)
  - [`backend/tests/test_context_manager.py`](file:///d:/MeiWenfeng-Classroom/backend/tests/test_context_manager.py)
  - [`docs/planning/bug-tracker.md`](file:///d:/MeiWenfeng-Classroom/docs/planning/bug-tracker.md)
- **Acceptance Criteria**:
  - [x] 系统提示词顶部第 1 条显式禁止输出伪 XML 工具标签和同段聊天对白；
  - [x] 单元测试 `test_get_cross_reference_protocol_structure` 及全部 13 个测试通过。
- **Blocked by**: None - can start immediately
- **Verification Command**: `pytest backend/tests/test_context_manager.py -v`

### <a id="issue-23"></a>[ISSUE-23] RAG记忆召回与实时对话区隔标注与尾部防幻觉强化 (RAG Memory & Active Dialogue Demarcation Defense)
- **Status**: `DONE` (已完成 - 经 TDD 13 项单测验证 100% 通过)
- **Parent**: `ISSUE-22`
- **User Story**: 针对模型因读取 RAG 检索结果中的“对话记录”旧切片而误以为是用户当前实时指令的问题，遵循 `GLOSSARY.md` 中的零污染铁律与效率铁律，对记忆召回区加装防伪大写英文警告，并在最后一轮将最新指令精准包裹于 `<current_user_instruction>` 内。
- **What to build**:
  1. 在 `backend/services/context_manager.py` 的 `_build_dynamic_tail_injection` 中对 RAG 和近期日记外包 `<retrieved_past_memory_archives>` / `<recent_journal_summaries>` 标签及大写防伪通知；
  2. 升级 `assemble_messages` 的过渡引导句 `directive` 为防记忆幻觉指引，且将用户当轮指令严格包裹于 `<current_user_instruction>`；
  3. 更新 `backend/tests/test_context_manager.py` 中的回归单测断言。
- **Affected Files**:
  - [`backend/services/context_manager.py`](file:///d:/MeiWenfeng-Classroom/backend/services/context_manager.py)
  - [`backend/tests/test_context_manager.py`](file:///d:/MeiWenfeng-Classroom/backend/tests/test_context_manager.py)
  - [`docs/planning/bug-tracker.md`](file:///d:/MeiWenfeng-Classroom/docs/planning/bug-tracker.md)
- **Acceptance Criteria**:
  - [x] RAG 和近期日记拥有独立标签和纯英文显式历史归属警告；
  - [x] 用户的实时最新指令被 `<current_user_instruction>` 物理隔离和包裹；
  - [x] 全部 13 项单测在 TDD 回归下绿灯通过 (`pytest -v`)。
- **Blocked by**: None - can start immediately
- **Verification Command**: `pytest backend/tests/test_context_manager.py -v`



