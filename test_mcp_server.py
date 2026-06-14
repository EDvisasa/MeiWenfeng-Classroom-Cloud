import pytest
from backend.mcp_server import read_active_course, append_new_course

def test_read_active_course_with_active_course(mock_get_active_course):
    """Test read_active_course when there is an active course."""
    mock_get_active_course.return_value = {"phase": "Phase 2: Frontend", "topic": "React Hooks"}
    
    result = read_active_course()
    
    assert "Phase 2: Frontend" in result
    assert "React Hooks" in result
    mock_get_active_course.assert_called_once()

def test_read_active_course_without_active_course(mock_get_active_course):
    """Test read_active_course when there is no active course."""
    mock_get_active_course.return_value = None
    
    result = read_active_course()
    
    assert "No active course" in result
    mock_get_active_course.assert_called_once()

def test_append_new_course(mock_append_to_syllabus):
    """Test append_new_course successfully appends to the syllabus."""
    result = append_new_course("Phase 3: Integration", "VS Code APIs")
    
    assert "[Success]" in result
    assert "Phase 3: Integration" in result
    mock_append_to_syllabus.assert_called_once_with("Phase 3: Integration", "VS Code APIs")
