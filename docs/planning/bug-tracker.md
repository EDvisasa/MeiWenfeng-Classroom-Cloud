---
id: PLAN-BUG
title: 当前缺陷与Bug追踪
status: active
created: 2026-06-27
domain: project-planning
---
# 04 - 当前缺陷与Bug追踪

> **目标**：集中记录当前系统已发现的缺陷（Bugs）及需要修正的项点，便于后续进行调查分析与逐一修复。严禁未经调研盲目修改代码。

## 🔴 当前处理中：待修复 Bug 与架构重构工单 (Active Issues & Refactorings)

### 1. 数据目录写入与存储机制异常
- **现象描述**：系统目前对于如何对 `data/` 文件夹进行合法的写入操作、以及如何标准地存储教学文档，缺乏明确的工作流。
- **调查方向**：
  - 需要分析现有的 `AgentExecutor` 与沙盒 (`Sandbox`) 工具流中，如何才能合法向 `data/materials/` 等受保护的目录写入数据。
  - 需要排查后端安全机制（如防注入护栏和路径穿越防御）是否过度拦截了正常的教学文档保存动作。

### 15. [待重构] 斜杠指令 (Slash Commands) 巨石阵结构
- **现象描述**：`slash_handler.py` 内部使用庞大的 `if/elif` 链为每个指令硬塞海量多行 XML 系统指令。难以新增或删除，完全违背删除测试 (Deletion Test)。
- **调查方向**：提炼 `CommandStrategy` 接口，每条指令独立为类，由核心注册器分发。

## 🟢 已闭环归档：Bug 与架构重构成果 (Resolved Archive)

### 16. [已解决] 启动脚本 `start.bat` 清理僵尸进程时提示 `'netstat' 不是内部或外部命令`
- **现象描述**：执行 `start.bat` 启动应用行进至 `Cleaning up potential zombie processes...` 阶段时，终端连续抛出 3 次 `'netstat' 不是内部或外部命令，也不是可运行的程序或批处理文件。` 导致端口检查与僵尸清理命令失效。
- **根因分析**：当命令行会话环境变量 `PATH` 丢失 `C:\Windows\System32` 系统目录时，直接调用的简写 `netstat` 与 `taskkill` 无法在 PATH 中寻址。
- **闭环修复**：在 `start.bat` 第 46~57 行将命令调用全部升级为绝对路径常量 `%SystemRoot%\System32\netstat.exe` 与 `%SystemRoot%\System32\taskkill.exe`，不依赖当前终端环境变量 PATH，保障任何终端环境下均可稳定执行。

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

