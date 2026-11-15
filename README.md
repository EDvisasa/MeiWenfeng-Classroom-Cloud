# 媚吻锋随身课堂 (MeiWenfeng Classroom)

> 轻量化本地 Agentic 伴学与角色扮演教学引擎 — FastAPI + React + 本地双轨 RAG + 自主记忆召回架构

---

## 📖 项目简介

**媚吻锋随身课堂**是一个完全独立运行的本地 Web 伴学与教学应用。后端基于 Python **FastAPI** 与可插拔 **LiteLLM** 网关构建，前端采用 **React 19 + Vite 8**（并附带 `vscode-extension/` VS Code 侧边栏插件工程），通过分层上下文管线（`ContextManager`）、多轮工具执行器（`AgentExecutor`）与字符级响应拦截管道（`ResponsePipeline`），兼顾流式对话体验、多轮本地工具协作、课程沙盒教学与跨日长程记忆管理。

### 核心特性
- ✅ **双氛围模式与人设切换** — 状态栏一键切换 **【生活 / 研学】**（日常伴读温情 vs 现代数理工程严谨授课）与 **【精简 / 原版】** 人设；支持多模态图片上传与剪贴板粘贴提问。
- ✅ **流式渲染与丰富教学组件** — 原生支持 Markdown GFM 表格、`KaTeX` 数学公式（`$...$` / `$$...$$`，长公式横向自适应滚动）、`<explainer>` 理论讲义卡与 `<quiz>` 四选一互动测验卡。
- ✅ **12 工具四类正交智能体路由** — 集成 **`[Memory]`**（4）、**`[Workspace]`**（5）、**`[Web]`**（2）、**`[Collab]`**（1）共 12 个安全工具，支持 AST 级 Bash 防注入、高危操作人工确认（`HITL`）、多步无硬编码截断探索，并在前端自动收敛为 `Remembering...` 多步卡片。
- ✅ **双层主动记忆召回与遗忘曲线衰减** — 默认内置零依赖本地 **ChromaDB** 向量库（教学知识库与聊天记忆库物理隔离），可选挂接外部 **RAGFlow**；支持会话内 `/compact` 压缩与跨日四段式记忆衰减 `/summarize`，并支持日历/时间线/关键词/原文展开主动回溯。
- ✅ **多课题物理沙盒隔离与 ZPD 渐进心流** — 支持 `/set_mission`、`/plan`、`/lesson [course_id]` 按课题隔离讲义、参考资料、学习漂移记录（LDRs）与代码沙盒，并根据答题表现动态调节 ZPD 难度系数。
- ✅ **多模型无缝切换与局域网跨屏访问** — 通过 LiteLLM 与 UI「🔌 API 设置」支持 DeepSeek、OpenAI 兼容接口、本地 Ollama / llama.cpp 及 Claude / Gemini；后端内置局域网 IP 白名单校验，支持手机/平板同 Wi-Fi 访问。

---

## 📁 目录结构

