import pytest
import sys
import os
from pathlib import Path

# Add backend directory to path so imports work
backend_path = Path(__file__).parent.parent
sys.path.append(str(backend_path))

@pytest.fixture
def mock_video_id():
    return "dQw4w9WgXcQ"

@pytest.fixture
def sample_video_metadata():
    return {
        "title": "Test Video Title",
        "description": "Test Description",
        "channel": "Test Channel",
        "tags": ["test", "video"],
        "category": "Education"
    }
