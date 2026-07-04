---
id: DOC-00
title: 文档规范与命名总纲
status: active
created: 2026-06-27
domain: core-architecture
---
# 文档规范与命名总纲 (Documentation Standards)

> **生效日期**：2026-06-27  
> **适用范围**：本仓库 `docs/` 目录下所有当前及未来新建的文件与子文件夹。  
> **核心宗旨**：消除命名混乱、分隔符混用与文档堆砌，构建面向 AI 友好 (AI-Native) 的清晰、严谨、隔离的文档知识体系。

---

## 一、 目录架构层级划分 (Directory Structure)

系统严格划分为**工程研发文档 (`docs/`)**与**用户学习数据 (`data/materials/`)**两大物理隔离空间，严禁将两者混搭堆叠：

### 1. 工程研发与系统规范 (`docs/`)
| 目录路径 | 核心定位 | 存放内容说明 |
| :--- | :--- | :--- |
| **`docs/` (根目录)** | **全局指引** | 仅放置全局性的标准规范与开发操作指南（如本文档及 `01_dev_and_test_guide.md`）。 |
| **`docs/planning/`** | **路线规划与冲刺** | 存放路线图大纲（Roadmap）、当前开发任务清单（Sprint Tracker）、子项架构设计方案等动态演进的规划文档。 |
| **`docs/architecture/`** | **系统架构决策 (ADRs)** | 存放长期生效、经评审通过的可视化架构决策记录（Architectural Decision Records）。**全量统一为单文件 `.html` 格式，不再保留冗余 `.md` 文件。** |
| **`docs/reports/`** | **分析与测试报告** | **合并收纳**原有的 `analysis/` 目录及散落在各处的静态 `.html` 报告（如测试覆盖率、Bug 分析、架构自动扫描报告）。实现核心规范与静态快照彻底隔离。 |

### 2. 用户私密学习资产与课堂物料 (`data/materials/`)
| 目录路径 | 核心定位 | 存放内容说明 |
| :--- | :--- | :--- |
| **`data/materials/References/`**| **理论讲义卡片 (一文)** | 存放 AI 导师拦截 `<explainer>` 标签时实时生成的理论备忘录与知识小结卡片，在前端 UI 树和本地 RAG 检索中使用。**受底层 `.gitignore` 全量屏蔽，100% 仅存本地，严禁同步上云。** |
| **`data/materials/Sandbox/`** | **教学实操沙盒 (一武)** | AI 导师为用户布置编程作业、排错练习题的唯一授权修改沙盒。**受底层 `.gitignore` 全量屏蔽，严禁同步上云。** |
| **`data/materials/Lessons/`** | **课程大纲与交互关卡** | 存放系统预置或动态生成的课程章节与学习关卡数据。**受底层 `.gitignore` 全量屏蔽，严禁同步上云。** |
| **`data/materials/LDRs/`** | **学习决策记录** | 记录用户的“Anti-Journaling”学习反馈与学习状态跟踪数据。**受底层 `.gitignore` 全量屏蔽，严禁同步上云。** |

---

## 二、 面向 AI 友好的文件命名与格式铁律 (AI-Native Naming & Formats)

所有文档必须严格遵循以下命名约定与元数据格式，确保跨操作系统的可排序性、脚本正则可匹配性与 AI 智能体低消耗提取：

### 1. 强制 YAML Frontmatter 元数据块 (Machine-Parsable Metadata)
所有存放在 `docs/` 下的 Markdown 文档（特别是在 `planning/` 和根目录下），**必须在其前 10 行内包含标准的 YAML Frontmatter 头部**。这样智能体在寻址和构建图谱检索时，可极速读取 `id`, `title`, `status`, `domain` 等属性，无需消耗大量 Token 读取正文。例子：
```yaml
---
id: DOC-GUIDELines
title: 开发与测试指南
status: active
created: 2026-06-27
domain: core-architecture
---
```

### 2. 序列化 / 编号类物理文件命名 (Planning & ADRs)
对于具有顺序、层级或唯一编号的文档，统一采用 **`编号_ASCII短横线/下划线.[扩展名]`** 格式：
- **规划类 (`.md`)**：强制使用数字编号 + 纯小写 ASCII 英文短横线/下划线命名，例如：
  - `00_project_roadmap.md`
  - `01_sprint_tasks.md`
  - `02_learning_engine_arch.md`
  - **【AI 与跨系统友好铁律】**：物理文件名必须采用纯英文 ASCII 小写短横线/下划线命名（如 `bug-tracker.md`、`01_sprint_tasks.md`），而将中文完整主题名称展示在文件内部的 YAML Frontmatter 头部与 H1 标题中，彻底消除 CLI 命令与 AI 工具在不同操作系统下的多字节转义摩擦。
