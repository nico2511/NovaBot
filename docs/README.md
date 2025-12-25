# 📚 Documentation Index

## 🚀 Démarrage rapide

### Pour utiliser le bot avec Next.js (Recommandé)
1. **[GUIDE_FINAL.md](GUIDE_FINAL.md)** - Guide complet d'utilisation
2. **[README_NEXTJS.md](README_NEXTJS.md)** - Installation et configuration

### Pour utiliser Streamlit (Backup)
- Lancer : `streamlit run main.py`

---

## 📖 Documentation principale

### Migration et architecture
- **[FINAL_SUMMARY.md](FINAL_SUMMARY.md)** - Résumé complet de la migration
- **[MIGRATION.md](MIGRATION.md)** - Détails de la migration Streamlit → Next.js
- **[STATUS_FINAL.md](STATUS_FINAL.md)** - État final du projet

### Améliorations
- **[IMPROVEMENTS.md](IMPROVEMENTS.md)** - Liste des améliorations apportées
- **[MIGRATION_SESSION.md](MIGRATION_SESSION.md)** - Journal de la session de migration

---

## 🔧 Guides techniques

### Déploiement
- **[DEPLOY_PROXMOX.md](DEPLOY_PROXMOX.md)** - Déploiement sur Proxmox
- **[DEBUG_PROXMOX.md](DEBUG_PROXMOX.md)** - Debugging Proxmox

### Résolution de problèmes
- **[RESTART_NEEDED.md](RESTART_NEEDED.md)** - Quand redémarrer le backend
- **[FIX_PERSISTENCE.md](FIX_PERSISTENCE.md)** - Fix persistance des données

---

## 📝 Autres documents

### Historique
- **[SUMMARY_2025-12-25.md](SUMMARY_2025-12-25.md)** - Résumé du 25 décembre
- **[project_documentation.md](project_documentation.md)** - Documentation projet
- **[THEME.md](THEME.md)** - Thème UI

---

## 🎯 Liens rapides

### Interfaces
- **Next.js UI** : http://localhost:3000
- **API Docs** : http://localhost:8000/docs
- **Streamlit** : http://localhost:8501

### Commandes
```bash
# Mode intégré (bot + API + UI)
./start_integrated.sh

# Mode standalone (API + UI seulement)
./start_nextjs.sh

# Streamlit backup
streamlit run main.py
```

---

## 📂 Structure du projet

```
PyBot/
├── backend/          # FastAPI backend
├── frontend/         # Next.js frontend
├── app/             # Bot Python core
├── strategies/      # Trading strategies
├── docs/            # Documentation (ce dossier)
├── main.py          # Streamlit (backup)
└── main_nextjs.py   # Bot intégré avec Next.js
```

---

## ✅ Documents à consulter en priorité

1. **[GUIDE_FINAL.md](GUIDE_FINAL.md)** - Pour démarrer
2. **[FINAL_SUMMARY.md](FINAL_SUMMARY.md)** - Pour comprendre l'architecture
3. **[README_NEXTJS.md](README_NEXTJS.md)** - Pour la configuration

---

## 🗑️ Documents obsolètes (supprimés)

Les documents suivants ont été supprimés car obsolètes :
- Anciennes versions de migration
- Docs de debug résolus
- Guides temporaires

---

**Dernière mise à jour** : 25 décembre 2025
**Version** : 2.0 (Next.js intégré)
