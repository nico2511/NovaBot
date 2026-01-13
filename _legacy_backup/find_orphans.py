
import os
import ast
import sys
from pathlib import Path

def get_all_python_files(root_dir):
    py_files = []
    for dirpath, _, filenames in os.walk(root_dir):
        if ".venv" in dirpath or "__pycache__" in dirpath or ".git" in dirpath:
            continue
        for f in filenames:
            if f.endswith(".py"):
                py_files.append(os.path.abspath(os.path.join(dirpath, f)))
    return py_files

def get_imports_from_file(file_path):
    imports = set()
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            tree = ast.parse(f.read(), filename=file_path)
        
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.add(alias.name.split('.')[0])
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imports.add(node.module.split('.')[0])
                    # Handle relative imports logic mostly by assuming package structure
    except Exception as e:
        pass
        # print(f"Error parsing {file_path}: {e}")
    return imports

def analyze_orphans(root_dir):
    all_files = get_all_python_files(root_dir)
    file_map = {f: os.path.basename(f) for f in all_files}
    filename_to_path = {os.path.basename(f): f for f in all_files}
    
    # Store all "module names" that are imported
    imported_modules = set()
    
    # Heuristic: Convert file path to module path
    # e.g., app/services/ia.py -> app.services.ia
    file_to_module = {}
    for f in all_files:
        rel_path = os.path.relpath(f, root_dir)
        module_path = rel_path.replace(os.path.sep, ".").replace(".py", "")
        file_to_module[f] = module_path
    
    # 2. Scan all files for imports
    imported_modules_raw = set()
    
    for f in all_files:
        try:
            with open(f, "r", encoding="utf-8") as file:
                content = file.read()
                
            tree = ast.parse(content)
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        imported_modules_raw.add(alias.name)
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        # Direct module import
                        imported_modules_raw.add(node.module)
                        # Also add "module.member" as potential file ref
                        # This is tricky without resolving members, but we'll stick to modules
        except:
            continue
            
    # Resolve imports to files
    # Check if a file's module path matches any imported module
    referenced_files = set()
    
    for f, mod_name in file_to_module.items():
        # Check strict match
        if mod_name in imported_modules_raw:
            referenced_files.add(f)
            continue
            
        # Check partial match (e.g. import app.services -> app.services.ia is NOT referenced, but app.services IS)
        # Actually usually it's the other way: "from app.services import ia" -> "app.services" is imported.
        # If we see "app.services.ia", that file is referenced.
        
        # Check if any imported string is a prefix of this module (package import)
        # or if this module is a prefix of an imported string (member import)
        
        is_referenced = False
        for imp in imported_modules_raw:
            if imp == mod_name:
                is_referenced = True
                break
            # File is "app.services.ia", Import is "app.services.ia.SomeClass"
            if imp.startswith(mod_name + "."):
                is_referenced = True
                break
            # File is "app.services.ia", Import is "app.services" (weak ref)
            # This doesn't necessarily mean the file is used, unless it's an __init__
            
        if is_referenced:
            referenced_files.add(f)
            
    # Special Handling for string-based dynamic imports commonly used in this project?
    # No, stick to static analysis first.
    
    # Whitelist
    whitelist = [
        "main.py", "app.py", "wsgi.py", "manage.py", "api.py", "setup.py",
        "conftest.py", "test_", "strategies.py", "main_nextjs.py"
    ]
    
    orphans = []
    for f in all_files:
        if f in referenced_files:
            continue
        
        # Check whitelist
        fname = os.path.basename(f)
        if any(w in fname for w in whitelist):
            continue
            
        # Check if it's an __init__.py (usually implicit)
        if fname == "__init__.py":
            continue
            
        orphans.append(f)
        
    return orphans

if __name__ == "__main__":
    root = os.getcwd()
    print(f"Scanning {root} for orphans...")
    orphans = analyze_orphans(root)
    
    print("\n📂 POTENTIAL ORPHAN FILES:")
    for o in orphans:
        print(f"  - {os.path.relpath(o, root)}")
        
    print(f"\nFound {len(orphans)} potential orphans.")
