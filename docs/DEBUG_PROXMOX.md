# 🔍 Guide de Débogage - Problèmes de Persistance et Trading

## Problèmes Identifiés

### 1. La persistance de l'automatisme Hyperliquid ne fonctionne pas
### 2. Aucun trade n'a été pris

---

## 📊 Diagnostic sur le Serveur Proxmox

Connectez-vous au serveur et exécutez ces commandes pour diagnostiquer :

```bash
# Se connecter au serveur Proxmox
ssh user@IP_PROXMOX

# Aller dans le dossier du bot
cd /var/www/novabot

# 1. Vérifier l'état du service
sudo systemctl status novabot

# 2. Voir les logs récents
sudo journalctl -u novabot --since "today" --no-pager

# 3. Vérifier le fichier bot_state.json
cat bot_state.json

# 4. Vérifier les stratégies
cat strategies.json

# 5. Copier le diagnostic script
# (Copiez le contenu de diagnostic.py depuis votre machine locale)
nano diagnostic.py
# Collez le contenu, puis Ctrl+X, Y, Entrée

# 6. Exécuter le diagnostic
python3 diagnostic.py
```

---

## 🔧 Corrections à Appliquer

Les modifications que j'ai faites corrigent deux bugs critiques :

### Bug 1 : Persistance du mode "Auto (Hyperliquid)"
**Fichier:** `app/ui/sidebar.py`

Le mode d'exécution n'était pas persisté. À chaque redémarrage, il revenait sur "Manual (Phantom)".

### Bug 2 : Persistance du checkbox "ALLOW LIVE TRADING"
**Fichier:** `app/ui/sidebar.py`

Le checkbox était hardcodé à `value=False`, donc même si vous l'activiez, il se désactivait au redémarrage.

---

## 🚀 Déployer les Corrections sur Proxmox

### Option 1 : Pull depuis Git (Recommandé)

```bash
# Sur le serveur Proxmox
cd /var/www/novabot

# Arrêter le service
sudo systemctl stop novabot

# Sauvegarder l'état actuel
sudo cp bot_state.json bot_state.json.backup

# Pull les dernières modifications
sudo -u www-data git pull origin master

# Redémarrer le service
sudo systemctl start novabot

# Vérifier que tout fonctionne
sudo systemctl status novabot
sudo journalctl -u novabot -f
```

### Option 2 : Modification Manuelle (Si pas encore commit)

Si les modifications ne sont pas encore dans Git, vous pouvez les appliquer manuellement :

```bash
# Sur le serveur Proxmox
cd /var/www/novabot

# Arrêter le service
sudo systemctl stop novabot

# Éditer sidebar.py
sudo nano app/ui/sidebar.py
```

**Modifications à faire dans `app/ui/sidebar.py` :**

1. Ligne ~68-76, remplacer :
```python
# 4. Hybrid Mode
st.sidebar.subheader("Execution Mode")
mode = st.sidebar.radio("Mode", ["Manual (Phantom)", "Auto (Hyperliquid)"])

can_trade = False
if mode == "Auto (Hyperliquid)":
    can_trade = st.sidebar.checkbox("✅ ALLOW LIVE TRADING", value=False, help="...")
```

Par :
```python
# 4. Hybrid Mode
st.sidebar.subheader("Execution Mode")

# Restore mode from persisted settings
default_mode = st.session_state.get('execution_mode', persisted_settings.get('execution_mode', 'Manual (Phantom)'))
mode_options = ["Manual (Phantom)", "Auto (Hyperliquid)"]
mode_index = mode_options.index(default_mode) if default_mode in mode_options else 0
mode = st.sidebar.radio("Mode", mode_options, index=mode_index, key='execution_mode')

can_trade = False
if mode == "Auto (Hyperliquid)":
    # Restore trading_enabled from persisted settings
    default_trading_enabled = st.session_state.get('trading_enabled', persisted_settings.get('trading_enabled', False))
    can_trade = st.sidebar.checkbox("✅ ALLOW LIVE TRADING", value=default_trading_enabled, key='trading_enabled', help="...")
```

