---
id: PLAN-04
title: 课题驱动的多课程隔离架构与课时授课闭环 (Course-Mission Driven Isolated Knowledge & Lesson System)
status: draft
created: 2026-11-13
domain: core-architecture
---

# 课题驱动的多课程隔离架构与课时授课闭环 (PRD)

> **文档定位**：需求与系统架构升级规范 (Product Requirements Document & Architecture Specification)  
> **所属规划**：`docs/planning/01_sprint_tasks.md` (`ISSUE-61` ~ `ISSUE-65`) / `docs/planning/00_project_roadmap.md`  
> **通用语言对齐**：严格遵照 [`docs/GLOSSARY.md`](file:///d:/MeiWenfeng-Classroom/docs/GLOSSARY.md) 领域术语标准。角色扮演仅限上层情感表达，底层架构严禁使用黑名单词汇。

---

## 1. Problem Statement (问题陈述)

随着用户在伴读系统中开启不同学科与研究方向的学习（例如“Navier-Stokes 方程偏微分有限时间爆破理论”、“Rust 异步运行时内核”或“高并发后端实战”），当前系统暴露出了严重的架构瓶颈与知识交叉污染问题：

1. **目标设立与课程体系割裂（Decoupled Mission & Courses）**：
   用户在聊天中通过 `/set_mission` 确立宏大目标并签署契约后，系统将数据硬编码写入全局单例表 `user_mission (id=1)` 及物理路径 `data/materials/Settings/user_mission.md`。而知识档案库中的分课程管理（`courses/<course_id>/`）完全由用户手动在弹窗点击「新建课题」，两者互不感知、无法在设立目标后自动构建课程沙盒。
2. **多学科知识交叉污染（Cross-Course Knowledge Contamination）**：
   - **术语表全局混淆**：`<glossary>` 抽取的专业术语存放在无 `course_id` 区分的单一 `glossary` 数据表中。不同领域的同名或歧义概念（如在不同上下文中的同名符号、技术简称）相互覆盖或混杂；
   - **讲义与沙盒写穿到全局**：长文讲义拦截器（`ExplainerHandler`）和沙盒代码工具硬编码读写全局 `data/materials/References` 和 `Sandbox`，导致不同学科的教材与实操代码杂糅在同一目录下；
   - **RAG 向量检索无界扩散**：向量知识库检索统一面向全局数据集 `Classroom_Knowledge`，授课过程中经常检索出其他毫不相干学科的历史切片，降低了大模型思考推理的信噪比。
3. **缺乏课时化（Lesson Periods）编排与课程导向授课闭环**：
   目前的 `course_progress`（章节大纲）为全局单一列表，执行 `/lesson` 时无法指定进入特定学科课程，也无法按具体的“课时（Lesson 1, Lesson 2...）”与阶段（Phase）进行循序渐进的学情沉淀与 ZPD 动态调控。

---

## 2. Solution (解决方案)

构建**课题驱动（Course-Mission Driven）的多租户物理隔离与课时授课全闭环体系**：

```
+---------------------------------------------------------------------------------------+
|                                  /set_mission [目标描述]                               |
|                                             |                                         |
|                                (强力审问与约束拟定循环)                                    |
|                                             v                                         |
|                       <finalize_mission goal="..." course_id="..." ...>               |
+---------------------------------------------------------------------------------------+
                                              |
                     +------------------------+------------------------+
                     | 自动物理建卷与初始化                              | 数据层多租户绑定
                     v                                                 v
   data/materials/courses/<course_id>/                SQLite (classroom.db)
   ├── course.json                                    ├── courses (主表)
   ├── Settings/user_mission.md, glossary.json        ├── user_mission (course_id)
   ├── Lessons/ (课时化大纲与课件)                     ├── course_progress (course_id, lesson_no)
   ├── References/ (隔离讲义)                          └── glossary (course_id)
   ├── Sandbox/ (隔离实操沙盒)
   └── LDRs/ (隔离决策记录)
                     ^
                     | (课时授课回路)
+---------------------------------------------------------------------------------------+
|                                /lesson [course_id (可选)]                              |
|                                             |                                         |
|                  (锁定当前课题 -> 挂载隔离沙盒与专用 RAG Collection)                         |
|                                             v                                         |
|   1. 课时进度推进 (Lesson Period: 第 N 课时 / ZPD 追踪)                                   |
|   2. 术语抽取 (<glossary>) -> 隔离入本课程专用术语表                                      |
|   3. 讲义卡片 (<explainer>) -> 隔离入 courses/<course_id>/References/                   |
|   4. 沙盒演练 (create_file) -> 隔离在 courses/<course_id>/Sandbox/                       |
+---------------------------------------------------------------------------------------+
```

1. **`/set_mission` 自动建卷与挂载**：
   - 目标拟定闭环末尾（`<finalize_mission>`），系统根据目标语义自动生成安全合法且具可读性的 `course_id` 与展示名称，调用 `MaterialsManager.create_course(course_id, name)` 自动在磁盘创建完整 5 大目录与 `course.json`；
   - 契约内容直接落盘至 `data/materials/courses/<course_id>/Settings/user_mission.md`，并在 SQLite 中激活该课程为主课程。
2. **多学科存储与 RAG 向量全面隔离**：
   - **术语表隔离**：`glossary` 表增加 `course_id` 键，同时在课题 `Settings/glossary.json` 进行文件级镜像。AI 仅能感知当前激活课程的术语；
   - **讲义与沙盒隔离**：`ExplainerHandler`、`create_file`、`replace_file_content` 动态锚定到当前活动课程的 `courses/<course_id>/` 子目录；
   - **RAG 向量隔离**：知识库向量同步与检索根据 `course_id` 分区（以独立的 Collection 或严格的 Metadata 过滤 `course_id = active_course_id`），杜绝跨学科知识污染。
3. **课时化（Lesson Periods）大纲体系与 `/lesson` 授课锚定**：
   - `course_progress` 表增加 `course_id`、`lesson_no`（课时序号，如第 1 课时、第 2 课时）与 `title`，支持各课程独立的教学大纲与关卡进度；
   - `/lesson` 支持指定课程代号或沿用当前活跃课程，自动装配该课题的课时目标、专属沙盒与知识上下文展开授课教学。

---

## 3. User Stories (用户故事清单)

1. **US-01 (目标设立自动建课)**: As a learner, I want `/set_mission` to automatically create a dedicated course project directory in the knowledge library when I finalize my goal, so that I don't have to manually create folders and copy configuration files.
2. **US-02 (自适应语义命名代号)**: As a learner, I want the system to generate a meaningful, clean ASCII `course_id` based on my mission topic (e.g. `navier_stokes_finite_time`), so that the folder name is immediately recognizable.
3. **US-03 (课程目标隔离存储)**: As a learner, I want my mission contract and constraints to be saved specifically within `courses/<course_id>/Settings/user_mission.md`, so that different learning projects do not overwrite each other's goals.
4. **US-04 (活跃课程状态跟踪)**: As a user, I want the classroom system to maintain an active course pointer, so that all subsequent chats, status displays, and tools know which course is currently in progress.
5. **US-05 (指令切课进入课题)**: As a learner, I want to type `/lesson [course_id]` or choose a course from the UI to switch my active study project, so that the tutor immediately shifts focus to that specific course.
6. **US-06 (无参 `/lesson` 快速复课)**: As a learner, I want typing `/lesson` without parameters to resume the current active course's next pending lesson period, so that my daily study flow is friction-free.
7. **US-07 (隔离术语抽取)**: As an AI tutor, I want the `<glossary>` tag to insert terms specifically bound to the active `course_id`, so that technical jargon from one domain does not pollute or collide with terms in another domain.
8. **US-08 (隔离讲义文件落盘)**: As an AI tutor, I want `<explainer>` cards to be saved under `data/materials/courses/<course_id>/References/`, so that theoretical handouts stay cleanly organized inside their own course library.
9. **US-09 (隔离实操沙盒操作)**: As an AI tutor, I want file tools (`create_file`, `replace_file_content`, `read_file`) to operate inside `data/materials/courses/<course_id>/Sandbox/`, so that student exercises and test code are completely sandboxed per course.
10. **US-10 (RAG 向量检索无污染)**: As a system engineer, I want RAG vector retrieval in `context_manager` to only query chunks belonging to the current `course_id`, so that historical knowledge slices from other courses never leak into the prompt.
11. **US-11 (课时大纲分级管理)**: As an AI tutor, I want each course to have its own sequence of lesson periods (`lesson_no`, `phase`, `topic`, `status`), so that I can guide the learner through a structured multi-lesson syllabus.
12. **US-12 (单课时推进与系统放行)**: As a learner, I want `<system_pass>` to advance the progress of the active course's current lesson period, so that I can see my progress score and ZPD difficulty dynamically update for that course.
13. **US-13 (档案库与课题无缝映射)**: As a learner, I want opening the Knowledge Library modal to default to the currently active course, so that the file tree matches what the tutor is currently teaching.
14. **US-14 (历史单例平滑兼容)**: As a system maintainer, I want existing legacy materials in `data/materials/` to be treated as a default course (`course_id='default'`), so that existing user data and tests remain 100% backward compatible.

---

## 4. Implementation Decisions (实施与架构决策)

### 4.1 数据库结构多租户迁移 (`backend/database.py`)
- **新增 `courses` 元数据主表**：
  ```sql
  CREATE TABLE IF NOT EXISTS courses (
      id TEXT PRIMARY KEY,               -- 安全课题标识符 (如 "navier_stokes")
      name TEXT NOT NULL,                -- 课题中文展示名
      status TEXT DEFAULT 'active',      -- active | paused | completed | archived
      created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
      last_accessed_at DATETIME DEFAULT CURRENT_TIMESTAMP
  );
  ```
- **活跃课程指针记录**：
  在 `courses` 表中维护当前活跃标记，或在全局配置表中记录 `active_course_id TEXT DEFAULT 'default'`。
- **存量表字段动态扩展 (ALTER TABLE 兼容)**：
  - `user_mission`: 增加列 `course_id TEXT DEFAULT 'default'`；
  - `course_progress`: 增加列 `course_id TEXT DEFAULT 'default'`, `lesson_no INTEGER DEFAULT 1`；
  - `glossary`: 增加列 `course_id TEXT DEFAULT 'default'`，联合唯一索引 `(course_id, term)`；
  - `mission_draft`: 增加列 `course_id TEXT DEFAULT NULL`（用于拟定特定课题）。

### 4.2 课题生命周期与自动建卷 (`backend/services/mission_manager.py`)
- **自动提取并合法化 `course_id`**：
  在审问提案 `<mission_proposal>` 阶段，大模型生成或建议一个合法的英文 ASCII 短代号（若缺失则根据 `goal` 拼音或核心词转为合法 slug）。
- **`finalize_draft` 升级**：
  1. 调用 `MaterialsManager.create_course(course_id, name)` 生成物理隔离文件夹及 5 大子目录；
  2. 将目标契约持久化到 `data/materials/courses/<course_id>/Settings/user_mission.md`；
  3. 在 SQLite `user_mission` 表中插入或更新对应 `course_id` 的记录；
  4. 将新课题注册进 `courses` 主表并将其标记为当前 `active_course_id`。

### 4.3 物理沙盒与副作用处理器隔离 (`backend/services/side_effects.py`)
- **`ExplainerHandler`**：
  获取当前活跃的 `course_id`，将写入基准目录动态重定向至：
  `data/materials/courses/<course_id>/References/`（当 `course_id == 'default'` 时回退至全局 `References/`）。
- **`GlossaryHandler`**：
  执行 `INSERT OR IGNORE INTO glossary (course_id, term, definition) VALUES (?, ?, ?)`，并同步追加到该课题的 `Settings/glossary.json`。
- **沙盒文件工具 (`agent_tools.py`)**：
  工具 `create_file`、`replace_file_content`、`read_file` 接收当前会话的 `active_course_id`，将其根目录沙盒限制在 `courses/<course_id>/Sandbox/`，严防跨课题目录遍历。

### 4.4 课时大纲与授课驱动 (`backend/services/course_manager.py` & `slash_handler.py`)
- **`get_active_course(course_id: Optional[str] = None)`**：
  支持按 `course_id` 过滤。默认拉取当前激活课题中状态为 `active` 的课时记录。
- **`/lesson` 指令增强**：
  - 若输入形如 `/lesson [course_id]`，先校验该课程是否存在；若存在则切换当前活跃课程；
  - 若输入 `/lesson`，加载当前活跃课程的当前课时及大纲；
  - 构造包含当前课题名称、目标、课时序号、该课时待解决核心问题及沙盒代码路径的完整 `<system_directive>`。

### 4.5 RAG 向量切片隔离策略 (`backend/services/rag_service.py` / `chroma_client.py`)
- **Collection / Metadata 双重隔离**：
  - 同步教材（`sync_knowledge`）时，为每个 Document Chunk 附加元数据 `{"course_id": active_course_id}`；
  - 检索（`retrieve`）时，在 `where` 查询条件中注入 `{"course_id": active_course_id}`（同时支持兼容 `course_id == 'default'` 的全局基础通用知识）；
  - 确保跨学科授课时绝不产生向量切片互串。

### 4.6 完整四步闭环交互授课流程 (The 4-Stage Interactive Lesson Pipeline)
1. **阶段一：课题锚定与学情装配**：执行 `/lesson [course_id]` 或无参 `/lesson` 锁定活跃课题，装载该课题专属 `user_mission.md`、当前第 N 课时任务与隔离知识库；
2. **阶段二：苏格拉底式启发对齐**：导师结合学情，抛出贴近最近发展区 (ZPD) 的启发式问题与 `<quiz>` 测验卡片，绝不直接给出答案；
3. **阶段三：动态演进沙盒与讲义生成**：长文讲义（`<explainer>`）与术语（`<glossary>`）隔离落盘本课题。导师调用文件工具在 `courses/<course_id>/Sandbox/` 注入挑战代码，学员在真实沙盒中实操调试；
4. **阶段四：系统关卡放行与课时推进**：学员通过代码校验与认知考核后，导师触发 `<system_pass>`，标记该课时完成并自动推进到下一课时，动态刷新 ZPD 难度与评分。

### 4.7 “上课生动高效”与“下课生活情趣”的模式联动与档案隔离 (/lesson 与 /end_lesson)
- **氛围模式原生联动**：语气与氛围由系统顶部「研学 / 生活」按钮（`atmosphereMode: 'study' | 'daily'`）统一调控。`/lesson` 与 `/end_lesson` 形成前后置联动，并作为底层档案库切换的触发契机；
- **课堂内（上课态 · 研学模式 / study）**：
  - **联动研学模式**：执行 `/lesson [course_id]` 自动联动进入「研学模式」，挂载特定课题隔离沙盒（`courses/<course_id>/`），装载专属目标、课时、术语与沙盒；
  - **生动高效研学**：导师以精炼启发式探问、精妙比喻和实操考核引导学员攻坚，保障高信噪比学习体验；
  - **沙盒实操闭环**：代码调试与知识点吸收基于真实沙盒运行与校验，扎实稳妥推进课时；
- **课堂外（下课态 · 生活模式 / daily）**：
  - **联动生活模式**：执行 `/end_lesson`（别名 `/下课`）或点击「生活」按钮时，系统结算课时学情并**将系统活跃档案库切回公共基础档案 (default)**；
  - **公共档案保护**：日常生活闲聊、日记摘要与随笔沉淀在公共空间中，不写入任何具体的专业学科目录；专业学科的沙盒与复杂代码也不会打扰下课后的闲适生活；
  - **温馨生活情趣**：导师自然转回生活伴读状态，支持日常见闻漫谈、端茶对弈等情感互动，劳逸结合、张弛有度。

---

## 5. Testing Decisions (测试决策与最高测试切缝)

### 5.1 最高测试切缝设计 (The Highest Test Seams)
按照架构规范，优先选择最高层次、面向外部行为的 Seam 进行端到端验证，避免深陷内部私有函数断言：
1. **Seam 1: 目标设立 -> 课程建卷全生命周期 Seam (`SlashHandler` -> 物理目录 & DB)**
   - 触发带 `<finalize_mission>` 的对话流；
   - 断言磁盘物理目录 `courses/<course_id>/` 及 5 个子目录已创建，`course.json` 和 `Settings/user_mission.md` 存在且内容完好，SQLite `courses` 与 `user_mission` 记录已正确关联。
2. **Seam 2: 课时授课与副作用隔离 Seam (`ResponsePipeline` -> 独立子目录落盘)**
   - 在激活 `course_A` 的状态下，模拟大模型输出 `<glossary term="T1">...</glossary>` 与 `<explainer title="Doc1">...</explainer>`；
   - 断言文件精准落盘在 `courses/course_A/References/Doc1.md`，SQLite 中 `glossary` 的 `course_id` 为 `course_A`；
   - 切换到 `course_B` 后，断言 `course_B` 的知识库检索与术语查询无法召回 `course_A` 的内容。
3. **Seam 3: `/lesson` 课时推进 Seam (`course_manager` / `/lesson` 路由)**
   - 验证多课程大纲下，推进 `course_A` 的进度不会影响 `course_B` 的课时进度。

### 5.2 历史工程用例参考 (Prior Art)
- `backend/tests/test_materials_manager.py`（现有的分课程物理路径与防遍历测试）；
- `backend/tests/test_interceptor.py` 与 `test_response_pipeline.py`（标签拦截与副作用派发测试）；
- `backend/tests/test_stream_stop.py`（会话级流与全局控制器测试）。

---

## 6. Out of Scope (本期明确非范围)

1. **多用户多租户远程云同步**：本系统属于面向个人的随身私密伴读课堂，隔离仅针对同一用户在本地建立的“不同学科课题”，不涉及跨用户 SaaS 权限认证；
2. **已有散落全局文件的自动分类迁移工具**：全局 `default` 目录将作为“基础课程”永久保留，不提供激进的自动正则脚本强行拆解旧目录中的混合文件，避免破坏用户的历史已有练习。

---

## 7. Further Notes (架构演进与前置核对)

本 PRD 确立了媚吻峰伴读系统从“单例平面体系”向“**课题驱动的模块化知识沙盒体系**”的关键跨越。
在正式着手编码前，需就关键交互细节与用户进行前置确认与对齐。