- **架构决策记录 ADR (`.html`)**：统一采用 `ADR-三位数字编号_主题简写.html` 格式，例如：
  - `ADR-001_web_search_and_pagination.html` 或保持既定简写。
- **🚫 禁止项**：严禁在物理文件名中使用中文及特殊字符；严禁在编号连接符上混用破折号与下划线。

### 3. 常规指南与系统说明文档
使用清晰的纯英文 ASCII 核心词汇命名，词与词之间使用连字符 `-` 或下划线 `_`：
- 例如：`01_dev_and_test_guide.md`、`CHANGELOG.md`、`bug-tracker.md`。

### 4. 自动化生成报告 (Reports)
所有自动化工具、脚本或 AI 生成的静态 HTML 分析页面，强制移入 `docs/reports/` 目录，并采用以下格式：
- `简明主题_report.html` 或 `简明主题_analysis.html`。
- 例如：`agent_bug_analysis.html`、`architecture_verification_report.html`。

---

## 三、 文档归纳与去重准则 (Pruning & Deduplication)

1. **一事一档原则**：同一个技术决策或模块设计，只能存在一个具体的终极归属文档。如果发生架构迭代，必须直接在原文档修改或标记废弃，严禁创建内容重复、命名略异的冗余文件（例如重叠的 `ADR-001` 与 `ADR-002`）。
2. **及时归档与清理**：临时调试分析生成的阶段性文档或残缺笔记，在阶段任务结束验收后，应提炼核心结论汇入 `planning/` 主任务清单，并将临时文件无情清理。
3. **未暂存统一提交**：文档整理工作遵循“先在工作区完成分类整理与重命名验证，确认无误后再统一 commit”的流程。

---

## 四、 架构资产生命周期与 HTML 报告规约 (Architecture Asset Lifecycle)

为兼顾**人类浏览器直观阅读**与**AI高信噪比代码结构分析**，系统架构资产实行**“单文件可视化架构规范制”与动态闭环生命周期**：

### 1. 单文件可视化 ADR 规约与布局模板
- **系统拓扑与规约集成**：对于列装生效的架构决策记录 (ADRs)，统一采用基于 Matt Pocock 理念的单文件 HTML 架构报告（Tailwind CSS + Mermaid CDN 渲染）。**`docs/architecture/` 目录仅保留 `.html` 格式文件，不再保留冗余 `.md` 文件。**
- **标杆级三段式布局结构（以 `ADR-001` 为模板标准）**：所有 ADR 文档必须严格包含顶部 Header 头部面板与以下三个标准 Section 章节，严禁偷工减料或仅贴流程图：
  1. **Header 面板**：包含 `Adopted (已落地列装)` 徽章、ADR 编号、决策时间、主题大标题、核心摘要说明及专属领域标签（Badge Row）。
  2. **Section 1: 背景与技术挑战 (Context & Challenges)**：配编号图标 `<div class="w-10 h-10 rounded-xl bg-red-100...">1</div>`，采用网格卡片清晰陈述旧架构的业务痛点与技术瓶颈。
  3. **Section 2: 决策方案与深模块解耦 (Decision & Solution)**：配编号图标 `<div class="w-10 h-10 rounded-xl bg-blue-100...">2</div>`，使用左侧彩边说明卡片 (`border-l-4`) 拆解核心设计与解耦要点，并在下方附上左右分栏的 **Before vs After 拓扑流程对比图**。
     - **🛡️ AI 防误导语义屏障铁律 (Anti-Hallucination Guardrail)**：为防止 AI 在 RAG 切片检索或长文本阅读时被旧架构（Before）误导，所有 Before / After 模块必须加入机器可读的语义隔离标签与注释：
       - **Before 模块**：容器必须带红色警告视觉，且在 Mermaid 代码首行强制添加注释 `%% DEPRECATED / HISTORICAL PATTERN (DO NOT USE)`，明确标识为已废弃历史。
       - **After 模块**：容器必须带绿色现行视觉，且在 Mermaid 代码首行强制添加注释 `%% ACTIVE / AUTHORITATIVE IMPLEMENTATION`，引导 AI 锚定唯一现行标准。
  4. **Section 3: 后果与架构评估 (Consequences & Evaluation)**：配编号图标 `<div class="w-10 h-10 rounded-xl bg-emerald-100...">3</div>`，列举架构列装后的正向收益与边界评估。

### 2. 卡片升格流转流程 (In-Place Transformation Flow)
所有系统架构的分析与改进遵循严格的生命周期流转：
1. **候选摩擦期 (`docs/reports/`)**：当发现架构偶合、Bug 或重构机会时，生成 HTML 报告置于 `reports/` 下。
2. **重构落地期**：手术刀修改代码并执行自动化测试验证。
3. **升格列装期 (`docs/architecture/`)**：在原 HTML 文件中将推荐卡片状态从“摩擦候选 (Candidate)”更新为“已落地列装 (Adopted)”，刷新 After 拓扑图至真实代码状态，并**通过 `git mv` 移入 `docs/architecture/` 作为永久可视化架构蓝图归档，同时自 `reports/` 中移除**。

