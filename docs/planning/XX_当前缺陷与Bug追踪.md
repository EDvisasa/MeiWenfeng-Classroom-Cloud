# 04 - 当前缺陷与Bug追踪

> **目标**：集中记录当前系统已发现的缺陷（Bugs）及需要修正的项点，便于后续进行调查分析与逐一修复。严禁未经调研盲目修改代码。

## 🔴 待修复 Bug 列表 (Current Bugs)

### 1. 数据目录写入与存储机制异常
- **现象描述**：系统目前对于如何对 `data/` 文件夹进行合法的写入操作、以及如何标准地存储教学文档，缺乏明确的工作流。
- **调查方向**：
  - 需要分析现有的 `AgentExecutor` 与沙盒 (`Sandbox`) 工具流中，如何才能合法向 `data/materials/` 等受保护的目录写入数据。
  - 需要排查后端安全机制（如防注入护栏和路径穿越防御）是否过度拦截了正常的教学文档保存动作。

### 2. 前端 `.md` 文件渲染导致白屏崩溃
- **现象描述**：在网页前端的导师状态栏或资源树中，一旦点击 `@data/materials` 目录下的任意 `.md` 文件，不会正常展示文本内容，而是导致整个 React 界面直接变白屏（前端应用崩溃）。
- **调查方向**：
  - 检查前端文件预览组件或 Markdown 渲染组件（如使用了 `react-markdown` 等库）是否存在解析异常或未捕获的渲染错误。
  - 检查后端拉取文件内容的 API（如 `GET /api/files/...`）返回的数据结构是否符合前端预期。
  - 修复前必须先查看浏览器的 Developer Console 报错堆栈以精准定位崩溃点。

### 3. [待修复] 小模型思考链引发正则截断故障（嵌套标签污染）
- **现象描述**：在与本地小模型（如 `ornith-1.0-9b`）对话时，模型经常会在其原生的 `<thought>` 思考过程中“打草稿”，提及 `<inner_thought>` 标签（例如在英文思考流中输出：`Output an <inner_thought> block and at the very end...`）。由于前端 `blockParser.js` 提取内心独白时使用的是正则匹配，这导致它把 `<thought>` 里面的这个字符串误认为了起始点，一口气将后续的整个思考过程、对话正文，直到真正的 `</inner_thought>` 出现前的所有内容，全部错误地打包塞进了“此刻内心”的渲染框里，造成页面排版严重错乱。
- **调查方向**：
  - 前端渲染：需修改 `blockParser.js` 的正则或解析逻辑。提取 `<inner_thought>` 时，必须排除掉包含在 `<thought>...</thought>` 内部的内容。
  - 后端管线：需排查后端的流式拦截器（`TagStreamInterceptor`）在遇到这种“思考过程中提及 XML 标签”的情况时，其内部的状态机（`in_tag`）是否也会发生混乱。

## 🏗️ 架构与深模块解耦缺陷 (Architecture Deepening Opportunities)

### 4. AgentExecutor 的流解析与工具调度耦合
- **现象描述**：`AgentExecutor.run` 作为上帝函数，严重混合了 LLM 流分块解析、多线程执行与系统状态管理，导致新增模型服务商或修改解析逻辑极易破坏底层工具执行，缺乏局部性 (Locality) 和接缝 (Seam)。
- **调查方向**：将流式解析适配器 (`StreamParser`) 与完全独立的工具引擎 (`ToolExecutionEngine`) 解耦。

### 5. Model Router 路由层人设泄漏
- **现象描述**：网络路由模块 `stream_chat` 内硬编码了长达 30 行的 `perfect_one_shot` 字符串。这导致路由层被核心角色扮演逻辑污染。
- **调查方向**：将 One-Shot 的动态注入逻辑移动到 `prompts.py` 中的 `PromptBuilder` 内，路由器只接收完全就绪的 messages。

### 6. 斜杠指令 (Slash Commands) 巨石阵结构
- **现象描述**：`slash_handler.py` 内部使用庞大的 `if/elif` 链为每个指令硬塞海量多行 XML 系统指令。难以新增或删除，完全违背删除测试 (Deletion Test)。
- **调查方向**：提炼 `CommandStrategy` 接口，每条指令独立为类，由核心注册器分发。
