---
title: 'Backend FastAPI Refactoring - Eliminate Dual State & Clean Architecture'
slug: 'backend-fastapi-refactoring'
created: '2026-02-01'
status: 'ready-for-dev'
stepsCompleted: [1, 2, 3, 4]
tech_stack: ['Python 3.10+', 'FastAPI 0.115.5', 'Pydantic 2.10.3', 'pytest 8.3.4', 'pytest-asyncio 0.24.0', 'httpx 0.28.1', 'uvicorn 0.32.1', 'watchdog (to add)']
files_to_modify: ['backend/api.py (1920 lines)', 'backend/bot_bridge.py', 'backend/routes/analysis.py', 'backend/routes/scanner.py']
files_to_create: ['backend/api/main.py', 'backend/api/dependencies.py', 'backend/api/routers/*.py', 'backend/services/storage.py', 'backend/services/settings_watcher.py', 'backend/models/api_models.py', 'backend/tests/*.py']
code_patterns: ['Singleton Pattern (BotBridge)', 'Dual State Pattern (to eliminate)', 'Pydantic BaseModel', 'FastAPI Depends()', 'Try/Except Global Imports (to remove)', 'Custom sanitize_for_json (to replace)']
test_patterns: ['pytest with TestClient', 'pytest-asyncio for async endpoints', 'Fixtures for mocking', 'Archived tests in _archive/tests/']
---

# Tech-Spec: Backend FastAPI Refactoring - Eliminate Dual State & Clean Architecture

**Created:** 2026-02-01

## Overview

### Problem Statement

Le backend FastAPI actuel (backend/api.py - 1920 lignes) souffre de plusieurs problèmes critiques de dette technique :

1. **Dual State Hell** : Existence de deux systèmes d'état parallèles (BotState standalone vs BotContext via bot_bridge) créant de la complexité et des risques d'incohérence
2. **Fichier Monolithique** : Tout le code API dans un seul fichier de 1920 lignes, difficile à maintenir et tester
3. **Mode Fallback Dangereux** : Logique de fallback vers bot_state.json masquant les vrais problèmes de connexion
4. **Écritures Non-Atomiques** : Risques de corruption des fichiers JSON (user_settings.json, strategies.json) lors d'écritures concurrentes
5. **Manque de Tests** : Pas de tests automatisés pour valider les flux critiques
6. **Code Patterns Inconsistants** : Mélange de patterns (try/except global, imports conditionnels, sanitize_for_json custom)

### Solution

Refactoring complet du backend en architecture propre et production-ready :

1. **Éliminer complètement BotState** : Supprimer toute la logique standalone/fallback. Si bot_bridge n'est pas connecté → 503 Service Unavailable avec messages d'erreur spécifiques
2. **Architecture en Couches** : Découper api.py en structure modulaire (routers, services, models, dependencies)
3. **Service de Storage Atomique** : Créer services/storage.py avec écriture atomique (temp file + fsync + rename) pour tous les fichiers JSON
4. **Hot-Reload des Settings** : Implémenter un mécanisme de rechargement automatique des settings quand user_settings.json est modifié
5. **Tests Automatisés** : Suite de tests pytest pour valider tous les flux critiques
6. **CORS Localhost-Only** : Configuration CORS explicite pour localhost uniquement (pas de VPN/online)

### Scope

**In Scope:**
- Suppression complète de la classe BotState et bot_state.json
- Restructuration de backend/api.py en architecture modulaire (routers, services, models)
- Création de api/dependencies.py avec get_bot_context() qui lève HTTPException(503) si non connecté
- Migration de tous les endpoints vers Pydantic models (request/response)
- Création de services/storage.py avec atomic_write_json() et méthodes spécialisées
- Implémentation du hot-reload des settings (file watcher + callback)
- Suite de tests pytest pour les flux critiques (start/stop, switch symbol, panic, settings update)
- Configuration CORS localhost-only avec liste explicite
- Suppression de sanitize_for_json() → utilisation de Pydantic .model_dump() et jsonable_encoder
- Logs structurés avec logger.info/warning/error

