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
