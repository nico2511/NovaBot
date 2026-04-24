"""
Pytest Configuration and Fixtures
"""
import os
import shutil

# Ensure API auth is disabled for the entire test run, regardless of what
# the developer has in their local .env. Must be set BEFORE importing app.*
# so app.core.config.Config reads the overridden env vars.
os.environ["API_KEY_REQUIRED"] = "false"
os.environ.setdefault("API_KEY", "test-key")

import pytest
from pathlib import Path
from tempfile import mkdtemp
from fastapi.testclient import TestClient
from app.api.main import app
from app.core.config import config as _app_config
from app.services.storage import StorageService

# Belt-and-suspenders: force the already-loaded singleton to the test defaults
# (in case something imported config before this module).
_app_config.API_KEY_REQUIRED = False

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
