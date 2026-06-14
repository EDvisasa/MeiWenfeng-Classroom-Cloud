from mcp.server.fastmcp import FastMCP
from backend.services.course_manager import (
    get_active_course,
    get_formatted_syllabus,
    advance_course_progress,
    append_to_syllabus
)
from backend.services.rag_factory import get_rag_client

# Initialize FastMCP Server
mcp = FastMCP("MeiWenfeng_Classroom")

@mcp.tool()
def search_memory(query: str, limit: int = 3) -> str:
    """Search the user's past learning memories and custom classroom knowledge base for relevant information.
    
    Args:
        query: The semantic search query based on user's input.
        limit: Max number of results to return.
    """
    rag_client = get_rag_client()
    try:
        context = rag_client.retrieve(query, dataset_names=["Classroom_Knowledge", "Memory_Knowledge"])
        if context:
            return context
        return "No relevant memories found."
    except Exception as e:
        return f"Error retrieving memories: {e}"

@mcp.tool()
def read_active_course() -> str:
    """Retrieve the currently active course phase and topic for the user."""
    course = get_active_course()
    if course:
        return f"Current Phase: {course['phase']}\\nCurrent Topic: {course['topic']}"
    return "No active course. User is in free exploration mode. Recommend creating a new plan using append_new_course."

@mcp.tool()
def read_syllabus_history() -> str:
    """Retrieve the entire formatted syllabus history to understand what the user has learned and what is pending."""
    return get_formatted_syllabus()

@mcp.tool()
def advance_course() -> str:
    """Mark the current active course as completed, and advance the user to the next pending course. Call this ONLY when the user passes the current topic assessment."""
    new_course = advance_course_progress()
    if new_course:
        return f"Successfully advanced to next course: {new_course['phase']} - {new_course['topic']}"
    return "Course advanced. No more pending courses. User has finished all planned topics."

@mcp.tool()
def append_new_course(phase: str, topic: str) -> str:
    """Append a new course topic to the syllabus. Call this when planning future learning for the user.
    
    Args:
        phase: The high-level phase or chapter name (e.g., 'Phase 1: Foundations').
        topic: The specific topic to learn (e.g., 'Variables and Data Types').
    """
    append_to_syllabus(phase, topic)
    return f"[Success] Successfully appended new course: Phase '{phase}', Topic '{topic}' to the syllabus as pending."

if __name__ == "__main__":
    mcp.run()
