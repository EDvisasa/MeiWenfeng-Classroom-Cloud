---
id: PLAN-CHANGELOG
title: Changelog
status: active
created: 2026-06-27
domain: project-planning
---
# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]
### Added
- **Combinatorial Ambient Greeting Engine (ADR-010 & ISSUE-27)**: 4D Cartesian product ($A \times B \times C \times D$) greeting generation engine extracting 38 original vignettes from 61KB persona, dynamically keyed to physical time slots, affection stages, and reunion status without token cost.
- **Affection Temporal Decay & Reunion Warm-Up (ISSUE-26)**: Realistic affection economic model with stage-specific buffer grace periods (2~7 days), floor guarantees preventing decay beyond one stage, +3 daily net cap, and 2-turn ice-breaking critical bonus.
- **Quiz Mistake Penalty & Attitude Directive (ISSUE-25)**: Atomic affection deduction (-2) and `<slacking_warning>` emotion directive when users trigger 3 consecutive wrong answers on quiz blocks.
- **Dynamic One-Shot Pipeline Hardening**: Preserves dynamic ambient opening greetings in `assemble_messages` without text truncation or static string overwrites, while formatting standardized `<think>`, `<monologue>`, and `<property_update>` in-context demonstration.
- **Conversation Auto-Compact Engine & Cutoff Boundary (ISSUE-24)**: Dynamic model window threshold detection (32K~128K cloud vs 8K local) and `compact_cutoff_id` incremental rolling compaction preventing repeat summarization.
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
- **Sandbox Boundary Violations**: Upgraded the internal path resolution mechanisms to firmly prevent AI `replace_file_content` out-of-bounds filesystem operations (restricting modifications to `data/materials/Sandbox/`).

### Changed
- **Pipeline Segregation**: Migrated specific `execute_bash` execution loops out of the generic `ResponsePipeline` and moved them directly into the pure agent `OpenAILLMClient` wrapper flow for stronger semantic isolation.
