import sys
import os
sys.path.insert(0, os.getcwd())
print(f"CWD: {os.getcwd()}")
try:
    from backend.api import app
    print("Import successful")
except Exception as e:
    print(f"Import failed: {e}")
    import traceback
    traceback.print_exc()
