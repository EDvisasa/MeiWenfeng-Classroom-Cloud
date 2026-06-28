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

### 3. [正在测试] 本地小模型思考过程格式泄露（未遵循 XML 规范）
- **现象描述**：在与本地小模型（如 `ornith-1.0-9b`）对话时，模型未能正确使用 `prompts.py` 中规定的 `<inner_thought>` 或 `<thought>` 等 XML 标签来包裹内心独白。相反，模型直接输出了纯文本 `Thinking` 并紧接英文思考链（例如 `Thinking\nThe user is playfully...`），导致后端的 `ResponsePipeline` 无法基于 XML 规则进行有效拦截，直接将思考过程暴露给了用户界面。
- **解决方案 (2026-06-28)**：
  - **零侵入架构决策**：坚持“大模型主动适配系统”原则，不修改本地任何 Python 路由逻辑。
  - **落地手段 (Assistant Prefill)**：在 `C:\Users\EDvisa\.lmstudio\config-presets\Classroom-Agent.preset.json` 中为其定制了专属 ChatML 强制模板。通过在 `messages` 渲染流的末尾强制注入 `<|im_start|>assistant\n<inner_thought>\n`，在物理层面上劫持了模型的首个 Token 生成，迫使其必须在 XML 标签内完成思考闭环，完美适配了后端的 `TagStreamInterceptor`。
- **当前状态**：方案已实装，当前正在长期测试其在连续多轮复杂对话中是否会出现格式抖动或回退。
