---
id: DOC-GLOSSARY
title: 全局领域通用语言字典
status: active
created: 2026-07-04
domain: core-architecture
---
# 📚 媚吻锋随身课堂 —— 全局领域通用语言字典 (Ubiquitous Language Dictionary)

> **对齐标准**：`ubiquitous-language` & `domain-modeling` 技能规范。  
> **核心作用**：本字典是全工程架构建模、代码命名、表结构设计与技术文档撰写的**最高语义标准与单一点权威 (Single Source of Truth)**。任何智能体或人类开发者在修改系统前，必须对照本字典核定用词规范。

---

## 一、 领域术语映射与物理隔离红线 (Domain Mapping & Separation Rules)

本项目严格区分 **严肃教学架构底座系统 (Serious Teaching Core System)** 与 **虚拟角色扮演系统 (Roleplay Persona System)**。下表列明了核心概念的标准技术用词、物理源码符号、所属领域以及绝对禁止的混用黑名单：

| 规范业务概念 (Ubiquitous Term) | 物理源码/表符号 (Code/DB Symbol) | 所属系统领域 (Domain Area) | 核心概念说明 (Authoritative Definition) | ❌ 绝对禁止的混淆说明 (Prohibited Terms) |
| :--- | :--- | :--- | :--- | :--- |
| **上下文会话管线管理器** | `ContextManager` <br>(`backend/services/context_manager.py`) | 严肃底层架构 | 负责管理用户多轮会话窗口切断（[PHASE 2] 回合截断）、API 消息构建与流式生命周期的核心引擎。 | ❌ 严禁在注释或架构文档中称作“心法流运转”、“神识管线”或“魔法通道”。 |
| **斜杠指令处理器** | `SlashHandler` <br>(`backend/services/slash_handler.py`) | 严肃教学系统 | 负责路由处理 `/lesson`, `/submit`, `/set_mission`, `/plan`, `/summarize` 等系统指令的控制器。 | ❌ 严禁称作“法阵调度员”或“咒语路由器”。 |
| **学习决策记录** | `learning_decision_records` <br>(SQLite 数据表) | 严肃教学系统 | 长期记录用户在习得概念过程中的证据 (`evidence`)、推论 (`implications`) 与迭代溯源 (`superseded_by`)。 | ❌ 严禁称作“修炼心得簿”或“悟道记”。 |
| **最近发展区难度追踪** | `course_progress` <br>(SQLite 数据表中的 ZPD 指标) | 严肃教学系统 | 基于 Vygotsky 最近发展区理论 (ZPD)，追踪用户对知识点的掌握曲线与挑战适配度。 | ❌ 严禁称作“破境等级”或“道行进度”。 |
| **实操编程沙盒空间** | `data/materials/Sandbox/` <br>(本地隔离目录) | 严肃教学底座 | AI 导师唯一授权可使用 `replace_file_content` 进行文件创建与题库演进的安全受控沙盒。 | ❌ 严禁称作“练功房”或“炼丹炉”。 |
| **流式事件传输协议** | `SSE (Server-Sent Events)` <br>(FastAPI `/chat/stream`) | 严肃底层架构 | 前后端进行实时打字机流式通讯与控制帧传输的单向长连接传输标准。 | ❌ 严禁称作“飞剑传音”。 |
| **静态系统预设** | `static_sys` / `role: system` | 严肃底层架构 | 处于会话最顶部的静态角色设定、教学规则与系统守则。 | ❌ 严禁混淆称为“系统提示词全局”或与最终组装报文混为一谈。 |
| **动态尾部夹层** | `tail_injection` | 严肃底层架构 | 由 `ContextManager` 在每次发包前实时追加至物理末端（末尾 User 消息或待机容器中）的动态上下文块，包含 `<current_time>` 与 RAG 切片。 | ❌ 严禁称作“小尾巴”、“系统尾缀”或与静态预设混淆。 |
| **实时组装报文视窗** | `Assembled Context Payload` <br>(`/api/chat/system_context`) | 严肃底层架构 | 经过洗净、单发示教与尾部夹层组装后，最终全量发往大模型 API 交互的完整会话报文展现。 | ❌ 严禁简称为“系统预设提示词”，避免让用户误以为仅包含顶部规则。 |
| **跨智能体协同网关桥接** | `call_openclaw_agent` / `<openclaw_gateway_status>` | 严肃底层架构 | 负责向外部 OpenClaw 智能体实例分派任务与状态探测的通用桥接协议 (`Inter-Agent Gateway Bridge`)。 | ❌ 严禁在底层架构中带有角色昵称或泛化为模糊称谓。 |
| **角色状态机与心流引擎** | `CSM 状态机` <br>(人设提示词组装部分) | 虚拟角色扮演 | 驱动 AI 导师根据当前语境呈现适宜教学语气（如严厉、温和、激将）的心流引导机。 | 属于人设层，允许在 prompt 模板中阐述情景。 |
| **师生亲密度参数** | `affection` <br>(SQLite `affection` 表) | 虚拟角色扮演 | 隐蔽在后台折算用户交互积极性与反馈好感度的数值变量。 | 属于人设层，允许在提示词注入中使用。 |

