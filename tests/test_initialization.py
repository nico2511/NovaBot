import os
import sqlite3
import pytest
from app.core.config import settings

def test_structure():
    assert os.path.isdir("app")
    assert os.path.isdir("app/core")
    assert os.path.exists("app/core/config.py")
    assert os.path.exists("app/core/database.py")
    assert os.path.exists("main.py")

def test_database_creation():
    db_path = "novabot.db"
    assert os.path.exists(db_path), "Database file not found"
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Check users table
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users';")
    assert cursor.fetchone() is not None, "users table missing"
    
    # Check decision_logs table
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='decision_logs';")
    assert cursor.fetchone() is not None, "decision_logs table missing"
    
    conn.close()