### 5. [已解决] 单次会话上下文缺乏时序时间戳（时间流逝感知缺失）
- **现象描述**：在单次会话（多轮对话）中，历史消息中没有任何确切的发生时间戳或时间间隔记录。当前系统仅在 [context_manager.py](file:///d:/MeiWenfeng-Classroom/backend/services/context_manager.py) 的尾部三明治注入（Tail Injection）里向最后一条 User 消息追加当前系统时间 `<current_time>`，导致 AI 无法感知历史轮次发生于何年何月几时几分（例如当用户在跨时段对话中提及“早上讨论的那个问题”，AI 失去了时间尺度与时序感知能力）。
- **预期行为**：会话上下文消息在存储与传导至大模型（如 `assemble_messages`）时，每一轮或跨时段的历史对白能附带精简的时序标尺（例如 `[2026-07-05 10:00]`），让 AI 导师在长程对话中拥有准确的时间流逝感和记忆锚点。
- **调查与修复方向**：
  - 排查前端与后端在记录和传递 `messages` 报文数组时，是否已保存 `timestamp` 字段。
  - 在 [context_manager.py](file:///d:/MeiWenfeng-Classroom/backend/services/context_manager.py) 的 `assemble_messages` 组装回路中，对历史对白自动注入精简的时间前缀或跨越时长提示。
- **解决路线**：
  1. 报文全链路透传：排查发现前端及后端 SQLite 均已完整保存 `timestamp`，但在 [chat.py](file:///d:/MeiWenfeng-Classroom/backend/routers/chat.py) 的 `send_message` 和 `get_system_context` 进行报文转换时将 `timestamp` 字段剥离。修复为在转换及洗净回路中完整透传 `timestamp`。
  2. 智能时序标尺注入：在 [context_manager.py](file:///d:/MeiWenfeng-Classroom/backend/services/context_manager.py) 的 `assemble_messages` 中，对所有附带合法时间戳的对白自动将其格式化并前置注入 `[YYYY-MM-DD HH:MM] ` 精简标尺（同时兼顾防重复注入幂等性）。
  3. TDD 闭环验证：在 [test_context_manager.py](file:///d:/MeiWenfeng-Classroom/backend/tests/test_context_manager.py) 新增单测 `test_assemble_messages_injects_timestamp`，全量测试绿灯通过。

### 6. [已解决] 前端 UI 提示消息 `system_info` 泄露进入大模型组装上下文
- **现象描述**：在“查看完整系统提示词”预览或实际发送聊天报文时，系统提示词或对白末尾会出现类似 `🔍 成功检索并加载：1 个讲义片段...` 等成功检索提示文本。这是因为前端为了在界面展示 UI 提示卡片，将 SSE 传回的 `system_hint` 存入了 `messages` 数组（标记为 `role: 'system_info'`）；而在请求后端 `/api/chat/system_context` 或 `/send` 时，后端 `assemble_messages` 组装回路未对 `system_info` 这种非标准 LLM 对白角色进行过滤，导致 UI 提示卡片作为消息报文泄露到了提示词及 LLM 上下文中。
- **预期行为**：`assemble_messages` 及报文清洗回路应当严格过滤掉 `role == 'system_info'` 等专供前端 UI 渲染的非对白报文，仅将合法的 `user`、`assistant` 及 `system` 消息传导至大模型和提示词预览。
- **调查与修复方向**：
  - 在 [context_manager.py](file:///d:/MeiWenfeng-Classroom/backend/services/context_manager.py) 的 `assemble_messages` 遍历回路中，增加对 `msg["role"] == "system_info"` 或非 `user`/`assistant` 历史消息的忽略与剥离逻辑。
- **解决路线**：
  1. 建立洗净边界（Sanitization Seam）：在 [context_manager.py](file:///d:/MeiWenfeng-Classroom/backend/services/context_manager.py) 的 `assemble_messages` 入口处建立严格的合法 LLM 角色白名单 `{"user", "assistant", "system"}`，任何不属于白名单的 UI 专用提示报文（如 `system_info`）在进入管线前均被拦截并过滤。
  2. 结构化契约升级（Deep Module）：废除了 `=== [DYNAMIC_BOUNDARY] ===` 字符串拼接切割，引入强类型 `ContextBundle` 数据契约，并在 `assemble_messages` 中构建了洗净时序、动态示教、尾部夹层三步标准管线；同步将 `perfect_one_shot` 下沉解耦至 [prompts.py](file:///d:/MeiWenfeng-Classroom/backend/services/prompts.py)。
  3. TDD 闭环验证：在 [test_context_manager.py](file:///d:/MeiWenfeng-Classroom/backend/tests/test_context_manager.py) 中新增单测 `test_assemble_messages_filters_system_info_bug_6` 与 `test_context_bundle_contract_and_three_step_pipeline`，回归测试全量绿灯通过。

### 7. [已解决] 空占位符消息被注入时间戳导致末尾出现突兀的时间戳报文
- **现象描述**：用户在聊天框发送消息瞬间，前端会为了展示流式打字机动画而在 `messages` 数组最底端 push 一个内容为空的占位符 `{ role: 'assistant', content: '', streaming: true }`；与此同时，依赖 `messages.length` 的 `useEffect` 触发 `/api/chat/system_context` 刷新预设预览。后端 `assemble_messages` 收到此空内容占位消息时，直接把空字符串拼上了时间戳前缀，导致右上角提示词预览末尾出现类似 `[ASSISTANT] [2026-07-05 04:18]` 的突兀残留。
- **解决路线**：
  1. 空内容拦截防御：在 [context_manager.py](file:///d:/MeiWenfeng-Classroom/backend/services/context_manager.py) 的 `assemble_messages` 中增加判断 `if not content.strip() and role == "assistant": continue`，对前端等待响应的空占位符静默跳过。
  2. TDD 闭环验证：在 [test_context_manager.py](file:///d:/MeiWenfeng-Classroom/backend/tests/test_context_manager.py) 中新增回归单测 `test_assemble_messages_ignores_empty_assistant_placeholder_bug_7`，验证空 assistant 消息不再生成任何报文，全量回归绿灯。

### 8. [已解决] 流式输出生成完毕后右上角提示词预览未同步刷新最后一轮 AI 回答
- **现象描述**：在大模型流式回答完毕后，右上角的“查看完整系统提示词”预览和 Token 统计依然停留在用户刚发出消息瞬间的状态，没有把 AI 最新生成的一整段回答同步显现出来。根因是 [ChatPanel.jsx](file:///d:/MeiWenfeng-Classroom/frontend/src/components/ChatPanel.jsx) 中调用 `/api/chat/system_context` 的 `useEffect` 依赖项只监听了 `messages.length`，但在流式生成过程中直至完毕，数组长度 `length` 并未变化，导致生成结束后没有触发重新拉取。
- **解决路线**：
  1. 依赖项同步闭环：在 [ChatPanel.jsx](file:///d:/MeiWenfeng-Classroom/frontend/src/components/ChatPanel.jsx) 的 `fetchSystemTokens` 钩子依赖项数组中将 `isStreaming` 状态加入监听。当流式生成完毕（`isStreaming` 从 `true` 切换为 `false`）瞬间，自动静默触发重新拉取并更新预览与 Token 统计。
  2. TDD 闭环验证：在 [ChatPanel.test.jsx](file:///d:/MeiWenfeng-Classroom/frontend/src/components/ChatPanel.test.jsx) 中新增回归单测 `TDD 5 [Bug #8]: triggers system_context fetch when isStreaming changes from true to false`，验证 `isStreaming` 切换能触发 `fetch` 调用，全量回归绿灯。

### 9. [已解决] 提示词预览中 AI 对白误增时间戳及预览弹窗显示滞后（上下文排版错乱）
- **现象描述**：用户在 QA 审核中发现右上角“当前系统预设提示词 (System Prompt Preview)”排版极其混乱，存在三个严重问题：1）部分 Assistant 历史回复被错误地加上了 `[YYYY-MM-DD HH:MM] ` 的时间戳前缀（放在了 `<think>` 标签最前面），既破坏了格式规范，又导致大模型在上下文学习中误以为回答需要带时间戳（引起 Bug #5）；2）被动态示教管线替换的第一条 Assistant 回复没有时间戳，而后续各条却带时间戳，导致对白格式前后不一致；3）在点击“查看当前完整系统提示词”按钮打开弹窗时，如果后台异步请求或流式拉取未完全就绪，弹窗不会主动拉取最新内容，导致最新一轮 AI 生成回复在弹窗中缺失。
- **解决路线**：
  1. Assistant 洁净对白保证：在 [context_manager.py](file:///d:/MeiWenfeng-Classroom/backend/services/context_manager.py) 的 `assemble_messages` 中，将时间戳前缀注入逻辑严格约束为 `if ts and isinstance(ts, str) and role == "user":`，只对用户的提问附加上下文时间标尺，坚决不向 Assistant 回复添加任何时间前缀，保证 AI 回答纯粹地以 `<think>` 开头。
  2. 弹窗主控即时刷新：在 [ChatPanel.jsx](file:///d:/MeiWenfeng-Classroom/frontend/src/components/ChatPanel.jsx) 中将 `fetchSystemTokens` 提炼为独立可访问方法，并在点击“查看当前完整系统提示词”按钮（`onClick`）打开弹窗时，强制执行一次 `fetchSystemTokens()`，确保每次弹窗展现的都是 100% 实时同步的最新对白与系统提示词。
  3. TDD 闭环验证：在 [test_context_manager.py](file:///d:/MeiWenfeng-Classroom/backend/tests/test_context_manager.py) 新增 `test_assemble_messages_only_injects_timestamp_to_user_messages_bug_9`；在 [ChatPanel.test.jsx](file:///d:/MeiWenfeng-Classroom/frontend/src/components/ChatPanel.test.jsx) 新增 `TDD 6 [Bug #9]: triggers system_context fetch when opening system prompt modal or clicking button`，全量前后端测试绿灯通过。


### 10. [已解决 / 物理空间校准] RAG 知识库语义检索缺乏有效相似度阈值过滤（闲聊时仍强制召回无关讲义）
- **现象描述**：在用户进行日常招呼或发送口语化短语（如 `你好`、`呃呃呃`、`现在呢？`、`依旧没解决`）时，系统右上角仍提示“成功检索并加载：3 个讲义片段”，并在尾部夹层（`<system_injection>`）中强行注入了与对话毫无关系的 STM32 / GPIO 硬件编程讲义切片。
- **物理空间真实分布调研（通过 `benchmark_rag_threshold.py` 68 组样本实测）**：
  1. 此前设定的 `dist <= 1.2` 在真实高维向量空间（`paraphrase-multilingual-MiniLM-L12-v2`）中彻底失效；原单测中依靠 `unittest.mock` 凭空伪造 `distances: [[1.5, 1.6]]` 蒙蔽了测试管线。
  2. 剔除非工科冗余切片、仅保留纯净硬核嵌入式硬件与操作系统的教学语料后，物理空间呈现出清晰的分隔屏障：
     - **纯闲聊与日常招呼（Suite A）**：欧氏平方距离区间落在 `[0.8038 ~ 0.9806]`，均值 `0.8841`。
     - **口语状态追问与模糊沟通（Suite B）**：欧氏平方距离区间落在 `[0.7889 ~ 0.9320]`，均值 `0.8764`。
     - **真实硬核技术提问（Suite C）**：欧氏平方距离区间落在 `[0.1557 ~ 0.6611]`，均值 `0.3637`。
  3. **绝对安全物理隔离区间**：在物理区间 `[0.68 ~ 0.78]` 内，闲聊/口语误报率降至绝对 **0.0%**（0 False Positives），而技术讲义真召回率高达 **100.0%**！
- **解决路线**：
  1. **收敛物理门限**：将 [chroma_client.py](file:///d:/MeiWenfeng-Classroom/backend/services/chroma_client.py) 中 `retrieve` 与 `retrieve_memory` 的距离过滤阈值自 `1.2` 严格收紧校准至黄金中道门限 **`0.75`**。
  2. **废除自欺欺人 Mock 测试**：在 [test_rag_retrieval.py](file:///d:/MeiWenfeng-Classroom/backend/tests/test_rag_retrieval.py) 中重构单测 `test_rag_retrieval_filters_out_irrelevant_casual_chat_bug_10`，彻底移除 `mock_coll.query` 伪造 distances，改为建立临时真实 ChromaDB 集合写入实体讲义，利用真实向量模型计算物理距离，验证闲聊被 `0.75` 精准过滤且专业提问成功通过，全量 92 项回归单测绿灯通过。


### 11. [已解决] 知识库分块重叠切片（`_chunk_text` Overlap）导致文本拼接出现半截单词与重复乱码
- **现象描述**：用户发现注入到提示词尾部的讲义切片文本中，存在诡异的重复和半截乱码（例如上一句话是 `选中多个引脚（如...）`，紧接着下一行重复出现半截句子 `个引脚（如...）`）。
- **解决路线**：
  1. 句界识别重构：优化 [chroma_client.py](file:///d:/MeiWenfeng-Classroom/backend/services/chroma_client.py) 的 `_chunk_text` 算法，废弃了粗暴的字符级截取 `[-overlap:]`，引入 `_get_overlap_text` 辅助算法在重叠区域内倒序查找最近的自然句界（`。！？\n`），保证新切片起始于完整句号后，彻底消灭半词和乱码。
  2. TDD 闭环验证：在 [test_rag_retrieval.py](file:///d:/MeiWenfeng-Classroom/backend/tests/test_rag_retrieval.py) 新增 `test_chunk_text_uses_natural_boundaries_without_character_truncation_bug_11`，回归测试绿灯通过。

### 12. [已解决] 回合间隙预览时尾部注入强塞历史 User 导致对白视觉割裂（反向扫描架构缺陷）
- **现象描述**：当 AI 刚刚回答完毕（当前列表末尾为 `Assistant` 回复）、用户尚未发起新提问时，若点击查看“当前完整系统提示词”预览，`assemble_messages` 会触发倒序寻找到上一轮旧 `User` 消息并将庞大的 `<system_injection>` 尾部夹层追加其中。结果硬生生将原本问答相连的 `User` 与 `Assistant` 暴力劈开，把 AI 上一次回复挤到预览最末尾，引起严重视觉割裂与误解。
- **根因分析（深度架构见解）**：在旧版 `assemble_messages` 中，开发者惯性使用了 `for i in range(len - 1, -1, -1)` 倒序往回扫描历史寻找 `user` 消息。这种“向后翻找历史”本身就是底层架构反模式 —— 尾部夹层永远只属于对话物理列表的“最后一条元素”。如果最后一条不是 `user`（如回合完结待机中的 `assistant` 或其他非 user 消息），向前翻找污染历史 `user` 就是视觉割裂的根本死因。
- **状态更新 (2026-07-05)**：通过 TDD [ISSUE-11] 彻底闭环解决：
  1. **废除历史倒序扫描**：彻底删去 11 行冗余的倒序循环与 `injected` 状态变量，将时间复杂度由 O(N) 降为极致的 O(1)。
  2. **建立 O(1) 物理边界断言**：通过常数时间条件判断 `if len(formatted_messages) > 0 and formatted_messages[-1]["role"] == "user":`；若当前物理最末端为 `user`，直接把尾部夹层追加至该条尾部；否则一视同仁在末尾 `append` 干净的待机容器 `{"role": "user", "content": "[下一轮提问等待中 / Waiting for next prompt]" + tail_injection}`。
  3. **TDD 闭环验证**：在 [test_context_manager.py](file:///d:/MeiWenfeng-Classroom/backend/tests/test_context_manager.py) 中新增回归单测 `test_assemble_messages_o1_tail_injection_no_reverse_scanning_bug_12` 与 `test_assemble_messages_prevents_visual_tearing_on_assistant_end_bug_12`，验证无倒序扫描及对白连贯性，全量 10 个测试绿灯通过。

### 13. [已解决 / 架构解耦] AgentExecutor 的流解析与工具调度耦合
- **状态更新**：已通过架构重构彻底解耦。抽离出独立的高内聚流式解析适配器 `backend/services/stream_parser.py` (专注于 SSE 流事件切分与 XML 解析) 与独立的工具执行引擎 `backend/services/tool_engine.py` (专注于多工具并发与权限控制)。`AgentExecutor` 仅作为轻量级调度回路，删除了 40 多行冗余旧代码。

### 14. [已解决 / 架构解耦] Model Router 路由层人设泄漏
- **状态更新**：已在架构解耦重构中彻底解决。网络路由层 `backend/services/model_router.py` 中的 `stream_chat` 函数已移除了长达 30 行的 `perfect_one_shot` 硬编码及所有角色扮演逻辑。该逻辑被收拢迁移至上下文与管线引擎 `backend/services/context_manager.py` 的 `assemble_messages` 方法中进行集中组装。路由层现在只纯粹负责接收并分发完全就绪的报文。

### 16. [已解决 / 架构解耦] 长程对话上下文管理与提示词尾部注入 (Tail Injection)
- **状态更新**：已正式抽离并列装高内聚的 `backend/services/context_manager.py` 模块。采用“顶部静态系统预设 (Static Persona) + 尾部三明治动态注入 (Tail Injection)”架构，动态整合 RAG 切片、近期记忆日志与 IDE 状态。同时实现了严格的**分回合工具切断协议 (Turn Separation Protocol)**，在调工具回合静默触发 API 调用不吐独白，彻底解决了长程对话中的格式错乱与 Token 浪费问题。