---

## 二、 命名一致性自检清单 (Naming Consistency Checklist)

进行任何新增模块或数据库 Schema 迁移 (`Migration`) 时，执行以下检验：
1. **类名 / 表名是否直接采用表中的物理源码符号？** （例如必须用 `learning_decision_records`，禁止缩写为 `ldr_tbl`）。
2. **测试用例名称是否清晰展现业务意图？** （例如 `test_replace_file_content_sandbox_boundary`）。
3. **架构决策文档 (ADR) 是否全量执行技术用语？** （凡在 `docs/architecture/` 中的文档，禁止带有小说叙事词汇）。

---

## 三、 核心架构核心类与深模块词汇 (Core Architecture Definitions)

- **CharacterState (`CharacterState`)**：虚拟角色的动态数值模型，涵盖好感度 (`Affection`)、格局修养 (`Social Status`)、为人处世 (`Social Skills`) 及生理不应期 (`Refractory Period`)。
- **CharacterStateManager (`backend/services/character_state_manager.py`)**：负责角色数值状态跃迁、边界限制 (0-100) 及 SQLite 持久化的深模块 (`Deep module`)。抛出明确的 `CharacterStateError` 异常而非静默吞下。
- **ActionRegistry 与 Side-Effect Handlers**：无状态副作用拦截处理器（如 `PropertyUpdateHandler`、`CourseManagerHandler`）统一注册于单例 `ActionRegistry` 中，由 `ResponsePipeline` 在流式生命周期中集中拦截捕获与执行。

---

## 四、 上下文管线与尾部夹层通用语言规范 (Context Pipeline Ubiquitous Language)

> **对齐标准**：根据 `/ubiquitous-language` 规范，解决用户交互界面中“系统提示词”语意模糊与重载问题。

### 1. 术语定义与辨析表 (Terminology Definition & Anti-Aliases)

| 规范术语 (Canonical Term) | 核心定义 (Tight Definition) | 避免使用的歧义词/同义词 (Aliases to avoid) |
| :--- | :--- | :--- |
| **静态系统预设 (Static Persona Prompt)** | 仅指放置于对话首条 (`role: system`) 的角色设定、教学规则与系统常量。 | 系统提示词、全局预设、System Prompt (模糊泛指时) |
| **动态尾部夹层 (Dynamic Tail Injection)** | 在发包前追加至对话物理末端的上下文感知块，整合时间戳、RAG 检索片段与底层防错指针。 | 尾部提示词、小尾巴、最后的话、系统尾缀、上下文尾部 |
| **实时组装报文视窗 (Assembled Context Payload)** | 前端弹窗展示的、由后端 `ContextManager` 最终组装完毕发往大模型 API 的完整对白报文快照。 | 完整系统提示词、系统预设预览、System Prompt Preview |
| **待机轮次容器 (Standby Turn Container)** | 在 AI 回合完结后、用户提问前，为承载尾部夹层而在末尾独立构造的临时 `user` 角色占位卡片。 | 空问答、占位符、假消息 |

### 2. 概念关系声明 (Relationships)
- 一个 **实时组装报文视窗** 由恰好一个 **静态系统预设** 和零个或多个历史对白回合组装而成。
- 每次发包构建时，**动态尾部夹层** 必须严格附着在物理列表的末尾：若末尾是真实提问则追加其后；若末尾是 AI 回答完结状态，则独立封装在 **待机轮次容器** 中。

### 3. 开发者与领域专家典型对话 (Example Dialogue)

> **Dev:** "点击前端的‘查看当前完整系统提示词’按钮时，返回的其实是 **实时组装报文视窗 (Assembled Context Payload)** 对吗？"  
> **Domain expert:** "没错。以前叫它‘系统预设提示词’是严重语意重载（Overloaded term），会让用户误以为里面只有顶部的 **静态系统预设 (Static Persona Prompt)**。"  
> **Dev:** "难怪用户在 QA 时问‘怎么看底部的上下文尾缀’。只要把弹窗重命名为 **实时组装报文视窗**，用户就知道滑动到最底端能实时检查 **动态尾部夹层 (Dynamic Tail Injection)** 了。"  
> **Domain expert:** "正是如此。如果在 AI 回合刚完结时打开视窗，最底部的夹层还会独立包装在一个干净的 **待机轮次容器 (Standby Turn Container)** 中，绝不会割裂历史提问。"

### 4. 标识出的歧义与解决决策 (Flagged Ambiguities)
- **“系统提示词 (System Prompt)”语意重载**：长期以来，开发人员与用户把“顶部静态规则 (`role: system`)”和“发给大模型的最终全量组装报文”都统称为“系统提示词”。这导致了严重认知解耦——用户以为预览弹窗里没有尾部注入。**决策**：正式拆分为**静态系统预设**、**动态尾部夹层**和**实时组装报文视窗**三个互斥的领域词汇，并在 UI 弹窗与后端注释中全量更名对齐。