```text
MeiWenfeng-Classroom/
├── backend/                          # Python FastAPI 后端
│   ├── main.py                       # 应用入口、CORS 与局域网 IP 白名单中间件
│   ├── database.py                   # SQLite Schema 初始化与连接管理
│   ├── litellm_config.yaml           # LiteLLM 代理网关模型路由配置
│   ├── mcp_server.py                 # FastMCP 服务接口（暴露记忆检索与当前课程读取）
│   ├── requirements.txt              # Python 核心依赖声明
│   ├── routers/                      # API 路由层
│   │   ├── chat.py                   # ↳ 流式对话、中断控制、会话存储与消息回滚
│   │   ├── course.py                 # ↳ 课题切换、大纲进度与 ZPD 难度状态
│   │   ├── rag.py                    # ↳ 知识库同步与向量检索接口
│   │   ├── memory.py                 # ↳ 遗忘曲线衰减、记忆状态与人设更新流
│   │   ├── files.py                  # ↳ 本地教学物料与沙盒安全读写路由
│   │   ├── models.py                 # ↳ 模型探测、切换与上下文预算查询
│   │   ├── db_viewer.py              # ↳ 内置只读数据库审查面板接口
│   │   └── openclaw.py               # ↳ OpenClaw 外部系统桥接接口
│   ├── services/                     # 核心业务引擎（上下文管线/工具执行器/记忆检索引擎等）
│   ├── scripts/                      # 独立联调探针与手工检查脚本
│   ├── tests/                        # pytest 自动化测试套件（带生产库与 Chroma 物理隔离）
│   ├── classroom.db                  # [运行期自动生成，.gitignore 屏蔽] 本地 SQLite 数据库
│   └── rag_index/                    # [运行期自动生成，.gitignore 屏蔽] Chroma 向量与模型缓存
├── frontend/                         # React + Vite 前端工作台
│   ├── src/
│   │   ├── components/               # ChatPanel / StatusPanel / DatabaseViewer / PreviewEditModal
│   │   │                             # KnowledgeLibraryModal / MissionProposalCard / QuizBlock / FileTree / CropModal
│   │   ├── constants/commands.js     # 全局斜杠指令表 (SSOT)
│   │   ├── services/                 # commandDispatcher（指令分发）与 rollbackService（消息回滚）
│   │   ├── utils/                    # markdownPlugins.js / blockParser.js / cropImage.js
│   │   ├── config.js                 # 跨端动态 API 寻址配置
│   │   ├── App.jsx                   # 主布局入口
│   │   └── index.css                 # 暗色毛玻璃主题样式
│   ├── package.json                  # 前端脚本与依赖（含 Vitest 单测）
│   └── vite.config.js                # Vite 配置（绑定 0.0.0.0:12703）
├── vscode-extension/                 # VS Code 侧边栏 Webview 插件工程
├── data/                             # 用户本地学习资产与角色配置
│   ├── materials/                    # [.gitignore 仅保留目录模板，数据纯本地保存]
│   │   ├── References/               # 理论讲义卡片（需 /prepare 同步至 RAG）
│   │   ├── Sandbox/                  # 默认教学实操安全沙盒
│   │   ├── Lessons/                  # 课时大纲与教学记录
│   │   ├── Settings/                 # 个人长期学习目标配置（user_mission.md 等）
│   │   ├── LDRs/                     # 课程规划漂移追踪记录（Learning Drift Records）
│   │   └── courses/                  # 按 course_id 物理隔离的多课题独立目录
│   └── persona/simplified/           # 精简人设配置目录
├── docs/                             # 工程规范、规划文档与架构决策
│   ├── architecture/                 # ADR-000 ~ ADR-014 单文件 HTML 系统架构决策记录
│   ├── planning/                     # 路线图、冲刺工单 (01_sprint_tasks.md)、bug-tracker.md 与 CHANGELOG.md
│   ├── reports/                      # 静态分析与历史评估报告快照
│   ├── GLOSSARY.md                   # 全局领域权威术语字典与双系统隔离表
│   ├── 00_doc_guidelines.md          # 文档分级存储、命名与元数据总纲
│   └── 01_dev_and_test_guide.md      # 自动化测试体系、性能准则与防污染红线
├── AGENTS.md                         # AI 智能体协作宪法与自动寻址路由表
├── pytest.ini                        # pytest 配置与 slow marker 定义
├── start.bat                         # Windows 一键初始化与全栈启动脚本
├── .env.example                      # 环境变量参考模板
└── README.md                         # 本文件
```

---

## 🚀 快速开始

### 前置要求
- **Node.js**（推荐 `18+`）
- **Python**（推荐 `3.10+`，已验证兼容 Python `3.13`）
- **模型配置**：准备可用的 OpenAI 兼容 API Key（如 DeepSeek 等），或本地运行 **Ollama / llama.cpp** 服务。
- **网络环境说明**：日常运行与本地模型对话无需代理（系统默认关闭 LiteLLM 遥测并使用本地模型字典）；仅在**首次使用本地向量检索自动下载 HuggingFace 嵌入模型**或直连海外 API 时，需确保网络或镜像可访问对应服务，模型缓存后即可离线使用。

### 第一步：获取代码

```bash
git clone https://github.com/EDvisasa/MeiWenfeng-Classroom-Cloud.git
cd MeiWenfeng-Classroom-Cloud
```

### 第二步：启动服务

#### 方式 A：Windows 一键启动（推荐）
直接双击根目录下的 **[`start.bat`](start.bat)**，脚本会自动完成：
1. 若缺少 `.env`，自动复制 [`.env.example`](.env.example) 生成初始配置；
2. 自动创建并校验 `.venv` 虚拟环境，按需安装 [`backend/requirements.txt`](backend/requirements.txt)；
3. 自动检测并按需补充 [`frontend/package.json`](frontend/package.json) 依赖；
4. 自动清理占用 `12701` / `12703` / `12704` 端口的残留进程；
5. 通过 `concurrently` 在单窗口内并发拉起三个核心服务：
   - **前端 Vite 界面**：`http://localhost:12703/`
   - **FastAPI 后端服务**：`http://127.0.0.1:12701`
   - **LiteLLM 代理网关**：`http://127.0.0.1:12704`

