---
id: PLAN-00
title: 开发计划总纲
status: active
created: 2026-06-27
domain: project-planning
---
# 媚吻锋随身课堂 —— 开发计划总纲

> **核心规范与纲领说明**：本文件是整个项目的宏观规划蓝本，只记录核心架构、设计决策与宏观阶段规划。具体的待办任务（Checklist）和子系统设计，请参阅本目录下的其他子项文件。
> **文档与架构遵守铁律**：全站所有架构设计文档、目录结构与命名准则必须服从最高总纲 **`docs/00_doc_guidelines.md`** 的约束，恪守 **角色扮演系统（台词人设模拟）** 与 **严肃教学及底座系统（现代工程技术标准）** 的双领域物理隔离。

## 一、核心架构与设计决策

| 维度 | 最终决定 |
|---|---|
| 后端语言 | **Python (FastAPI)** |
| 前端框架 | **React + Vanilla CSS** |
| 数据存储 | **SQLite**（全量涵盖 11 张核心业务与架构表） |
| 知识库 | **ChromaDB 本地内嵌库**（默认推荐） / **RAGFlow 本地实例**（复杂文档深度解析） |
| UI 布局 | **三栏 IDE 式**：左(文件树) / 中(对话授课区) / 右(状态面板) |
| 交互特色 | **斜体灰色动作描写**，好感度隐性化处理 |

## 二、多模型支持矩阵与统一网关架构

当前系统采用 **LiteLLM 本地网关 (端口 12704)** 实现多模型负载统一分发，严格对齐系统预置默认模型：

| 模型配置名称 | 接口协议 | 默认地址 / 承载机制 | 选型与说明 |
|---|---|---|---|
| DeepSeek (网关) | OpenAI 兼容 | `http://127.0.0.1:12704/v1` | 主力云端大模型 (`deepseek-chat`)，通过 LiteLLM 网关分发 |
| Gemini-Pro (网关) | OpenAI 兼容 | `http://127.0.0.1:12704/v1` | 备用云端多模态模型 (`gemini-3.1-pro-preview`) |
| Qwen-Local (网关) | OpenAI 兼容 | `http://127.0.0.1:12704/v1` | 本地自部署通义千问模型 (`qwen-local`) |
| Claude-Sonnet (网关) | OpenAI 兼容 | `http://127.0.0.1:12704/v1` | 高阶编码与深度推理模型 (`claude-3-sonnet`) |

> 💡 **架构注记**：系统底层具备完整的本地回环白名单保护机制（支持任意 `localhost`/`127.0.0.1`/`0.0.0.0` 离线端口），用户如挂载第三方本地私有化模型服务，均享受白名单路由守护，绝不劫持请求至外网。

## 三、底层数据库表设计 (SQLite 全量真实映射)

严格恪守技术底座现代命名与数据建模规范，当前系统真实存在的 11 张核心数据表及演进字段定义如下：

- **会话与基础消息表**：
  - `chat_sessions`: 会话历史记录会话元数据（ID、标题、`compact_summary` 结构化浓缩纪要、`compact_cutoff_id` 会话压缩分水岭指针）
  - `chat_messages`: 每一轮的具体对话与角色气泡文本（包含 `images` 多模态图片载荷列）
- **教学与课程状态表**：
  - `course_progress`: 严肃教学系统的进阶课程大纲与用户掌握状态（含 `zpd_coefficient` 最近发展区动态难度系数、`consecutive_correct` / `consecutive_wrong` / `total_consecutive_wrong` 连胜连错追踪）
  - `glossary`: 核心课程术语字典表（基于 Matt Pocock 理念，存储冷酷本体论定义）
  - `learning_decision_records`: 学习决策记录（LDRs，记录证据 `evidence`、推论 `implications` 与版本链 `superseded_by`）
- **长期学习目标管理表**：
  - `user_mission`: 用户确立的全局学习目标与核心任务指标（防空泛约束）
  - `mission_draft`: 目标拟定期的临时数据缓冲与锁定状态（`goal`, `daily_time_budget`, `hard_constraints`, `current_skill_level`）
