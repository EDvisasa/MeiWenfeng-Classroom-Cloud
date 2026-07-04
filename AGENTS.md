# 🤖 智能体与工程协作宪法及自动寻址路由表 (Agent Handover & Skill Routing Bridge)

> **生效日期**：2026-07-04  
> **适用范围**：任何连接至本仓库 (`MeiWenfeng-Classroom`) 的 AI 智能体（包括但不限于 Antigravity IDE、Claude Code、Cursor、Windsurf 等）以及人类接手开发者。  
> **核心定位**：本文件是智能体进入项目工作区时的**最高优先级宪法与寻址路由表**。解决通用技能（Skills）与项目具体物理文件路径的自动对齐问题。

---

## 一、 智能体技能寻址路由表 (Skill-to-Path Routing Matrix)

当智能体在会话中触发相关具体任务或挂载通用 Skills 时，**强制且只能寻址并读写以下约定的项目目标文件**，严禁凭空猜想路径或创建临时碎片文件：

| 触发的业务场景 / 通用 Skill | 目标工程路径 (Target Path) | 核心读写规范与职责 |
| :--- | :--- | :--- |
| **通用领域词汇校验** <br>`ubiquitous-language` / `domain-modeling` | [`docs/GLOSSARY.md`](file:///d:/MeiWenfeng-Classroom/docs/GLOSSARY.md) <br>*(最高词汇标准)* | 全局唯一的通用语言与系统术语映射表。对任何数据表、类名或核心逻辑建模前，强制读取校验领域词汇合法性。 |
| **系统架构决策查阅/记录** <br>`decision-mapping` / `codebase-design` | [`docs/architecture/`](file:///d:/MeiWenfeng-Classroom/docs/architecture) <br>*(单文件 HTML ADRs)* | 存放已审定列装的架构决策记录。严格遵守单文件可双击运行 HTML 规范及“Before/After 语义防误导提示词屏障”。 |
| **待办任务领取与新工单拆解** <br>`to-issues` / `to-prd` / `request-refactor-plan` | [`docs/planning/01_sprint_tasks.md`](file:///d:/MeiWenfeng-Classroom/docs/planning/01_sprint_tasks.md) | 活文档冲刺跟踪表。每个待办任务必须保持标准四要素工单结构（User Story / Affected Files / Acceptance Criteria / Verification Command）。 |
| **开发规范与单测执行** <br>`tdd` / `diagnosing-bugs` | [`docs/01_dev_and_test_guide.md`](file:///d:/MeiWenfeng-Classroom/docs/01_dev_and_test_guide.md) <br>[`backend/tests/`](file:///d:/MeiWenfeng-Classroom/backend/tests) | 开发前与排错前的必读指南。改动后端逻辑前、中、后，强制执行指定的 `pytest` 测试脚本以保证回归绿灯。 |
| **交互式缺陷排查与记录** <br>`qa` | [`docs/planning/bug-tracker.md`](file:///d:/MeiWenfeng-Classroom/docs/planning/bug-tracker.md) | 交互式 QA 会话或发现新 Bug 时，将缺陷现象、调查方向与复现步骤标准记入缺陷追踪榜。 |
| **前端 UI 设计与自动化测试** <br>`frontend-design` / `webapp-testing` | [`frontend/src/`](file:///d:/MeiWenfeng-Classroom/frontend/src) <br>*(Playwright E2E)* | 负责 React 交互卡片（如 `ChatPanel`、`QuizBlock`）的设计规范落地与页面端到端测试。 |
| **文档创建与格式审计** <br>`doc-coauthoring` / `review` | [`docs/00_doc_guidelines.md`](file:///d:/MeiWenfeng-Classroom/docs/00_doc_guidelines.md) | 规范文档层级分类、生命周期流转规约（特别是 `reports/` 到 `architecture/` 的升格淘汰机制）。 |
| **安全沙盒文件演进操作** <br>底层工具安全边界 (`replace_file_content`) | [`data/materials/Sandbox/`](file:///d:/MeiWenfeng-Classroom/data/materials/Sandbox) | AI 导师为用户布置实操练习、修改作业代码的唯一授权沙盒空间。受底层路径锁严格防护。 |

---

## 二、 文档格式与操作权限核定矩阵 (Document Operation Matrix)

> **全库唯一权威定义 (SSOT)**：各级文档的生命周期流转、允许与严禁的操作，请查阅完整核定表：[`docs/00_doc_guidelines.md #五、智能体自动化寻址与文档操作核定矩阵`](file:///d:/MeiWenfeng-Classroom/docs/00_doc_guidelines.md)。

---

## 三、 双系统领域物理隔离铁律 (Dual-System Terminology Iron Law)

> **全库唯一权威定义 (SSOT)**：关于严肃教学底座与角色扮演系统用词界限及表名黑名单，请强制遵守字典表：[`docs/GLOSSARY.md`](file:///d:/MeiWenfeng-Classroom/docs/GLOSSARY.md)。

---

## 四、 自动化交接自检确认协议 (Handover Check Protocol)

任何智能体在处理本工程新会话或任务时，承诺先执行以下内心自检：
1. **是否认清任务归属？** -> 翻阅 `docs/planning/01_sprint_tasks.md` 锁准具体目标卡片；
2. **是否掌握词汇标准？** -> 遇核心类/数据表名，校验 `docs/GLOSSARY.md`；
3. **是否跑通安全测试？** -> 提交代码前，执行 `pytest` 确保无任何安全与接口回归。
