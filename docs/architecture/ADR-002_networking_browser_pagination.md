# ADR-002: 智能体联网泛搜与深度长文分页阅读架构

## 状态
已通过 & 已列装 (2026-06-27)

## 背景与痛点
在传统的 Agent 架构中，大语言模型（LLM）面对实时性问题或需要查阅大量外部文书时，常遇到以下限制：
1. **纯泛搜信息量不足**：DuckDuckGo 等搜索引擎 API 返回的摘要（Snippet）通常仅有两三百字，如果核心数据（如具体的 Benchmark 跑分表）未被抓进摘要，模型会基于先入为主的错觉进行“高情商脑补/编造”。
2. **直接网页抓取的显存灾难**：如果无脑将完整 URL 的 HTML 正文塞入 LLM 上下文，冗余的 `<script>`、`<style>`、导航栏和页脚会严重污染注意力机制，且动辄几万字的内容会直接撑爆本地小显存（如 RTX 4070 Laptop 8G 显存上限），引发 OOM。

## 决策方案
构建**“分层渐进式信息获取管线（Two-Tier Information Pipeline）”**，并统一引入**“向下滚动翻页机制（Pagination）”**：

### 1. 第一层：快速扫视（Web Search）
- **工具**：`WebSearchTool` (`web_search`)
- **实现**：基于 `ddgs` 接口，仅抓取前 5 条摘要片段。
- **UI 映射**：前端气泡回显标签规范化为 `Web`。
- **Agentic 逻辑**：如果摘要已包含精准答案，即刻终止抓取，践行高效能“懒惰原则”。

### 2. 第二层：降维精读与翻页（Browser Reading）
- **工具**：`ReadUrlContentTool` (`read_url_content`)
- **清洗引擎**：引入 `beautifulsoup4` 剥离页面噪音节点，经由 `markdownify` 转化为保留标题层级与表格结构的纯净 Markdown。
- **统一翻页护城河**：
  - 复刻 `ReadFileTool` 的防爆显存经验，将 Markdown 正文按**行数（Line Count）**切割，单页限制为 **800 行**。
  - 触发截断时，抛出带有强心理诱导的系统行动暗示：
    `👉 To read more, call this tool again with <start_line>{s+800}</start_line>`
- **UI 映射**：前端气泡回显标签规范化为 `Browser: {url}`，大段 Markdown 正文仅留于系统隐匿上下文中。

## 影响与验证
- 极大提升了 9B ~ 35B 级别开源模型在面对复杂长文时的深挖自查能力。
- 本地 8G VRAM 环境下单次抓取内存占用绝对稳定，杜绝上下文溢出。