**Out of Scope:**
- Modification du code Python backend existant (app/, strategies/) - IMMUTABLE selon project-context.md
- Changements dans le frontend Next.js
- Migration vers une autre base de données (on garde les fichiers JSON)
- Authentification/Authorization (localhost uniquement)
- WebSocket refactoring (focus sur REST API)
- Performance optimization (focus sur maintenabilité)

## Context for Development

### Codebase Patterns

**Architecture Actuelle :**
- Fichier monolithique : `backend/api.py` (1920 lignes)
- Dual state pattern : `if bot_bridge.is_connected()` → BotContext, sinon → BotState
- Imports conditionnels avec try/except global
- Fonction helper `_execute_bot_action(bot_action, standalone_action, ...)` pour gérer le dual state
- Écriture JSON directe sans atomicité : `json.dump(data, f, indent=2)`

**Contraintes du Projet (project-context.md) :**
- Backend Python (app/, backend/, strategies/) considéré **IMMUTABLE**
- Exception : Ajout d'endpoints API dans backend/ si strictement nécessaire
- Communication Frontend ↔ Backend via REST API polling (1s) sur localhost:8001
- Pas d'authentification requise (contexte localhost/VPN)
- Le Frontend ne possède PAS l'état, il reflète bot_state.json

**Patterns à Suivre :**
- Typage strict (typing + Pydantic)
- Fonctions courtes (< 40 lignes idéalement)
- Dependency Injection via FastAPI Depends()
- Service Layer pour la logique métier
- Repository Pattern pour le storage
- Logs structurés avec contexte

### Files to Reference

| File | Purpose |
| ---- | ------- |
| `backend/api.py` | Fichier monolithique actuel à refactorer (1920 lignes) |
| `backend/bot_bridge.py` | Bridge vers BotContext - à préserver et utiliser exclusivement |
| `app/core/bot.py` | BotContext class - READ ONLY, ne pas modifier |
| `app/core/state_manager.py` | StateManager pour sauvegarder l'état du bot - READ ONLY |
| `app/services/hyperliquid_service.py` | Service d'intégration exchange - READ ONLY |
| `user_settings.json` | Fichier de configuration utilisateur - à protéger avec atomic writes |
| `strategies.json` | Configuration des stratégies - à protéger avec atomic writes |
| `docs/project-context.md` | Contraintes et règles du projet |

### Technical Decisions

**1. Gestion d'Erreur 503 - Messages Spécifiques :**
- Chaque endpoint doit avoir un message d'erreur contextuel
- Exemples :
  - `/api/engine/start` → "Cannot start engine - bot not connected"
  - `/api/status` → "Cannot fetch status - bot not connected"
  - `/api/switch_symbol` → "Cannot switch symbol - bot not connected"
- Format : `HTTPException(status_code=503, detail="<message spécifique>")`

**2. Storage Service - Simple et Maintenable :**
- Service générique `atomic_write_json(path: str, data: dict)` pour la base
- Méthodes spécialisées pour chaque type de fichier :
  - `save_user_settings(settings: dict)`
  - `load_user_settings() -> dict`
  - `save_strategies(strategies: dict)`
  - `load_strategies() -> dict`
- Pattern : temp file → write → fsync → rename (atomic)

**3. Tests Automatisés - pytest :**
- Créer `backend/tests/` avec structure :
  - `test_engine.py` : start/stop/restart/panic
  - `test_trading.py` : switch_symbol, enable/disable trading
  - `test_settings.py` : get/update global settings, scanner settings
  - `test_storage.py` : atomic writes, concurrent access
- Utiliser pytest fixtures pour mock bot_bridge
- Tests d'intégration pour les flux end-to-end

**4. Hot-Reload Settings - Automatique :**
- Utiliser `watchdog` library pour surveiller user_settings.json
- Callback qui recharge les settings dans BotContext quand le fichier change
- Implémentation dans `services/settings_watcher.py`
- Démarrage automatique au startup de l'API