#### 方式 B：手动命令行启动（跨平台适用）

```bash
# 1. 初始化环境变量与 Python 虚拟环境
cp .env.example .env
python -m venv .venv
# Windows: .venv\Scripts\pip install -r backend/requirements.txt
# macOS/Linux: .venv/bin/pip install -r backend/requirements.txt
npm --prefix frontend install

# 2. 分别启动后端、前端与 LiteLLM 代理（建议使用虚拟环境中的可执行文件）
python -m backend.main
npm --prefix frontend run dev
litellm --config backend/litellm_config.yaml --port 12704 --telemetry False
```

> 💡 **局域网跨屏访问**：项目默认内置局域网 IP 白名单校验，允许本机及 `192.168.x.x` / `10.x.x.x` / `172.16-31.x.x` 内网网段访问，可通过同 Wi-Fi 下的手机浏览器直接打开 `http://你的电脑局域网IP:12703`。

### 第三步：API 与路径配置
- 大模型的 Base URL、API Key、默认模型名以及 **自定义最大上下文 Tokens** 均可直接在网页右上角的 **「🔌 API 设置」** 弹窗中配置并即时生效。
- 如需自定义服务端口、HuggingFace 缓存路径、本地角色立绘目录（`IMAGE_DIR`）或原始/精简人设同步目录（`PERSONA_SOURCE_DIR` / `PERSONA_SIMPLIFIED_OUTPUT_DIR`），请编辑根目录 `.env`（参数说明见 [`.env.example`](.env.example)）。

---

## ⚙️ 核心架构解析

### 🤖 12 工具四类正交路由与 `AgentExecutor` 执行引擎
系统在 [`backend/services/agent_tools.py`](backend/services/agent_tools.py) 统一注册了 12 个工具，并按四类正交标签路由（适配云端大模型与 Hermes 等本地小模型）：
- **`[Memory]` 主动记忆召回（4 个）**：
  - `get_memory_calendar`：按日历查看有对话/日记的活跃日期，查天/查月为空时渐进返回同月活跃日或同年活跃月；
  - `get_memory_timeline`：按单天、月份、年份或 `all` 顺/逆序浏览日记与会话摘要；
  - `search_memory`：支持空格多词打分、SQL `LIKE` 通配符转义与标准化时间戳优先排序；
  - `expand_memory`：展开完整日记正文或同会话上下文窗口，自动剥离历史内部控制标签。
- **`[Workspace]` 工作区与安全沙盒（5 个）**：
  - `read_file`（支持行号分页与 800 行截断保护，原生提取 `.pdf` / `.docx` 文本）、`grep_search`、`create_file`、`replace_file_content`（受路径守卫严格限定于 `data/materials/Sandbox/` 或当前课题独立沙盒）、`execute_bash`（AST 级高危指令拦截 + 前端 `BashApprovalCard` 人工确认机制）。
- **`[Web]` 联网检索与阅读（2 个）**：`web_search`（DuckDuckGo `ddgs`）与 `read_url_content`（`httpx` + `BeautifulSoup4` + `markdownify` 分页长文读取）。
- **`[Collab]` 外部系统协作（1 个）**：`call_openclaw_agent`（桥接 OpenClaw 原生网关）。

底层配合 [`context_manager.py`](backend/services/context_manager.py) 的“静先动后”上下文分层与 O(1) 尾部组装（锁定长会话前缀 KV-Cache 命中，多模态图片强制排于文本之前），以及 [`response_pipeline.py`](backend/services/response_pipeline.py) 的流式拦截、标签清洗与单/多步原子回滚守卫。

### 🧠 双轨 RAG 与双层记忆体系
- **教学与记忆物理隔离**：教学讲义写入 `Classroom_Knowledge`，记忆摘要写入 `Memory_Knowledge`，原始每轮片段记录在 SQLite `memory_logs` 与 ChromaDB `conversation_memory`。
- **双轨向量后端**：默认内置即开即用的 ChromaDB；可在前端「🔌 API 设置」无缝切换至外部 RAGFlow 实例以应对复杂版面学术论文解析。
- **动态遗忘曲线与会话防溢出**：支持自动阈值触发 / 手动 `/compact` 会话历史滚动浓缩，以及 `/summarize` 按日跨阶段提炼浓缩长期记忆。

### 🖥️ 双栏教研工作台与交互卡片
- **全能知识弹窗**：`KnowledgeLibraryModal` 与 `PreviewEditModal` 支持在线预览与修改本地 Markdown 讲义，保存后自动重算向量索引。
- **学习状态闭环**：右侧 `StatusPanel` 集中呈现当前课题、ZPD 难度系数、隐藏好感度阻尼与不应期状态，以及【生活 / 研学】与【精简 / 原版】快捷切换；右上角内置 Token 消耗实时指示与 `DatabaseViewer` 只读数据库检查窗口。

