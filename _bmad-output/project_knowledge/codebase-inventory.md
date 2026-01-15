# Codebase Inventory & Utility Analysis

## 📂 Root Directory
| File/Folder | Status | Utility Analysis |
| :--- | :--- | :--- |
| `main_nextjs.py` | ✅ **VITAL** | The heart of the bot. Monolithic but essential currently. |
| `start_integrated.sh` | ✅ **VITAL** | Primary startup script for PM2. |
| `ecosystem.config.js` | ✅ **VITAL** | PM2 configuration for process management. |
| `strategies.json` | ✅ **VITAL** | Configuration persistence for strategy parameters. |
| `.env` | ✅ **VITAL** | Secrets and config. |
| `app/` | ✅ **VITAL** | Core application logic (Services, Risk, Strategies). |
| `backend/` | ✅ **VITAL** | FastAPI server and bridge. |
| `utils/` | ⚠️ **REDUNDANT** | Seems to be a legacy artifact. Logic moved to `app/utils`. |
| `_legacy_backup/` | 🗑️ **JUNK** | Old backup. Safe to archive/delete after verification. |
| `bot_activity.log` | ℹ️ **TEMP** | Runtime logs. Safe to clear. |
| `data/` | ℹ️ **DATA** | Storage for local CSVs/JSONs (Trade history). |
| `docs/` | ℹ️ **DOCS** | Old documentation. Potentially superseded by `_bmad-output`. |

## 📂 Backend (`backend/`)
| File/Folder | Status | Utility Analysis |
| :--- | :--- | :--- |
| `api.py` | ✅ **VITAL** | The API Entry point. |
| `bot_bridge.py` | ✅ **VITAL** | Connects API to the Main Loop. |
| `market_data.py` | ✅ **VITAL** | Helper for data fetching. |
| `api_optimizations.py`| ✅ **VITAL** | Middleware and caching logic. |
| `routes/` | ✅ **VITAL** | Modular routes (scanner). |
| `api.py.backup` | 🗑️ **JUNK** | Large backup file (94KB). Safe to delete. |

## 📂 App Structure (`app/`)
| Folder | Status | Analysis |
| :--- | :--- | :--- |
| `services/` | ✅ **VITAL** | `hyperliquid_service`, `ia`, `discord`. Core logic. |
| `core/` | ✅ **VITAL** | `config`, `risk_manager`, `state_manager`. Essential. |
| `utils/` | ✅ **VITAL** | Modern utilities (`retry_decorator`, `websocket_manager`). |

## 🛠️ Cleanup Recommendations
1. **Delete**: `backend/api.py.backup`, `utils/` (root folder, if empty/duplicate).
2. **Archive**: `_legacy_backup/` (Move out of active workspace or delete).
3. **Consolidate**: `docs/` content should be merged into `_bmad-output/project_knowledge`.

## ⚠️ Specific Attention Needed
- **`utils` vs `app/utils`**: The root `utils` folder is likely a remnant of an older structure. Recommendation: Verify emptiness/redundancy and delete.
