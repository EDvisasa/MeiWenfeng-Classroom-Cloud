import pytest
from unittest.mock import patch

@pytest.fixture
def mock_get_active_course():
    with patch('backend.mcp_server.get_active_course') as mock_get:
        yield mock_get

@pytest.fixture
def mock_append_to_syllabus():
    with patch('backend.mcp_server.append_to_syllabus') as mock_append:
        yield mock_append