### 3. 专属领域标签集 (Badge Row Extensions)
在 HTML 报告卡片的 Badge row 中，除通用标签（如 `Strong`, `in-process`）外，强制启用本教学引擎专属标签：
- `LLM-Prompt-Injection`：人设与系统提示词注入拦截
- `Sandbox-Evolving`：用户测验练习沙盒动态演进
- `RAG-Vector-Indexed`：知识库卡片向量化索引
- `ZPD-Adaptive`：最近发展区难度自适应跟踪
- `DB-Transaction`：核心数据库事务闭环

### 4. 双系统领域用词物理隔离铁律 (Domain Terminology Separation)
本工程由两个核心子系统交织而成，在代码注释、系统日志、架构决策记录 (ADR) 与官方技术文档中，严禁用词混淆，必须严格恪守以下领域界限（全量权威映射与黑名单请强制查阅字典表：[`docs/GLOSSARY.md`](file:///d:/MeiWenfeng-Classroom/docs/GLOSSARY.md)）：
1. **角色扮演系统 (Roleplay Persona System)**：涉及人物模拟与虚拟互动属性（如 `CSM 状态机`、`好感度 (affection)`、`阶位 (social_status)`、`角色提示词` 等），属于人设模拟器的领域参数，允许使用此类专属属性用词。
2. **严肃教学与底座架构系统 (Serious Teaching & Core Architecture System)**：涉及教学流程、课程讲义、管线拦截、异步I/O与系统路由，必须严格使用**现代、准确、高效、凝练的技术软件工程术语**（如 `讲义 Markdown 文件持久化`、`结构化参考文档`、`SSE 流式生成`、`架构决策记录 (ADR)`）。**严禁**在技术系统架构阐述中使用任何国风修仙、虚拟魔法或小说叙事化的词汇（例如将文件称为“玉简”，将架构文档称为“法典”等）。

---

## 五、 智能体自动化寻址与文档操作核定矩阵 (Agent Routing & Document Operation Matrix)

为彻底打通跨 IDE 环境与大模型技能（Skills）之间的桥梁，全库实施**“先确立权限与验证规约，再核定修改”**准则。智能体进入本工程时，自动遵循项目根目录全局寻址枢纽 [`AGENTS.md`](file:///d:/MeiWenfeng-Classroom/AGENTS.md)，并对各级文档遵守以下操作权限表：

| 文档层级 | 物理路径说明 | 对照管理 Skill | 允许的操作 (Allowed Operations) | 严禁的操作 (Prohibitions) | 操作核定条件 (Verification) |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **全局宪法** | `docs/00_doc_guidelines.md`<br>`docs/01_dev_and_test_guide.md`<br>`AGENTS.md` | `ubiquitous-language`<br>`doc-coauthoring` | ✅ **严谨修订**：增补通用语言字典、更新单测指引或强化安全护栏。 | ❌ **严禁私自放宽标准**：严禁放宽用词隔离铁律或删除已有安全验证提醒。 | 修改后全栈执行 `pytest backend/tests/test_agent_tools.py` |
| **不可变决策** | `docs/architecture/*.html` | `decision-mapping`<br>`codebase-design` | ✅ **只能新增 / 状态追加**：新架构生成 HTML 放入；或在旧文件头标记已废弃。 | ❌ **严禁历史篡改**：严禁直接涂改过去的已落地架构拓扑与历史决策。 | 符合单文件 HTML 三段式模板规则 |
| **动态任务榜** | `docs/planning/01_sprint_tasks.md` | `to-issues`<br>`request-refactor-plan` | ✅ **高频迭代**：按标准工单结构追加新卡片；完成任务打钩 `[x]` 并归档。 | ❌ **严禁长篇大论**：严禁在待办清单中写入长篇理论设计，长篇设计请走 ADR。 | 对应具体任务卡片中声明的单测命令 |
| **分析缓冲期** | `docs/reports/*.html` | `triage`<br>`diagnosing-bugs` | ✅ **临时存查**：存放排错分析报告；落地后转为 ADR 或直接删除。 | ❌ **严禁永久滞留**：严禁让 `reports/` 堆满无人清理的过期 HTML。 | 阶段任务结束验收时清理或升格 |
| **用户隔离区** | `data/materials/Sandbox/` | 底层路径防护栏<br>`replace_file_content` | ✅ **仅在练习时受控读写**：AI 仅可在授课与批改环节修改此目录下文件。 | ❌ **严禁写坏边界**：受 `.gitignore` 屏蔽，严禁越界修改或上云。 | 强制通过 `pytest backend/tests/test_agent_tools.py` 校验 |