---

## 📋 斜杠命令速查

在聊天输入框中输入 `/` 可触发联想补全与快捷菜单（契约定义见 [`frontend/src/constants/commands.js`](frontend/src/constants/commands.js) 与 [`backend/services/slash_handler.py`](backend/services/slash_handler.py)）：

| 类别 | 命令 | 支持别名 | 功能描述 |
| :--- | :--- | :--- | :--- |
| **课题与教学** | `/set_mission [目标]` | — | 设定或变更长期学习目标（进入审问定稿并生成 `MissionProposalCard`） |
| **课题与教学** | `/cancel_mission` | — | 取消当前目标设定草稿流程 |
| **课题与教学** | `/plan [course_id]` | — | 结合历史进度生成或动态修订课题课程大纲 |
| **课题与教学** | `/lesson [course_id]` | — | 开始或切入指定课题课时，切入【研学】模式并生成 `<quiz>` 随堂测验 |
| **课题与教学** | `/submit` | — | 提交成果接受考核，进入苏格拉底式严格追问与进阶沙盒演进 |
| **课题与教学** | `/end_lesson` | `/下课`、`recess`、`dismiss` | 结算并封存当前课时状态，切回【生活】模式与默认基础档案 |
| **记忆与知识库** | `/compact` | — | 手动浓缩当前会话较早轮次为结构化纪要，防止上下文溢出 |
| **记忆与知识库** | `/summarize` | — | 触发遗忘曲线时间衰减，将未压缩交互切片沉淀为长期记忆 |
| **记忆与知识库** | `/prepare` | — | 将当前左侧选中的讲义文件分块同步至当前知识库（RAG） |
| **人物与人设** | `/reward` | — | 课后奖励互动，增加隐藏好感度并触发专属回馈 |
| **人物与人设** | `/cooldown` | `cooldown` | 降温转场，好感度阻尼回退并进入【静心专注 / 余韵温存】状态 |
| **人物与人设** | `/update_persona` | `/更新人设` | 根据最新长期记忆动态迭代并精简系统人设卡 |

> 注：用户在前端提交 `<quiz>` 选择题后，前端会自动通过内部指令 `/lesson_continue` 回传答题结果以更新 ZPD 难度与连错惩罚，无需手动输入。

---

## 🧪 自动化测试与开发者指引

### 常用测试与构建命令

```bash
# 后端日常快速回归（跳过 @pytest.mark.slow 慢速集成测试）
.venv\Scripts\python.exe -m pytest -m "not slow" -q

# 后端全量测试（提交前完整验收）
.venv\Scripts\python.exe -m pytest -q

# 前端单测 (Vitest)
npm --prefix frontend test -- --run

# 前端生产构建校验
npm --prefix frontend run build
```

> ⚠️ **防污染说明**：后端 `pytest` 通过 [`backend/tests/conftest.py`](backend/tests/conftest.py) 自动将 `SQLite` 与 `ChromaDB` 重定向至临时目录；手工联调生产端点请务必使用 `"dry_run": true` 或 `test-` 前缀会话，详见 [`docs/01_dev_and_test_guide.md`](docs/01_dev_and_test_guide.md)。

### 工程文档与 AI 协作寻址
接手二次开发或使用 AI 智能体协作时，请先阅读以下权威入口：
- **[`AGENTS.md`](AGENTS.md)**：智能体进入仓库的最高寻址路由表与交接自检协议。
- **[`docs/GLOSSARY.md`](docs/GLOSSARY.md)**：全工程通用语言字典与“严肃教学底座 vs 角色扮演系统”双领域隔离法则。
- **[`docs/00_doc_guidelines.md`](docs/00_doc_guidelines.md)**：文档分级存储规范、YAML 元数据与 ASCII 文件命名铁律。
- **[`docs/01_dev_and_test_guide.md`](docs/01_dev_and_test_guide.md)**：TDD 规范、测试速度准则与数据库防污染守卫。
- **[`docs/planning/`](docs/planning)**：演进路线图（`00_project_roadmap.md`）、冲刺任务卡（`01_sprint_tasks.md`）、缺陷追踪（`bug-tracker.md`）与变更日志（`CHANGELOG.md`）。
- **[`docs/architecture/`](docs/architecture)**：长期生效的单文件 HTML 系统架构决策记录（`ADR-000` ~ `ADR-014`）。

---

*最后更新: 2026-11-16*
