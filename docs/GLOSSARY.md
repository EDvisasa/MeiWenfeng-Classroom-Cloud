---
id: DOC-GLOSSARY
title: 全局领域通用语言字典
status: active
created: 2026-07-04
updated: 2026-09-09
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
| **动态示教报文** | `Dynamic One-Shot Demonstration` <br>(`get_one_shot_demonstration`) | 在 `assemble_messages` 第 2 步中，对首轮真实开场白外层动态包裹 `<think>`、`<monologue>` 与 `<property_update>` 的格式规范范本。**必须原封不动透传真实对白本体**，确保模型习得输出契约且不丢失当前生活化情境。 | ❌ 严禁称作“静态单发”、“写死示例”或模糊单字“one-shot”。 |
| **待机轮次容器** | `Standby Turn Container` | 在 AI 回合完结后、用户发起下一轮提问前，为承载动态尾部夹层而在末尾独立构造的临时 `user` 角色占位消息。 | ❌ 严禁称作“假消息”、“空问答”。 |
| **实时组装报文视窗** | `Assembled Context Payload` <br>(`/api/chat/system_context`) | 经由动态示教、窗口截断及尾部夹层组装完毕后，最终发往大模型 API 交互的完整会话报文快照。 | ❌ 严禁简称为“系统预设”，必须体现这是发包快照全量。 |
| **会话压缩分水岭** | `compact_cutoff_id` <br>(SQLite `chat_sessions` 表列) | 会话上下文提炼浓缩时的物理分水岭指针。分水岭之前历史对白收敛为结构化提要，分水岭之后保留近期真实轮次。 | ❌ 严禁称作“截断标记”或“清理点”。 |
| **结构化前情提要** | `<compact_summary>` <br>(Prompt 标签) | 由 Auto-Compact 或 `/compact` 提炼的多角色（阿冯/吻锋/小白/关键共识）长记忆浓缩块，锚定于历史对白最前端。 | ❌ 严禁称作“历史大纲”或与 RAG 检索证据混淆。 |
| **当前用户指令沙箱** | `<current_user_instruction>` <br>(Prompt 标签) | 在动态尾部夹层中严格物理隔离与包裹当前轮次真实用户提问的独立标签，彻底阻断大模型将 RAG 历史当成当前指令。 | ❌ 严禁与历史问答直接平铺混排。 |
| **记忆召回防伪归档区** | `<retrieved_past_memory_archives>` / `<recent_journal_summaries>` | 在动态尾部夹层中盛放 RAG 与日记历史的独立只读标签，携带显式防伪警告，防止模型误认为当前实时发言。 | ❌ 严禁直接无标记插入用户对白。 |
| **流式事件传输协议** | `SSE (Server-Sent Events)` <br>(FastAPI `/chat/stream`) | 前后端打字机流式输出与状态帧传输的单向长连接通信协议。 | ❌ 严禁称作“飞剑传音”等叙事虚构词汇。 |

### 1.2 教学处理与调度控制术语 (Teaching Control & Sandbox)

| 规范业务概念 (Ubiquitous Term) | 物理源码/表符号 (Code Symbol) | 核心概念定义 (Authoritative Definition) | ❌ 绝对禁止的混淆表达 (Prohibited Terms) |
| :--- | :--- | :--- | :--- |
| **斜杠指令处理器** | `SlashHandler` <br>(`backend/services/slash_handler.py`) | 负责路由并执行 `/lesson`, `/submit`, `/set_mission`, `/plan`, `/qa`, `/compact` 等教学动作的后端引擎类。 | ❌ 严禁称作“法阵调度员”或“咒语路由器”。 |
| **学习决策记录** | `learning_decision_records` <br>(SQLite 数据表) | 结构化记录用户对知识要点的掌握证据 (`evidence`)、推论 (`implications`) 与溯源 (`superseded_by`)。 | ❌ 严禁称作“修炼心得簿”。 |
| **最近发展区难度追踪** | `course_progress` <br>(SQLite ZPD 指标列) | 依据最近发展区理论 (ZPD)，对用户学习难度与掌握度进行自适应评估与跟踪的指标体系。 | ❌ 严禁称作“破境等级”或“道行”。 |
| **实操编程沙盒空间** | `data/materials/Sandbox/` <br>(受控工作区) | AI 导师唯一被授权操作代码创建与演练示例输出的隔离文件目录。 | ❌ 严禁称作“炼丹炉”或“练功房”。 |
| **跨智能体协同网关桥接** | `call_openclaw_agent` / `<openclaw_gateway_status>` | 负责向外部 OpenClaw 智能体网关分派任务及健康状态探测的连接通道 (`Inter-Agent Gateway Bridge`)。 | ❌ 底层类或接口严禁带角色昵称。 |

### 1.3 虚拟角色扮演与人设数值演化术语 (Roleplay Persona & Character Mechanics)