- **系统引擎与检索配置表**：
  - `model_config`: 多模型接入配置及 API Key 密钥池（含 `selected_model_id`, `max_context_tokens`, `is_custom_tokens`, `supports_vision`）
  - `rag_config`: 动态 RAG 检索后端连接参数（ChromaDB / RAGFlow）
- **角色扮演记忆表**：
  - `memory_logs`: 长期记忆日志（供四段式记忆衰减脚本 `memory_decay.py` 处理，受数据库防清空物理拦截保护）
  - `affection`: 虚拟导师交互好感度与亲密度参数（包含 `social_status`, `social_skills`, `refractory_period` 生理不应期, `daily_gain_date`, `daily_gain_amount` 每日上限约束, `reunion_warmup_turns` 破冰补偿）

## 四、斜杠命令流转体系

| 命令 | 触发类型 / 后端路由 | 核心业务目标 |
|---|---|---|
| `/lesson` | 大模型注入微课流 | 根据当前课题与 ZPD 系数推送包含 `<quiz>` 测验组件的极简交互微课 |
| `/submit` | 大模型注入考核流 | 严格苏格拉底式审问，验证掌握度，触发闭环判题并演进沙盒（`data/materials/Sandbox/`） |
| `/set_mission`| 目标设定交互流 | 触发四要素审问（目标/时间/约束/基线），通过防空泛拦截锁定或更新全局宏大目标 |
| `/cancel_mission` | 系统重置流 | 取消并清除当前正处于草稿拟定中的目标任务缓冲 |
| `/compact` | 纯系统长记忆浓缩 | 手动对超长会话历史执行滚动浓缩，更新 `compact_cutoff_id`，保留最近 10 轮原汁原味对白 |
| `/summarize` | 后台记忆衰减任务 | 触发四段式衰减管线（`memory_decay.py`），对 `memory_logs` 进行即时归档与被动延时降级 |
| `/update_persona` (`/更新人设`) | SSE 纯系统状态卡片 | 提炼并刷新角色设定卡，以微光脉冲进度卡片闭环反馈，杜绝虚假对白污染上下文 |
| `/cooldown` (`cooldown`) | 拟人生理调节流 | 触发双态自适应平复台词（真事后怀中看代码 / 日常专注端庄授业），执行潮汐阻尼衰减降温 |
| `/reward` | 亲密度调节流 | 依据学习进展手动赋予好感度奖励与互动鼓励 |
| `/prepare` | 知识库同步流 | 将选定的本地讲义上传至 ChromaDB/RAGFlow 向量知识库 |
| `/plan` | 教学计划流 | 基于大纲进度，输出下一步的栽培任务并在需要时追加 `<new_course>` 节点 |

## 五、宏观开发阶段定义

### 第一阶段 · MVP（已完成）
建立基础三栏布局、FastAPI 后端、连通模型并实现流式输出与人设挂载。

### 第二阶段 · 知识接入与底层基建（已完成）
实现本地 ChromaDB、本地文件树挂载、自动同步解析，以及对话内容的向量化记忆。

### 第三阶段 · 课堂引擎与 Agent 底层融合（当前开发阶段 · 持续演进中）
**核心目标**：将系统从“聊天机器人”升级为具备“闭环反馈与长程记忆”的教学智能体。目前已建设核心基础设施与安全护栏，架构整体融合与深层 Bug 排查联调仍在积极推进中：
- **已落地的核心基础设施**：Agent 精准修改与沙盒隔离（`data/materials/Sandbox/`）、PDF/DOCX 阅读与分页阅读、HITL 人类审核卡片、微课 `<quiz>` 测验组件动态渲染、ZPD 动态难度追踪、`<current_session_history>` 边界隔离以及本地模型路由白名单守护。
- **进行中与待融合项**：斜杠指令巨石阵（`slash_handler.py`）模块化架构重构、深层潜在 Bug 排查与长程交互测试、各子系统（状态机、长短期记忆衰减、RAG 与沙盒演进）的无缝有机融合。

### 第四阶段 · 高级扩展（后续规划）
独立换肤、后台异步任务挂载、完整的原生协议路由与更丰富的多智能体协同扩展。

