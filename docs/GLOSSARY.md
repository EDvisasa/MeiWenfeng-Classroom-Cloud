---
id: DOC-GLOSSARY
title: 全局领域通用语言字典
status: active
created: 2026-07-04
updated: 2026-07-10
domain: core-architecture
---
# 📚 媚吻锋随身课堂 —— 全局领域通用语言字典 (Ubiquitous Language Dictionary)

> **对齐标准**：`ubiquitous-language` & `domain-modeling` 技能规范。  
> **核心作用**：本字典是全工程架构建模、代码命名、表结构设计与技术文档撰写的**最高语义标准与单一点权威 (Single Source of Truth)**。任何智能体或人类开发者在修改系统前，必须对照本字典核定用词规范。

---

## 一、 核心领域通用术语字典表 (Consolidated Ubiquitous Dictionary)

本项目严格区分 **严肃教学架构底座系统 (Serious Teaching Core System)** 与 **虚拟角色扮演系统 (Roleplay Persona System)**。下表按子领域划分，明确各核心概念的标准用词、物理代码/数据库映射及使用边界。

### 1.1 严肃底层架构与报文编排术语 (Core Architecture & Context Pipeline)

| 规范业务概念 (Ubiquitous Term) | 物理源码/符号映射 (Code Symbol) | 核心概念定义 (Authoritative Definition) | ❌ 绝对禁止的混淆表达 (Prohibited Terms) |
| :--- | :--- | :--- | :--- |
| **上下文会话管线管理器** | `ContextManager` <br>(`backend/services/context_manager.py`) | 负责管理多轮会话窗口切断（`[PHASE 2]` 回合截断）、发包前上下文组装与流式处理的核心类。 | ❌ 严禁称作“心法流运转”、“神识管线”或“魔法通道”。 |
| **静态系统预设** | `Static Persona Prompt` <br>(`role: system`) | 处于报文列表最顶部（且仅在第一条）的静态设定、角色基础信息与核心教学守则。 | ❌ 严禁简称为模糊的“系统提示词全局”或混淆指代整包上下文。 |
| **动态尾部夹层** | `Dynamic Tail Injection` <br>(`tail_injection`) | 每次大模型请求发出前，由会话管理器动态追加至物理列表尾部的上下文感知块，整合当前时间戳 `<current_time>`、RAG 检索证据与防错约束。 | ❌ 严禁称作“小尾巴”、“系统尾缀”或与顶部静态系统预设混为一谈。 |
| **待机轮次容器** | `Standby Turn Container` | 在 AI 回合完结后、用户发起下一轮提问前，为承载动态尾部夹层而在末尾独立构造的临时 `user` 角色占位消息。 | ❌ 严禁称作“假消息”、“空问答”。 |
| **实时组装报文视窗** | `Assembled Context Payload` <br>(`/api/chat/system_context`) | 经由单发示教、窗口截断及尾部夹层组装完毕后，最终发往大模型 API 交互的完整会话报文快照。 | ❌ 严禁简称为“系统预设”，必须体现这是发包快照全量。 |
| **流式事件传输协议** | `SSE (Server-Sent Events)` <br>(FastAPI `/chat/stream`) | 前后端打字机流式输出与状态帧传输的单向长连接通信协议。 | ❌ 严禁称作“飞剑传音”等叙事虚构词汇。 |

### 1.2 教学处理与调度控制术语 (Teaching Control & Sandbox)

| 规范业务概念 (Ubiquitous Term) | 物理源码/表符号 (Code Symbol) | 核心概念定义 (Authoritative Definition) | ❌ 绝对禁止的混淆表达 (Prohibited Terms) |
| :--- | :--- | :--- | :--- |
| **斜杠指令处理器** | `SlashHandler` <br>(`backend/services/slash_handler.py`) | 负责路由并执行 `/lesson`, `/submit`, `/set_mission`, `/plan`, `/qa` 等教学动作的后端引擎类。 | ❌ 严禁称作“法阵调度员”或“咒语路由器”。 |
| **学习决策记录** | `learning_decision_records` <br>(SQLite 数据表) | 结构化记录用户对知识要点的掌握证据 (`evidence`)、推论 (`implications`) 与溯源 (`superseded_by`)。 | ❌ 严禁称作“修炼心得簿”。 |
| **最近发展区难度追踪** | `course_progress` <br>(SQLite ZPD 指标列) | 依据最近发展区理论 (ZPD)，对用户学习难度与掌握度进行自适应评估与跟踪的指标体系。 | ❌ 严禁称作“破境等级”或“道行”。 |
| **实操编程沙盒空间** | `data/materials/Sandbox/` <br>(受控工作区) | AI 导师唯一被授权操作代码创建与演练示例输出的隔离文件目录。 | ❌ 严禁称作“炼丹炉”或“练功房”。 |
| **跨智能体协同网关桥接** | `call_openclaw_agent` / `<openclaw_gateway_status>` | 负责向外部 OpenClaw 智能体网关分派任务及健康状态探测的连接通道 (`Inter-Agent Gateway Bridge`)。 | ❌ 底层类或接口严禁带角色昵称。 |

