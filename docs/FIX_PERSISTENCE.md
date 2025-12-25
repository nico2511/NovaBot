# 🔧 Correction de la Persistance - Résumé

## 📊 Problème Identifié

**Symptôme:** Le checkbox "✅ ALLOW LIVE TRADING" n'est pas coché après un redémarrage de l'application, même si vous l'aviez activé avant.

**Cause racine:** 
1. Streamlit réinitialise `st.session_state` à chaque redémarrage de l'application
2. L'ancien code utilisait `value=default_trading_enabled` dans le checkbox, mais cette approche ne fonctionne pas correctement avec les widgets qui ont un `key=` parameter
3. Le check `if 'settings_initialized' not in st.session_state` était inutile car `settings_initialized` était aussi perdu au redémarrage

## ✅ Solution Appliquée

### Changement dans `app/ui/sidebar.py`

**Avant:**
```python
# Initialize session state from persisted settings on first load
if 'settings_initialized' not in st.session_state:
    st.session_state.settings_initialized = True
    for key, value in persisted_settings.items():
        if key not in st.session_state:
            st.session_state[key] = value

# Plus tard...
default_trading_enabled = st.session_state.get('trading_enabled', persisted_settings.get('trading_enabled', False))
can_trade = st.sidebar.checkbox("✅ ALLOW LIVE TRADING", value=default_trading_enabled, key='trading_enabled', ...)
```

**Après:**
```python
# Always restore persisted values to session state if they don't exist
# This happens on every app restart since session_state is cleared
for key, value in persisted_settings.items():
    if key not in st.session_state:
        st.session_state[key] = value

# Plus tard...
# Initialize trading_enabled in session state if not present (from persisted settings)
# This MUST happen BEFORE the checkbox is created
if 'trading_enabled' not in st.session_state:
    st.session_state.trading_enabled = persisted_settings.get('trading_enabled', False)

can_trade = st.sidebar.checkbox("✅ ALLOW LIVE TRADING", key='trading_enabled', ...)
```

### Pourquoi ça fonctionne maintenant ?

1. **Initialisation systématique:** À chaque démarrage, on restaure TOUS les paramètres de `persisted_settings` dans `session_state`
2. **Ordre correct:** On initialise `st.session_state['trading_enabled']` **AVANT** de créer le widget
3. **Pas de `value=`:** Quand un widget Streamlit a un `key=`, il utilise automatiquement `st.session_state[key]` comme valeur. Pas besoin de `value=`

## 🚀 Déploiement sur Proxmox

### Étape 1: Pull les modifications

```bash
ssh user@IP_PROXMOX
cd /var/www/novabot
sudo systemctl stop novabot
sudo -u www-data git pull origin master
```

### Étape 2: Activer le trading automatique

**Option A: Via l'interface web** (Recommandé)
1. Démarrer le service: `sudo systemctl start novabot`
2. Aller sur `http://IP_PROXMOX:8501`
3. Sélectionner "Auto (Hyperliquid)"
4. Cocher "✅ ALLOW LIVE TRADING"
5. Les paramètres seront automatiquement sauvegardés dans `bot_state.json`

**Option B: Via script** (Pour tester rapidement)
```bash
# Copier le script enable_auto_trading.py sur le serveur
# Puis l'exécuter:
cd /var/www/novabot
python3 enable_auto_trading.py
```

### Étape 3: Tester la persistance

```bash
# Redémarrer le service
sudo systemctl restart novabot

# Vérifier les logs
sudo journalctl -u novabot -f

# Vérifier bot_state.json
cat bot_state.json | grep -A 10 sidebar_settings
```

Vous devriez voir:
```json
"sidebar_settings": {
    "execution_mode": "Auto (Hyperliquid)",
    "trading_enabled": true,
    ...
}
```

### Étape 4: Vérifier dans l'interface

1. Recharger `http://IP_PROXMOX:8501`
2. Vérifier que "Auto (Hyperliquid)" est sélectionné ✅
3. Vérifier que "✅ ALLOW LIVE TRADING" est coché ✅

## 🧪 Scripts de Test Fournis

### `diagnostic.py`
Affiche l'état complet du bot et identifie les problèmes de configuration.
```bash
python3 diagnostic.py
```

### `test_persistence.py`
Simule la logique de restauration pour vérifier qu'elle fonctionne.
```bash
python3 test_persistence.py
```

### `enable_auto_trading.py`
Active automatiquement le trading dans `bot_state.json`.
```bash
python3 enable_auto_trading.py
```

## 📝 Checklist de Vérification

- [ ] Code mis à jour sur le serveur (`git pull`)
- [ ] Service redémarré
- [ ] "Auto (Hyperliquid)" sélectionné dans l'interface
- [ ] "✅ ALLOW LIVE TRADING" coché dans l'interface
- [ ] `bot_state.json` contient `"execution_mode": "Auto (Hyperliquid)"`
- [ ] `bot_state.json` contient `"trading_enabled": true` (dans sidebar_settings)
- [ ] Après redémarrage du service, les paramètres sont toujours actifs
- [ ] Les logs montrent que le bot génère des signaux
- [ ] Les trades sont exécutés (si signaux valides)

## 🐛 Troubleshooting

### Le checkbox n'est toujours pas coché après redémarrage

1. Vérifier que `bot_state.json` contient bien les bonnes valeurs:
   ```bash
   cat bot_state.json | python3 -m json.tool | grep -A 10 sidebar_settings
   ```

2. Vérifier les permissions du fichier:
   ```bash
   ls -la bot_state.json
   sudo chown www-data:www-data bot_state.json
   ```

3. Vérifier les logs pour voir si la restauration se fait:
   ```bash
   sudo journalctl -u novabot | grep -i "state\|persist\|restored"
   ```

### Les trades ne sont toujours pas pris

Vérifier dans l'ordre:
1. Engine démarré ? (checkbox "START ENGINE")
2. Mode = "Auto (Hyperliquid)" ?
3. "ALLOW LIVE TRADING" coché ?
4. Données reçues ? (regarder les logs)
5. Stratégies actives ? (vérifier strategies.json)
6. Signaux générés ? (visible dans l'interface)
7. Risk Manager ne bloque pas ? (vérifier daily_pnl et is_stop_mode)

## 📚 Documentation

- Guide de déploiement: `docs/DEPLOY_PROXMOX.md`
- Guide de débogage: `docs/DEBUG_PROXMOX.md`

## 🎯 Prochaines Étapes

1. **Déployer** les corrections sur Proxmox
2. **Activer** le trading automatique via l'interface
3. **Tester** la persistance en redémarrant le service
4. **Monitorer** les logs pour vérifier que tout fonctionne
5. **Vérifier** que des trades sont pris quand des signaux sont générés

---

**Date de la correction:** 2025-12-25
**Commit:** aa51d13 - "Fix: Corrected session_state initialization for trading_enabled persistence"
