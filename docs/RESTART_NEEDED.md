# ⚠️ IMPORTANT - Redémarrage requis

## Problème détecté

L'endpoint `/api/settings` retourne 404 car le backend tourne avec l'ancienne version du code.

## Solution

**Redémarrer le backend :**

1. Arrêter le processus actuel (Ctrl+C dans le terminal)
2. Relancer avec :

```bash
./start_nextjs.sh
```

OU pour l'intégration complète :

```bash
./start_integrated.sh
```

## Vérification

Après redémarrage, tester :
- http://localhost:8000/docs
- Chercher `/api/settings` dans la liste des endpoints
- Devrait apparaître avec GET et POST

## Note

Les modifications du code backend ne sont prises en compte qu'après redémarrage du serveur FastAPI.

**Hot reload n'est pas activé par défaut.**

Pour activer le hot reload (développement) :
```bash
cd backend
uvicorn api:app --reload --host 0.0.0.0 --port 8000
```

Mais pour l'instant, un simple redémarrage suffit ! 🚀
