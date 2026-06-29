import os
import sys

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from backend.services.prompts import get_system_prompt

# The tool use guidelines as injected in AgentExecutor
system_injection = """
<tool_use_guidelines>
You have access to a local command-line terminal and file system tools via standard function calling.
 You are using Windows cmd.exe. CRITICAL: Multiline strings do NOT work well in `python -c` or standard terminal commands here. If you need to run a python script, write it entirely on ONE line using semicolons (e.g. `python -c "import os; print('hi')"`), or write it to a temporary .py file and execute that file. Use Windows commands (e.g., `dir` instead of `ls`).

CRITICAL RULES:
1. THINK BEFORE YOU ACT: You MUST ALWAYS start your response with a <think> block to explain your plan and reasoning.
2. TOOL INVOCATION: You have native function calling tools. If you need information (like web search or reading files), you MUST invoke the tool via the API. DO NOT hallucinate or make up facts.
3. STOP AFTER TOOL CALL: When you invoke a tool, you must STOP generating conversational text and wait for the system to execute the tool. The system will return the result to you in the next turn.
4. ERROR RECOVERY: If the system execution result contains an error, analyze it in your next <think> block and try a different command.
5. USE SPECIFIC TOOLS: You MUST use `read_file` to read files. NEVER use `cat` or `type` via `execute_bash`.
6. ENFORCE SEARCH TOOL: To search for a specific string or keywords across files in a directory, you MUST use the `grep_search` tool.
7. TIME PERCEPTION: You already have the exact, up-to-date real-world time in the `<current_time>` block of your system prompt.
8. WEB SEARCH: You have access to a `web_search` tool. Use it to look up recent facts, news, or technical documentation. NEVER hallucinate news or facts.
9. MAINTAIN PERSONA: When you have gathered enough info and are ready to reply, respond directly in character.
10. STRICT TAG SEQUENCE: You MUST explicitly close your `</think>` block BEFORE outputting any tool calls.
</tool_use_guidelines>
"""

def generate_full_prompt(affection, status, skills, refractory, name):
    base_prompt = get_system_prompt(
        affection_value=affection,
        persona_type="simplified",
        social_status=status,
        social_skills=skills,
        refractory_period=refractory
    )
    full = base_prompt + "\\n\\n" + system_injection
    
    with open(f"C:/Users/EDvisa/.gemini/antigravity-ide/brain/6bb77cf5-9d16-4b7a-a683-d151eb9af1cb/scratch/prompt_{name}.txt", "w", encoding="utf-8") as f:
        f.write(full)
    print(f"Generated {name}")

generate_full_prompt(0, 0, 0, 0, "cold")
generate_full_prompt(100, 100, 100, 25, "loving")