2. Ligne ~135-145, dans le return, ajouter :
```python
return {
    "is_running": is_running,
    "asset": selected_asset,
    "mode": mode,
    "execution_mode": mode,  # AJOUTER CETTE LIGNE
    "trading_enabled": can_trade,
    # ... reste inchangé
}
```

**Modifications à faire dans `main.py` :**

Ligne ~187-194, remplacer :
```python
ctx.sidebar_settings = {
    "size_type": sidebar_state.get("size_type"),
    "size_value": sidebar_state.get("size_value"),
    "leverage": sidebar_state.get("leverage"),
    "max_positions": sidebar_state.get("max_positions"),
    "daily_stop_loss": sidebar_state.get("daily_stop_loss")
}
```

Par :
```python
ctx.sidebar_settings = {
    "execution_mode": sidebar_state.get("execution_mode"),  # AJOUTER
    "trading_enabled": sidebar_state.get("trading_enabled"),  # AJOUTER
    "size_type": sidebar_state.get("size_type"),
    "size_value": sidebar_state.get("size_value"),
    "leverage": sidebar_state.get("leverage"),
    "max_positions": sidebar_state.get("max_positions"),
    "daily_stop_loss": sidebar_state.get("daily_stop_loss")
}
```

Puis redémarrer :
```bash
sudo systemctl start novabot
```

---

## ✅ Vérification Post-Déploiement

1. **Accéder à l'interface** : `http://IP_PROXMOX:8501`

2. **Configurer le bot** :
   - Activer "START ENGINE"
   - Sélectionner "Auto (Hyperliquid)"
   - Cocher "✅ ALLOW LIVE TRADING"
   - Configurer les paramètres de risque

3. **Redémarrer le service** pour tester la persistance :
   ```bash
   sudo systemctl restart novabot
   ```

4. **Vérifier que les paramètres sont conservés** :
   - Recharger l'interface web
   - Vérifier que "Auto (Hyperliquid)" et "ALLOW LIVE TRADING" sont toujours actifs
   - Vérifier `bot_state.json` :
     ```bash
     cat bot_state.json | grep -A 10 sidebar_settings
     ```

---

## 📝 Checklist de Vérification

- [ ] Le service novabot est actif (`systemctl status novabot`)
- [ ] Les logs ne montrent pas d'erreurs (`journalctl -u novabot -f`)
- [ ] `bot_state.json` contient `"execution_mode": "Auto (Hyperliquid)"`
- [ ] `bot_state.json` contient `"trading_enabled": true`
- [ ] L'interface web est accessible
- [ ] Les paramètres persistent après un redémarrage du service
- [ ] Des signaux sont générés (visible dans les logs)
- [ ] Les trades sont exécutés (si signaux valides)

---

## 🐛 Problèmes Courants

### Le bot ne prend toujours pas de trades

Vérifiez dans l'ordre :

1. **Engine démarré ?** → Checkbox "START ENGINE" doit être ON
2. **Mode correct ?** → Doit être "Auto (Hyperliquid)"
3. **Trading activé ?** → Checkbox "ALLOW LIVE TRADING" doit être coché
4. **Données reçues ?** → Vérifier les logs : `journalctl -u novabot -f`
5. **Stratégies actives ?** → Vérifier `strategies.json`
6. **Signaux générés ?** → Regarder dans l'interface ou les logs
7. **Risk Manager bloque ?** → Vérifier daily_pnl et is_stop_mode dans bot_state.json

### La persistance ne fonctionne toujours pas

1. Vérifier les permissions du fichier :
   ```bash
   ls -la bot_state.json
   # Doit être accessible en écriture par www-data
   sudo chown www-data:www-data bot_state.json
   ```

2. Vérifier que StateManager.save_state() est appelé :
   ```bash
   sudo journalctl -u novabot | grep "State"
   ```
