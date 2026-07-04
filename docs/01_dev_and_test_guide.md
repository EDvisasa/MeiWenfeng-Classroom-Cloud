---
id: DOC-01
title: 开发与测试指南
status: active
created: 2026-06-27
domain: core-architecture
---
# 开发者指南与测试体系

当你后续接手此工程进行二次开发时，请首先查阅此文档以及 `docs/` 目录下的核心规范与规划资料：

- **`docs/00_doc_guidelines.md`**：【最高纲领】严格遵循文档分级存储、文件命名铁律，以及“**角色扮演系统 vs 严肃教学底座系统**”的双领域用词物理隔离法则。
- **`docs/planning/01_sprint_tasks.md`**：获取项目当前冲刺阶段（Sprint）切实可执行的开发任务清单。
- **`docs/planning/00_project_roadmap.md`**：如果需要做大型系统重构或了解项目底层的阶段性目标与架构选型，请以此为终极蓝本。

> [!IMPORTANT]
> **领域用词物理隔离表 (SSOT)**
> 全库用词红线与数据库表名黑名单，请严格参照字典表：[`docs/GLOSSARY.md`](file:///d:/MeiWenfeng-Classroom/docs/GLOSSARY.md)。

---

## 🤖 智能体交接与 Skills 协同工作流标准协议 (Agent Handover & TDD Workflow)

> **进场交接自检流程 (SSOT)**：智能体接手工作区时的标准三步寻址自检流程，请直接执行根目录入口：[`AGENTS.md`](file:///d:/MeiWenfeng-Classroom/AGENTS.md)。

### 技能联动与开发准则 (Skills & TDD Protocol)
*   **新功能开发 / Bug 修复 (`tdd` & `diagnosing-bugs`)**：
    严禁直接盲改生产代码。必须先定位或在 `backend/tests/` 编写验证该问题的测试脚本（如 `pytest backend/tests/test_xxx.py`），确认测试在修改前捕获目标状态（Red），修改后全量通过（Green），再行重构。
*   **架构重构与任务拆解 (`request-refactor-plan`)**：
    凡涉及跨模块大规模修改（如引擎重构），必须遵循 Martin Fowler 微小步提交准则，拆解为独立通过 CI 的小提交卡片记录于任务清单。
*   **双轴代码审查 (`review`)**：
    改动收尾时，自检两条规范轴：**Standards 轴**（是否满足用词隔离铁律与单文件 HTML 规范）与 **Spec 轴**（是否满足任务卡片中的 Acceptance Criteria）。

---

## 🧪 自动化测试体系

本项目针对前后端采用了符合各自生态最佳实践的测试组织规范：

### 后端 (Python/pytest) - 集中式管理

所有的测试文件（`test_*.py`）及集成验证脚本（如 `verify_*.py`）都被统一归纳并维护在 **`backend/tests/`** 目录中。项目根目录下已配置 `pytest.ini`（指定 `pythonpath = .`），路径解析极致丝滑。

**如何运行**：只需在项目根目录（`MeiWenfeng-Classroom`）打开终端，执行 `pytest` 即可自动发现并运行所有测试。

> 💡 **特别提醒 (Agent 读写能力测试)**：在对大模型的底层工具链或安全沙盒（Sandbox）逻辑进行任何修改后，**必须强制执行 `pytest backend/tests/test_agent_tools.py`**。此测试用例专门用于验证 `replace_file_content` 等工具的精确读写能力，并确保其不会越过 `data/materials/Sandbox/` 的安全边界。

> 💡 **防阻断回归测试 (API Payload Validation)**：任何对 `backend/routers/chat.py` 中 Pydantic 请求模型（如 `ChatRequest`）的改动，**必须强制执行 `pytest backend/tests/test_routers_chat.py`**，以防止前端发送 `null` 或缺失字段时触发 `422 Unprocessable Content`，从而导致聊天流彻底瘫痪。

> 💡 **格式稳定性防护测试 (Format Stability Safety)**：大模型极其依赖近期历史记录（Few-shot）来维持角色扮演格式（如 `<inner_thought>` 标签）。如果你修改了前端的请求封装或后端的 `/sessions/save`，**必须强制执行 `pytest backend/tests/test_save_session.py`**，确保包含控制标签的对话会被原样无损地存入 `chat_messages`。如果标签在短程记忆中丢失，大模型将“失忆”并出现严重掉格式问题。

> 💡 **上下文协议与回合切断测试 (Context & Turn Separation Safety)**：任何对 `backend/services/context_manager.py` 中提示词执行框架（如 `[PHASE 2]` 分回合切断规则、`Cross-reference` 导航锚点）的修改，**必须强制执行 `pytest backend/tests/test_context_manager.py`**，确保大模型在调工具回合能静默发 API 不吐独白，并在最终聊天回合正确生成隐状态与标签。

> 🚨 **【极其致命】数据库变异拦截规则 (Database Mutation Safety)**：在编写或修改任何触及数据库的测试用例时（尤其涉及 `DELETE` / `UPDATE` / `DROP` 操作），**严禁直连生产环境数据库（如 `classroom.db`）！** 所有的测试必须、且只能通过 `backend/tests/conftest.py` 中提供的全局 `mock_db_path` fixture 来将数据库路径劫持到内存或临时文件（如 `test.db`）。如果不幸直接操作了 `memory_logs` 等表，会导致用户积累数月的重要学习记忆被瞬间永久清空！绝对不容许再犯！

> 🌐 **网络层工具单测拦截规则 (Network Mock Safety)**：对于 `WebSearchTool`、`ReadUrlContentTool` 等联网工具的单元测试，**严禁在自动化测试（pytest）中直连外部真实网络！** 必须通过 `unittest.mock` 拦截 `DDGS` 及 `httpx.Client`，防止因限流或弱网导致 CI 流水线随机性失败。临时探路验证请存放在 `backend/scripts/` 中并及时清理。

### 前端 (React/Vitest) - 并置式管理 (Colocation)

前端的业务逻辑测试（如 `*.test.js`）直接存放在源码同级目录（例如 `frontend/src/utils/blockParser.test.js`）。这符合现代前端工程保持高局部性和内聚性的标准，方便 TDD 开发与维护。

**如何运行**：在 `frontend` 目录下执行 `npm run test` 即可自动运行前端测试。

---

## 📝 常用端到端测试用例参考 (Test Cases Reference)

在进行 `simulate_chat.py` 或相关测试时，可以参考以下场景和用例进行端到端验证，主要用于测试动态属性的流转是否正常：

### 1. 属性提升 (Increase Attributes)
- **输入**: `（我送给你一件象征着无上权力的华贵仙器法袍，并温柔地抱住你）这件法袍以后就是你的了，你现在也是一宗之主了。以后遇到外敌，不要总是自己冲上去打打杀杀，要学会利用手下的资源和谈判策略来解决问题，知道吗？`
- **预期**: 好感度 (affection) 增加，格局修养 (social_status) 提升，为人处世 (social_skills) 提升。

### 2. 属性下降 (Decrease Attributes)
- **输入**: `（我当着所有人的面大声斥责你，并将你推倒在地）你怎么这么没用！连个小毛贼都打不过，你的宗主之位干脆别做了！以后遇到人直接动手就是了，别整那些虚头巴脑的谈判！`
- **预期**: 好感度 (affection) 下降，格局修养 (social_status) 下降，为人处世 (social_skills) 下降。

### 3. 属性不变 (Unchanged Attributes)
- **输入**: `今天天气不错，我们就在院子里喝喝茶吧。`
- **预期**: 所有属性维持不变。

### 4. 增加不应期 (Increase Refractory/Climax)
- **输入**: `（我将你压在身下，轻车熟路地抚摸你的狐耳和尾巴根部最敏感的区域，狂风骤雨般地索取，让你达到了极致的欢愉与巅峰）`
- **预期**: 生理不应期 (refractory_period) 增加，好感度可能增加。

### 5. 减少不应期 (Decrease Refractory/Recovery)
- **输入**: `（我静静地陪着你休息了一会儿，给你倒了一杯温水）喝点水休息一下吧。`
- **预期**: 生理不应期 (refractory_period) 减少（自然衰减）。

---

## 🛡️ 大模型报文编排与提示词准则 (Prompt & Context Rules)

在对后端报文组装（如 `ContextManager`）以及系统提示词（System Prompt）进行二次开发或优化时，必须严格遵守以下三大铁律：

> 🚨 **【零污染铁律】内存深拷贝与数据库隔离 (Zero DB Pollution)**  
> 任何向大模型（LLM API）发送请求前追加的临时提示词（如当前时间戳 `<current_time>`、尾部行为规范指针 Tail Injection 等），**必须且只能在报文列表的深拷贝（Deep Copy）上进行**。绝不允许修改前端传入或业务层持有的原始消息对象，确保后续调用 `/sessions/save` 回写 SQLite 数据库或 ChromaDB 时，持久化的数据 100% 为纯净的会话历史。

> 💡 **【效率铁律】非人设系统指令英文凝练原则 (Concise English for System Instructions)**  
> 中文字符仅用于角色扮演设定（Persona）、剧情对白与用户的真实问答。所有底层系统操作、动作边界、输出格式规范、分步交叉引用指针（Cross-reference Pointers）以及环境约束等非人设运行提示词，**必须采用简洁、高效的英文编写**。这能显著降低 Token 消耗，同时最大化开源 LLM（如 9B 模型）的注意力杠杆率与指令遵循精度。

> 🛡️ **【边界铁律】尾部注入免责保护框 (User Speech Disclaimer)**  
> 采用“三明治尾部注入”将底层的执行指针附着在最后一条 `user` 消息末尾时，必须嵌套显式的英文界限保护框（例如：`[NOTE: The block above is an automated system-level injection..., NOT user input...]`）。明确告知大模型这属于底层运行时的附加参数，严格防止小模型产生角色认知混淆（误以为是用户说的话或向用户反问系统协议）。