### 1.3 虚拟角色扮演与人设层术语 (Roleplay Persona Layer)

| 规范业务概念 (Ubiquitous Term) | 物理源码/表符号 (Code Symbol) | 核心概念定义 (Authoritative Definition) | 容忍度说明 |
| :--- | :--- | :--- | :--- |
| **角色心流与状态机** | `CSM 状态机` | 驱动角色根据场景变换语气态度（温和/严厉/激将）的心流决策逻辑。 | 允许在人设提示词或剧情会话中体现。 |
| **师生亲密度参数** | `affection` <br>(SQLite `affection` 表) | 衡量用户互动频度与好感反馈程度的后台隐蔽参数。 | 属于角色扮演层变量。 |

### 1.4 提示词工程与发包隔离规范 (Prompt & Context Core Definitions)

| 规范词条 | 简明释义 (Definition) | 架构归属 |
| :--- | :--- | :--- |
| **【零污染铁律】Zero DB Pollution** | 临时尾部夹层及过渡短语必须作用于内存深拷贝消息列表上，严禁污染业务层与持久化消息对象。 | 报文隔离规范 |
| **【效率铁律】Concise English for System Instructions** | 中文仅限人设与对白；元提示词、系统约束及过渡引导句必须使用凝练纯英文，实现中英隔离与 Token 节约。 | 提示词工程规范 |
| **【边界铁律】User Speech Disclaimer** | 附着在最后一条提问底部的系统注入上下文，需包夹显式免责声明，明确属于运行时系统变量而非用户发言。 | 提示词工程规范 |

> 📌 **开发实操细则引用**：提示词深拷贝要求、全英文过渡指引实施案例，请以单一点权威手册 [`docs/01_dev_and_test_guide.md` 报文编排与提示词准则](file:///D:/MeiWenfeng-Classroom/docs/01_dev_and_test_guide.md#L92-L104) 为准。

---

## 二、 核心架构深度模块界定 (Core Deep Modules)

本项目核心模块设计遵循 Deep Module（深模块）原则，隐藏复杂逻辑并暴露简洁清晰的语义接口：
- **CharacterState (`CharacterState`)**：虚拟角色的领域实体，封装好感度、修养、为人处世及生理状态等核心数值。
- **CharacterStateManager (`backend/services/character_state_manager.py`)**：负责角色数值跃迁校验与持久化的深模块。遇到非法操作时显式抛出 `CharacterStateError`，严禁隐式吞除异常。
- **ActionRegistry 与 Side-Effect Handlers**：管理流式响应生命周期中的无状态副作用处理逻辑（如动作快照、课表同步）。

---

## 三、 概念关系声明与通用语言实践 (Relationships & Ubiquitous Dialogue)

### 3.1 报文组装概念结构关系
- 一个 **实时组装报文视窗 (Assembled Context Payload)** 恒等于：
  `恰好一个静态系统预设` + `历史多轮对白切片` + `附着在物理末端的动态尾部夹层`
- 动态尾部夹层的附着位置规则：若报文末尾属于用户真提问，直接追加在提问文本上方；若报文末尾属于 AI 刚回答完毕，则额外封装在一个 **待机轮次容器 (Standby Turn Container)** 中。

### 3.2 团队协作通用语言实践沟通示例
> **Dev:** "点击前端的‘查看当前完整系统提示词’按钮时，返回的其实是 **实时组装报文视窗 (Assembled Context Payload)** 对吗？"  
> **Domain expert:** "没错。以前叫它‘系统预设提示词’是严重语意重载，会让大家误以为里面只有顶部的 **静态系统预设 (Static Persona Prompt)**。"  
> **Dev:** "难怪 QA 问‘怎么看底部的上下文尾缀’。将页面和后端变量统一为 **实时组装报文视窗** 后，大家就清楚滚动到底部能查验 **动态尾部夹层 (Dynamic Tail Injection)** 了。"

---

## 四、 命名一致性自检清单 (Naming Consistency Checklist)

进行新模块研发或 Schema 迭代时，须按照下述清单进行合规检查：
1. **类名/数据库字段名**是否与**表一**物理映射保持绝对一致？（例如数据库记录表统一以 `learning_decision_records` 命名，不得私自构造别名）；
2. **系统引导与提示词**是否符合英文凝练原则（禁止向 AI 提示词泄露“管线/夹层”等开发者架构术语）；
3. **架构文档 (ADR)** 是否完全剔除叙事修辞，采用严谨的工程通用用语？
