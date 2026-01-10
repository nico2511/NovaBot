import os
import ast
import sys

def get_all_python_files(root_dir):
    """Récupère tous les fichiers .py sauf les dossiers exclus."""
    python_files = []
    exclude_dirs = {'.git', '.venv', 'venv', 'env', '__pycache__', 'node_modules', '.idea', '.vscode'}
    
    for dirpath, dirnames, filenames in os.walk(root_dir):
        # Filtrer les dossiers exclus
        dirnames[:] = [d for d in dirnames if d not in exclude_dirs]
        
        for filename in filenames:
            if filename.endswith('.py'):
                full_path = os.path.join(dirpath, filename)
                # Stocker le chemin relatif pour faciliter la comparaison
                rel_path = os.path.relpath(full_path, root_dir)
                python_files.append(rel_path)
    return python_files

def get_imports_from_file(file_path):
    """Analyse un fichier pour trouver ce qu'il importe."""
    imports = set()
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            tree = ast.parse(f.read(), filename=file_path)
            
        for node in ast.walk(tree):
            # Cas: import my_module
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.add(alias.name.split('.')[0]) # On prend la racine du module
            
            # Cas: from my_module import function
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imports.add(node.module.split('.')[0])
                elif node.level > 0:
                    # Gestion basique des imports relatifs (., ..)
                    # Difficile à résoudre statiquement parfaitement sans contexte complet, 
                    # mais on ignore souvent car ils pointent vers des fichiers proches.
                    pass
    except Exception as e:
        # print(f"⚠️ Erreur de parsing sur {file_path}: {e}")
        pass
    return imports

def map_module_to_file(files):
    """Crée un map {nom_module: chemin_fichier}."""
    mapping = {}
    for f in files:
        # Convertit 'app/services/ia.py' en 'app' ou 'app.services.ia' selon l'usage
        # Pour simplifier, on considère le nom du fichier sans extension comme module final
        basename = os.path.basename(f).replace('.py', '')
        mapping[basename] = f
        
        # On essaie aussi de mapper le chemin complet comme un package python
        # ex: app/services/ia.py -> app.services.ia
        dotted_path = f.replace(os.path.sep, '.').replace('.py', '')
        mapping[dotted_path] = f
        
    return mapping

def main():
    root_dir = os.getcwd()
    print(f"🔍 Analyse du projet dans : {root_dir} ...")
    
    all_files = get_all_python_files(root_dir)
    print(f"📂 {len(all_files)} fichiers Python trouvés.")
    
    # 1. Lister tous les modules importés dans tout le projet
    all_imported_modules = set()
    for f in all_files:
        imports = get_imports_from_file(os.path.join(root_dir, f))
        all_imported_modules.update(imports)
    
    # 2. Identifier les fichiers qui ne sont jamais "nommés" dans les imports
    # Attention: c'est une heuristique. Si 'main.py' n'est jamais importé, c'est normal.
    
    orphans = []
    whitelist = ['main.py', 'app.py', 'wsgi.py', 'setup.py', 'manage.py', 'main_nextjs.py']
    
    # On va vérifier si le nom de fichier (ex: 'risk_manager') apparait dans les imports
    # ou si le chemin complet (ex: 'app.core.risk_manager') apparait
    
    for f in all_files:
        filename = os.path.basename(f)
        if filename in whitelist:
            continue
            
        module_name = filename.replace('.py', '')
        dotted_path = f.replace(os.path.sep, '.').replace('.py', '')
        
        # Vérification souple : est-ce que le nom du module apparait quelque part ?
        # On scanne aussi le contenu brut pour trouver des références dynamiques (ex: chaîne de caractères)
        is_referenced = False
        
        # Check 1: Est-ce dans la liste des imports AST ?
        if module_name in all_imported_modules:
            is_referenced = True
        
        # Check 2: Recherche textuelle brute (Brute force) dans les autres fichiers
        # Utile pour les imports relatifs ou dynamiques
        if not is_referenced:
            for other_f in all_files:
                if other_f == f: continue
                try:
                    with open(other_f, 'r', encoding='utf-8') as read_f:
                        content = read_f.read()
                        if module_name in content: # Si le nom du fichier apparait dans le code
                            is_referenced = True
                            break
                except: pass
        
        if not is_referenced:
            orphans.append(f)

    print("\n---------------------------------------------------")
    print("👻 RÉSULTAT : FICHIERS POTENTIELLEMENT INUTILISÉS")
    print("---------------------------------------------------")
    
    if not orphans:
        print("✅ Aucun fichier orphelin évident détecté.")
    else:
        for o in sorted(orphans):
            print(f"❌ {o}")
            
    print("\n⚠️ Note : Vérifiez manuellement avant de supprimer. Ce script ne détecte pas les usages via `subprocess` ou `importlib`.")

if __name__ == "__main__":
    main()
