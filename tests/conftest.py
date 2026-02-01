"""
Pytest Configuration and Fixtures
"""
import pytest
import shutil
import os
from pathlib import Path
from tempfile import mkdtemp
from fastapi.testclient import TestClient
from backend.api.main import app
from backend.services.storage import StorageService

@pytest.fixture
def temp_data_dir():
    """Create a temporary data directory for tests"""
    tmp_dir = mkdtemp()
    yield Path(tmp_dir)
    shutil.rmtree(tmp_dir)

@pytest.fixture
def mock_storage(temp_data_dir):
    """
    Storage Service initialized in temp dir.
    This prevents tests from messing with real data/ folder.
    """
    # Initialize directory structure manually to mimic init_storage
    (temp_data_dir / "config").mkdir(parents=True, exist_ok=True)
    (temp_data_dir / "cache").mkdir(parents=True, exist_ok=True)
    (temp_data_dir / "state").mkdir(parents=True, exist_ok=True)
    (temp_data_dir / "analysis").mkdir(parents=True, exist_ok=True)
    
    service = StorageService(temp_data_dir)
    return service

@pytest.fixture
def test_client():
    """FastAPI Test Client"""
    with TestClient(app) as client:
        yield client
