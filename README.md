# 媚吻锋随身课堂 (MeiWenfeng Classroom)

> 极致轻量化的本地 Web 角色扮演与教学引擎 - 剥离 LLM Prompt 实现极限 Token 压缩

---

## 📖 项目简介

媚吻锋随身课堂是一个完全独立于 SillyTavern 的本地 Web 角色扮演与教学应用。项目基于 Python (FastAPI) 后端与 React 前端构建，旨在通过将“好感度”、“课程进度”、“记忆管理”从 LLM Prompt 中完全剥离并结构化存储，实现极端的 Token 压缩和更高效的 RAG（检索增强生成）系统。

- ✅ **流式对话渲染** - 内嵌角色设定，自动渲染灰色斜体动作描写
- ✅ **动态记忆衰减** - 本地 ChromaDB 支持，自动提取核心并按遗忘曲线衰减
- ✅ **全景式 IDE 布局** - 深色三栏设计：左侧文件树、中间对话区、右侧导师状态面板
- ✅ **多模型无缝切换** - 支持 DeepSeek、Claude、Gemini 以及本地 Ollama/llama.cpp
- ✅ **内网跨屏访问** - 动态 API 寻址与 IP 白名单防黑设计，支持手机端无缝使用

---

## 📁 目录结构

```
MeiWenfeng-Classroom/
├── backend/                  # Python FastAPI 后端
│   ├── main.py               # API 入口与中间件 (含防肉鸡白名单)
│   ├── routers/              # 路由层 (对话/记忆/知识库/课程大纲/监控)
│   ├── services/             # 核心服务 (模型路由/记忆衰减算法等)
│   ├── database.py           # SQLite 初始化与操作
│   └── classroom.db          # 结构化数据库 (好感度/课程进度/系统配置)
├── frontend/                 # React 前端
│   ├── src/
│   │   ├── components/       # UI 组件 (FileTree/ChatPanel/StatusPanel 等)
│   │   ├── config.js         # 全局动态 API 寻址配置
│   │   ├── App.jsx           # 主程序入口
│   │   └── index.css         # 深色主题与样式系统
│   ├── vite.config.js        # Vite 构建配置 (绑定 0.0.0.0)
│   └── index.html            # 页面入口
├── docs/                     # 项目文档与规划记录
├── start.bat                 # Windows 一键启动脚本
├── start.sh                  # Linux/Mac 一键启动脚本
├── .env.example              # 环境变量参考模板
└── README.md                 # 本文件
```

---

## 🚀 快速开始

### 前置要求

- **Node.js** (推荐 18+版本)
- **Python** (推荐 3.10+ 版本)
- **API 密钥**：获取你希望使用的在线模型 API Key (如 DeepSeek, Claude, Gemini) 或者准备好本地模型服务 (如 Ollama)。

### 第一步：克隆并配置

```bash
# 1. 准备项目代码
git clone https://github.com/YourUsername/MeiWenfeng-Classroom.git
cd MeiWenfeng-Classroom

# 2. 配置环境变量
# 复制 .env.example 为 .env，并填入您的 API Key
copy .env.example .env

# 3. 准备后端环境
python -m venv .venv
# 激活虚拟环境后安装依赖
.venv\Scripts\activate
pip install -r backend/requirements.txt
```

### 第二步：一键启动

双击根目录下的 **`start.bat`**。

脚本将自动：
1. 启动 FastAPI 后端服务（绑定 `0.0.0.0:8000`）。
2. 启动 Vite 前端开发服务器（绑定 `0.0.0.0:5173`）。

> 💡 **局域网访问提醒**：项目默认开启了 IP 白名单防护。您不仅可以在本机的 `http://localhost:5173` 访问，也可以在同一 WiFi 下的手机上，通过输入 `http://您的电脑IP:5173` 进行访问，恶意不明 IP 会被后端自动拦截。

---

## ⚙️ 核心功能解析

### 🧠 记忆系统与时间线重构
内置本地 ChromaDB 向量知识库。基于自研的遗忘曲线算法，系统会按天对历史记忆（精确、关键、模糊、里程碑、索引）进行衰减处理和提炼，解决传统扮演 LLM 动辄塞入几万字上下文导致崩溃或幻觉的问题。

### 📚 课程与大纲进度控制
引入右侧的全局“导师状态栏”，完全图形化展示当前课题、用户理解分数与任务节点。所有交互行为带来的进度改变直接回写至底层的 SQLite `course_progress` 表。

### ⚡ 智能多模型流控
- 支持 **OpenAI 协议兼容** (DeepSeek/Qwen/Llama)
- 支持 **Claude 原生协议**
- 支持 **Gemini 原生协议**

通过右上角的 `🔌 API 设置`，随时切换模型，应对不同知识深度的教学需求。

### 🛡️ 内置数据监控大屏
不必再使用第三方数据库软件瞎猜！前端集成了一个专用的 `DatabaseViewer` 组件。点击界面上的数据库审查图标，就能在只读弹出层内实时审查所有对话日志和用户隐藏档案。

---

## 📋 斜杠命令速查

在对话输入框内输入以 `/` 开头的指令，即可触发后台服务：

| 命令 | 功能描述 |
|------|------|
| `/上课` | 开始新课时，加载当前课时大纲，切换为授课模式 |
| `/交作业` | 检验理解程度，AI 切入"考核模式"出题并等待用户回答 |
| `/奖励` | 课后奖励，基于隐藏好感度解锁特殊剧情段落 |
| `/总结` | 主动压缩记忆，触发衰减算法整合并存入 SQLite |
| `/备课` | 将左侧当前选中的目录上传解析进本地向量知识库 |
| `/计划` | 读取历史进度，对课程大纲的未来路径进行自动重规划 |

---

## 📚 开发者指引 (给 AI 的备注)

当你后续接手此工程进行二次开发时，请首先查阅 `docs/` 目录：
- **`docs/任务进展.md`**：了解项目最新版本的开发进度和已修复 Bug 记录。
- **`docs/项目实施计划.md`**：如果需要做大型系统重构或调整阶段性核心目标，请以此为蓝本。

---

*最后更新: 2026-06-15*