**5. CORS Localhost-Only :**
- Remplacer `allow_origins=["*"]` par liste explicite :
  ```python
  allow_origins=[
      "http://localhost:3000",  # Next.js dev
      "http://localhost:8001",  # API
      "http://127.0.0.1:3000",
      "http://127.0.0.1:8001"
  ]
  ```
- Pas de variable d'environnement nécessaire (toujours localhost)

## Implementation Plan

### Tasks

#### Phase 1: Suppression du Dual State (Étapes 1-2)

**Task 1.1: Supprimer la classe BotState et bot_state.json**
- File: `backend/api.py`
- Action: Supprimer complètement la classe `BotState` (lignes 205-289)
- Action: Supprimer l'instanciation `bot_state = BotState()` (ligne 291)
- Action: Supprimer toutes les références à `bot_state.save_state()`, `bot_state.load_state()`
- Action: Supprimer le fichier `bot_state.json` s'il existe

**Task 1.2: Supprimer la fonction _execute_bot_action**
- File: `backend/api.py`
- Action: Supprimer la fonction `_execute_bot_action()` (lignes 341-354)
- Action: Identifier tous les appels à cette fonction dans les endpoints

**Task 1.3: Créer api/dependencies.py avec get_bot_context()**
- File: `backend/api/dependencies.py` (NEW)
- Action: Créer le fichier avec la dépendance `get_bot_context()`
- Code:
  ```python
  from fastapi import HTTPException, Depends
  from backend.bot_bridge import bot_bridge
  
  def get_bot_context():
      """Dependency to get bot context. Raises 503 if not connected."""
      if not bot_bridge or not bot_bridge.is_connected():
          raise HTTPException(
              status_code=503,
              detail="Bot engine not connected - service unavailable"
          )
      return bot_bridge.get_bot_context()
  ```

#### Phase 2: Restructuration en Architecture Modulaire (Étapes 3-4)