| 规范业务概念 (Ubiquitous Term) | 物理源码/表符号 (Code Symbol) | 核心概念定义 (Authoritative Definition) | 容忍度 / 规范说明 |
| :--- | :--- | :--- | :--- |
| **角色心流与状态机** | `CSM 状态机` | 驱动角色根据场景变换语气态度（温和/严厉/激将）的心流决策逻辑。 | 允许在人设提示词或剧情会话中体现。 |
| **师生亲密度参数** | `affection` <br>(SQLite `affection` 表) | 衡量用户互动频度与好感反馈程度的后台隐蔽参数（分 Stage 1~4 四阶，受每日净增上限与离线衰减约束）。 | 属于角色扮演层变量。 |
| **动态属性跃迁标签** | `<property_update>` <br>(模型输出 XML 自闭合协议) | 大模型在对白末尾携带的标准化状态增量契约（含 `affection_delta`, `refractory_delta`, `social_status_delta`, `social_skills_delta`）。 | ❌ 严禁称作“加分指令”或“角色变量回调”。 |
| **时间自然衰减与缓冲期** | `Temporal Decay & Buffer Grace Period` <br>(`backend/services/side_effects.py`) | 依据用户离线自然天数计算的好感衰退机制。在各阶对应的豁免缓冲期（2~7天）内不扣分，超期后按天衰减。 | ❌ 严禁称作“好感掉级”或“无底线清零”。 |
| **阶数跌落保底** | `Affection Stage Floor Guarantee` <br>(`STAGE_FLOOR_LIMITS`) | 好感衰减算法中的防崩塌铁律：无论离线多久，好感度**至多只退一阶**，且停滞在该阶最低保底值（65/40/20/10）。 | ❌ 严禁称作“掉段锁死”。 |
| **破冰保护期与暴击补偿** | `Ice-Breaking Warm-Up & Critical Bonus` <br>(`ice_breaking_turns`) | 发生阶数衰减后触发的 2 轮破冰过渡态。互动享受翻倍暴击与 +3 破冰补偿分，且豁免单日增量上限。 | ❌ 严禁称作“新手加成”或“补偿包”。 |
| **单日好感净增上限** | `Daily Affection Net Cap` <br>(`MAX_DAILY_NET_GAIN = 3`) | 日常非破冰状态下，单日好感净增至多 +3 点，次日自然刷新，防止高频短对话刷屏溢出。 | ❌ 严禁称作“防沉迷”或“经验锁”。 |
| **笛卡尔积开场白编排引擎** | `Combinatorial Ambient Greeting Engine` <br>(`backend/services/greeting_service.py`) | 由好感阶段(A) × 现实时段(B) × 久别重逢状态(C) × 原版行为池(D) 四维正交空间构成的零 Token、零延迟生活化开场白生成器。 | ❌ 严禁称作“随机问候机”或“随机话术库”。 |
| **槽位填充开场白模板** | `Slot-Filling Greeting Template` | `*（[时段衣着]，正[独处行为]。[过渡面相]）*“[首句台词]”` 的严谨角色生活化动作组装语法。 | ❌ 严禁称作“字符串拼接”。 |
| **原版生活行为池** | `Persona Vignette Pool` <br>(`ORIGINAL_VIGNETTES`) | 深度挖掘自 61KB 原版人设（《桃花扇》对戏、螺子黛画眉、缝制红狐玩偶、软榻压腿做臀桥等）的 38 种日常真实行为切片集合。 | ❌ 严禁称作“日常动作列表”。 |

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
- **ActionRegistry 与 Side-Effect Handlers**：管理流式响应生命周期中的无状态副作用处理逻辑（如动作快照、课表同步、自然衰减）。

---

## 三、 概念关系声明与通用语言实践 (Relationships & Ubiquitous Dialogue)

### 3.1 报文组装概念结构关系
- 一个 **实时组装报文视窗 (Assembled Context Payload)** 恒等于：
  `恰好一个静态系统预设 (Static Persona Prompt)`
  + `[可选] 结构化前情提要 (<compact_summary>)`
  + `动态示教报文 (Dynamic One-Shot Demonstration) [首轮真实对白保留 + 规范外包]`
  + `历史多轮真实对白切片 (Recent Dialogue Turns)`
  + `附着在物理末端的动态尾部夹层 (Dynamic Tail Injection) [含 <current_user_instruction> 与 <retrieved_past_memory_archives>]`
- 动态尾部夹层的附着位置规则：若报文末尾属于用户真提问，直接追加在提问文本上方；若报文末尾属于 AI 刚回答完毕，则额外封装在一个 **待机轮次容器 (Standby Turn Container)** 中。

### 3.2 团队协作通用语言实践沟通示例
> **Dev:** "点击前端的‘查看当前完整系统提示词’按钮时，返回的其实是 **实时组装报文视窗 (Assembled Context Payload)** 对吗？"  
> **Domain expert:** "没错。以前叫它‘系统预设提示词’是严重语意重载，会让大家误以为里面只有顶部的 **静态系统预设 (Static Persona Prompt)**。"  
> **Dev:** "难怪 QA 问‘怎么看底部的上下文尾缀’。将页面和后端变量统一为 **实时组装报文视窗** 后，大家就清楚滚动到底部能查验 **动态尾部夹层 (Dynamic Tail Injection)** 了。"  
> **Dev:** "既然是发给大模型的范例，为什么不直接叫它 One-Shot，而一定要叫 **动态示教报文 (Dynamic One-Shot Demonstration)** 呢？"  
> **Domain expert:** "如果简称为模糊的 One-Shot，开发者或后续接入的智能体会以为里面是一个‘写死的问答模板字符串’，从而在发包时把真实生成的个性化开场白直接抹除掉；或者与底层一次性子任务智能体 (One-Shot Agent) 混淆。叫 **动态示教报文**，能清晰传达‘必须保留首轮对白真实情境，仅在动态外层加装标签’的架构约束。"

---

## 四、 命名一致性自检清单 (Naming Consistency Checklist)

进行新模块研发或 Schema 迭代时，须按照下述清单进行合规检查：
1. **类名/数据库字段名**是否与**表一**物理映射保持绝对一致？（例如数据库记录表统一以 `learning_decision_records` 命名，不得私自构造别名）；
2. **系统引导与提示词**是否符合英文凝练原则（禁止向 AI 提示词泄露“管线/夹层”等开发者架构术语）；
3. **架构文档 (ADR)** 是否完全剔除叙事修辞，采用严谨的工程通用用语？
