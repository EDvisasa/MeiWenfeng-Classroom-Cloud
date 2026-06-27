# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]
### Added
- **Web Search & Deep Reading (Browser)**: Integrated `WebSearchTool` (using DuckDuckGo API) and `ReadUrlContentTool` (using `httpx`, `BeautifulSoup4`, and `markdownify`).
- **Agent Scrolling & Pagination**: Implemented an explicit line-based (800 lines max) pagination mechanism for both `read_file` and `read_url_content`, allowing the AI to scroll through massive documents/webpages without context window overflow.
- **UI Title Mapping**: Mapped `web_search` to display as "Web" and `read_url_content` as "Browser" in the frontend `ChatPanel` header.
- **Multi-Tool Concurrency**: Integrated `<tool_batch>` capability allowing the AI agent to execute multiple tools in a single response cycle.
- **Human-In-The-Loop (HITL) execution**: Interactive UI for hazardous tools (`execute_bash`). A `BashApprovalCard` component now floats natively within the `ChatPanel` enabling users to allow or reject system modifications.
- **Enhanced Agent Tools architecture**: Centralized registry for `read_file`, `grep_search`, `execute_bash`, `replace_file_content`, and `create_file` within `agent_tools.py`.
- **System Guardrails**: Injected dynamic real-world time into the AI's persona, preventing time-check hallucinations. Introduced robust safety checks blocking the use of `cat`, `type`, `grep`, and `findstr` in bash, guiding the model to use optimized native implementations.
- **Robust Multi-Turn Loop**: Overhauled `AgentExecutor.run()` to cleanly intercept server-sent events, pause for HITL inputs, and resume generation synchronously without dropping state or chunking issues.

### Fixed
- **UI State Glitches**: Resolved "ghost typing-cursor" blinking artifact that persisted after streaming had logically concluded.
- **Responsive Layout**: Rebuilt `ChatPanel` layout logic so that the input textarea safely coexists with system tool block logs and the absolute-positioned `BashApprovalCard`.
- **Sandbox Boundary Violations**: Upgraded the internal path resolution mechanisms to firmly prevent AI `replace_file_content` out-of-bounds filesystem operations (restricting modifications to `docs/sandbox/`).

### Changed
- **Pipeline Segregation**: Migrated specific `execute_bash` execution loops out of the generic `ResponsePipeline` and moved them directly into the pure agent `OpenAILLMClient` wrapper flow for stronger semantic isolation.
