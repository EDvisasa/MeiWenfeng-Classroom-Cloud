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