**Task 2.1: Créer la structure de dossiers**
- Action: Créer `backend/api/` avec `__init__.py`, `main.py`, `dependencies.py`
- Action: Créer `backend/api/routers/` avec `__init__.py`
- Action: Créer `backend/core/` (si n'existe pas) avec `exceptions.py`
- Action: Créer `backend/services/` avec `__init__.py`
- Action: Créer `backend/models/` avec `__init__.py`, `api_models.py`
- Action: Créer `backend/utils/` avec `__init__.py`

**Task 2.2: Créer backend/models/api_models.py**
- File: `backend/models/api_models.py` (NEW)
- Action: Migrer tous les Pydantic models depuis api.py :
  - `BotStatus`
  - `GlobalSettingsModel`
  - `ScannerSettingsModel`
  - `StrategySelectModel`
- Action: Ajouter tous les request models manquants (actuellement dict)

**Task 2.3: Créer backend/api/routers/engine.py**
- File: `backend/api/routers/engine.py` (NEW)
- Action: Extraire les endpoints engine depuis api.py :
  - `POST /api/engine/start`
  - `POST /api/engine/stop`
  - `POST /api/engine/restart`
  - `POST /api/engine/panic`
- Action: Utiliser `Depends(get_bot_context)` pour chaque endpoint
- Action: Messages d'erreur 503 spécifiques pour chaque endpoint

**Task 2.4: Créer backend/api/routers/trading.py**
- File: `backend/api/routers/trading.py` (NEW)
- Action: Extraire les endpoints trading :
  - `POST /api/trading/enable`
  - `POST /api/trading/disable`
  - `POST /api/switch_symbol`
  - `POST /api/close_trade` (si existe)
  - `POST /api/manual_trade` (si existe)
- Action: Utiliser Pydantic models pour les request bodies

**Task 2.5: Créer backend/api/routers/market.py**
- File: `backend/api/routers/market.py` (NEW)
- Action: Extraire les endpoints market data :
  - `GET /api/candles`
  - `GET /api/market_data`
  - `GET /api/metrics`
  - `GET /api/positions`
  - `GET /api/balance`

**Task 2.6: Créer backend/api/routers/settings.py**
- File: `backend/api/routers/settings.py` (NEW)
- Action: Extraire les endpoints settings :
  - `GET /api/settings/global`
  - `POST /api/settings/global`
  - `GET /api/settings/scanner`
  - `POST /api/settings/scanner`
  - `POST /api/settings/update` (si existe)

**Task 2.7: Créer backend/api/routers/history.py**
- File: `backend/api/routers/history.py` (NEW)
- Action: Extraire les endpoints historiques :
  - `GET /api/trades`
  - `GET /api/fills`
  - `GET /api/logs`
  - `GET /api/equity_curve`
  - `GET /api/sentiment`

**Task 2.8: Créer backend/api/main.py**
- File: `backend/api/main.py` (NEW)
- Action: Créer l'application FastAPI principale
- Action: Configurer CORS avec localhost-only
- Action: Inclure tous les routers
- Action: Configurer les middlewares
- Action: Gérer le startup event (bot initialization)

#### Phase 3: Service de Storage Atomique (Étape 7)

**Task 3.1: Créer backend/services/storage.py**
- File: `backend/services/storage.py` (NEW)
- Action: Implémenter `atomic_write_json(path, data)`
- Action: Implémenter `save_user_settings(settings)`
- Action: Implémenter `load_user_settings()`
- Action: Implémenter `save_strategies(strategies)`
- Action: Implémenter `load_strategies()`
- Code pattern:
  ```python
  import os
  import json
  import tempfile
  
  def atomic_write_json(path: str, data: dict):
      """Atomic JSON write using temp file + rename."""
      dir_path = os.path.dirname(path)
      with tempfile.NamedTemporaryFile(
          mode='w', 
          dir=dir_path, 
          delete=False,
          suffix='.tmp'
      ) as tmp:
          json.dump(data, tmp, indent=2)
          tmp.flush()
          os.fsync(tmp.fileno())
          tmp_path = tmp.name
      os.replace(tmp_path, path)  # Atomic rename
  ```

**Task 3.2: Migrer toutes les écritures JSON vers storage.py**
- Files: Tous les routers qui écrivent dans user_settings.json, strategies.json
- Action: Remplacer `json.dump()` direct par `storage.save_user_settings()`
- Action: Remplacer `json.load()` direct par `storage.load_user_settings()`

#### Phase 4: Hot-Reload des Settings (Étape 8)

**Task 4.1: Créer backend/services/settings_watcher.py**
- File: `backend/services/settings_watcher.py` (NEW)
- Action: Implémenter file watcher avec `watchdog`
- Action: Callback qui recharge settings dans BotContext
- Code pattern:
  ```python
  from watchdog.observers import Observer
  from watchdog.events import FileSystemEventHandler
  
  class SettingsFileHandler(FileSystemEventHandler):
      def on_modified(self, event):
          if event.src_path.endswith('user_settings.json'):
              # Reload settings into bot context
              pass
  ```

**Task 4.2: Intégrer le watcher au startup**
- File: `backend/api/main.py`
- Action: Démarrer le settings watcher dans le startup event
- Action: Arrêter le watcher dans le shutdown event

#### Phase 5: Nettoyage et Optimisations (Étape 9)

**Task 5.1: Supprimer sanitize_for_json()**
- Files: Tous les fichiers utilisant `sanitize_for_json()`
- Action: Remplacer par Pydantic `.model_dump()` ou `jsonable_encoder()`
- Action: Supprimer la fonction `sanitize_for_json()` de api.py

**Task 5.2: Nettoyer les imports conditionnels**
- Files: `backend/api/main.py` et routers
- Action: Déplacer tous les imports au début des fichiers
- Action: Supprimer les try/except global autour des imports
- Action: Laisser l'application crasher proprement si imports critiques manquent

**Task 5.3: Uniformiser les logs**
- Files: Tous les routers
- Action: Utiliser `logger.info()`, `logger.warning()`, `logger.error()`
- Action: Ajouter structured fields quand possible : `logger.info("Action", extra={"symbol": symbol})`

#### Phase 6: Tests Automatisés (Étape 3)

**Task 6.1: Créer backend/tests/conftest.py**
- File: `backend/tests/conftest.py` (NEW)
- Action: Créer fixtures pytest :
  - `mock_bot_bridge` : Mock du bot_bridge
  - `test_client` : TestClient FastAPI
  - `mock_bot_context` : Mock du BotContext

**Task 6.2: Créer backend/tests/test_engine.py**
- File: `backend/tests/test_engine.py` (NEW)
- Action: Tests pour `/api/engine/start`, `/stop`, `/restart`, `/panic`
- Action: Test du comportement 503 quand bot_bridge non connecté
- Action: Test des messages d'erreur spécifiques

**Task 6.3: Créer backend/tests/test_trading.py**
- File: `backend/tests/test_trading.py` (NEW)
- Action: Tests pour switch_symbol, enable/disable trading
- Action: Tests de validation des symboles

**Task 6.4: Créer backend/tests/test_settings.py**
- File: `backend/tests/test_settings.py` (NEW)
- Action: Tests pour GET/POST global settings
- Action: Tests pour GET/POST scanner settings
- Action: Tests de validation des Pydantic models

**Task 6.5: Créer backend/tests/test_storage.py**
- File: `backend/tests/test_storage.py` (NEW)
- Action: Tests d'écriture atomique
- Action: Tests de concurrent access
- Action: Tests de rollback en cas d'erreur

**Task 6.6: Créer backend/tests/test_status.py**
- File: `backend/tests/test_status.py` (NEW)
- Action: Tests pour `/api/status`
- Action: Tests de la structure BotStatus
- Action: Tests des métriques (daily_pnl, margin_usage, etc.)

### Acceptance Criteria

**AC1: Dual State Complètement Éliminé**
- Given: Le backend est démarré
- When: bot_bridge n'est pas connecté
- Then: Tous les endpoints retournent 503 avec message spécifique
- And: Aucune référence à BotState ou bot_state.json dans le code
- And: Aucun fallback vers standalone mode

**AC2: Architecture Modulaire Propre**
- Given: Le code backend est organisé
- When: Je navigue dans backend/
- Then: Je trouve la structure :
  - `api/main.py` (< 100 lignes)
  - `api/routers/` (6 fichiers, chacun < 200 lignes)
  - `services/storage.py`, `services/settings_watcher.py`
  - `models/api_models.py`
  - `api/dependencies.py`
- And: Aucun fichier > 300 lignes

**AC3: Storage Atomique Fonctionnel**
- Given: Le service storage est implémenté
- When: J'appelle `POST /api/settings/global` avec nouvelles settings
- Then: user_settings.json est mis à jour atomiquement (temp + rename)
- And: En cas d'erreur, le fichier original n'est pas corrompu
- And: Les écritures concurrentes ne causent pas de race condition

**AC4: Hot-Reload Automatique**
- Given: Le bot est en cours d'exécution
- When: Je modifie user_settings.json manuellement
- Then: Le BotContext recharge automatiquement les settings dans les 2 secondes
- And: Un log confirme le rechargement : "Settings reloaded from file"

**AC5: Tests Automatisés Passent**
- Given: La suite de tests pytest est créée
- When: J'exécute `pytest backend/tests/`
- Then: Tous les tests passent (100% success)
- And: Coverage des flux critiques > 80%
- And: Tests incluent : engine, trading, settings, storage, status

**AC6: CORS Localhost-Only**
- Given: L'API est configurée
- When: Je vérifie la configuration CORS
- Then: `allow_origins` contient uniquement localhost:3000, localhost:8001, 127.0.0.1:3000, 127.0.0.1:8001
- And: Aucun wildcard "*" n'est présent

**AC7: Pydantic Models Partout**
- Given: Les endpoints sont refactorés
- When: Je vérifie tous les endpoints POST/PUT
- Then: Chaque endpoint utilise un Pydantic model pour le request body
- And: Chaque endpoint avec response_model utilise un Pydantic model
- And: Aucun endpoint n'accepte `dict` brut

**AC8: Logs Structurés**
- Given: Le code utilise le logger
- When: J'exécute une action (start, stop, switch symbol)
- Then: Les logs utilisent logger.info/warning/error
- And: Les logs incluent du contexte structuré quand pertinent
- And: Aucun `print()` n'est utilisé (sauf debug temporaire)

**AC9: Pas de Code Mort**
- Given: Le refactoring est terminé
- When: Je scanne le code
- Then: Aucune fonction/classe inutilisée n'existe
- And: Aucun import inutilisé
- And: Aucun commentaire de code mort (# old code...)

**AC10: Fonctionnalités 100% Préservées**
- Given: Le refactoring est terminé
- When: Je teste manuellement tous les flux critiques :
  - Start/Stop/Restart engine
  - Switch symbol
  - Panic close
  - Update global settings
  - Update scanner settings
  - Fetch status
- Then: Toutes les fonctionnalités fonctionnent exactement comme avant
- And: Aucune régression détectée

## Additional Context

### Dependencies

**Nouvelles Dépendances à Ajouter :**
- `watchdog` : Pour le file watching (hot-reload settings)
- `pytest` : Pour les tests automatisés
- `pytest-asyncio` : Pour tester les endpoints async
- `httpx` : Pour TestClient FastAPI

**Dépendances Existantes à Utiliser :**
- `fastapi` : Framework API
- `pydantic` : Validation et serialization
- `uvicorn` : ASGI server

### Testing Strategy

**Structure des Tests :**
```
backend/tests/
├── conftest.py           # Fixtures pytest
├── test_engine.py        # Tests engine endpoints
├── test_trading.py       # Tests trading endpoints
├── test_settings.py      # Tests settings endpoints
├── test_storage.py       # Tests atomic storage
├── test_status.py        # Tests status endpoint
└── test_integration.py   # Tests end-to-end
```

**Approche de Test :**
1. **Unit Tests** : Chaque router testé isolément avec mock bot_bridge
2. **Integration Tests** : Flux end-to-end avec vrai bot_bridge (si possible)
3. **Error Handling Tests** : Vérifier les 503, 400, 500 appropriés
4. **Concurrency Tests** : Tester les écritures atomiques sous charge

**Commande de Test :**
```bash
# Tous les tests
pytest backend/tests/ -v

# Avec coverage
pytest backend/tests/ --cov=backend --cov-report=html

# Tests spécifiques
pytest backend/tests/test_engine.py -v
```

### Notes

**Ordre d'Exécution Recommandé :**
1. Phase 1 (Suppression dual state) - CRITIQUE, à faire en premier
2. Phase 2 (Restructuration) - Découper progressivement
3. Phase 3 (Storage atomique) - Sécuriser les écritures
4. Phase 4 (Hot-reload) - Feature additionnelle
5. Phase 5 (Nettoyage) - Polish final
6. Phase 6 (Tests) - Validation continue

**Stratégie de Commit :**
- Un commit par task (granularité fine)
- Messages de commit descriptifs : "feat: add engine router with 503 handling"
- Tests dans le même commit que le code (TDD si possible)

**Points d'Attention :**
- ⚠️ Ne JAMAIS modifier app/, strategies/ (IMMUTABLE)
- ⚠️ Tester manuellement après chaque phase
- ⚠️ Garder l'API compatible avec le frontend existant (pas de breaking changes)
- ⚠️ Vérifier que StateManager.save_state() est toujours appelé après modifications du bot

**Rollback Strategy :**
- Garder une copie de backend/api.py original
- Tester chaque phase avant de passer à la suivante
- En cas de problème critique, revenir au commit précédent

**Performance Considerations :**
- Le file watcher (watchdog) a un overhead minimal (< 1% CPU)
- Les écritures atomiques ajoutent ~5ms par write (acceptable)
- Les tests ne doivent pas ralentir le développement (< 30s pour toute la suite)
