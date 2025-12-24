# 🚀 Déploiement de NovaBot sur Proxmox (LXC/VM)

Ce guide détaille la procédure pour remplacer l'ancien service `novasignal` par la nouvelle version `NovaBot` sur votre conteneur Proxmox.

## 📋 Pré-requis
*   Accès SSH au conteneur Proxmox.
*   L'adresse du dépôt Git : `https://github.com/nico2511/NovaBot.git`
*   Votre fichier `.env` local (contenant les clés API).

---

## 1. Nettoyage de l'Ancienne Version (`novasignal`)

Connectez-vous à votre conteneur et exécutez ces commandes pour arrêter et supprimer l'ancien bot.

```bash
# Arrêter le service
sudo systemctl stop novasignal

# Désactiver le démarrage automatique
sudo systemctl disable novasignal

# Supprimer le fichier de service
sudo rm /etc/systemd/system/novasignal.service
sudo systemctl daemon-reload

# (Optionnel) Supprimer les anciens fichiers
# sudo rm -rf /chemin/vers/ancien/dossier
```

# Installer le bot dans /var/www/novabot
# (Ou /var/www directement si vous préférez, mais un sous-dossier est recommandé)

```bash
# Installer Git et Python venv
sudo apt update && sudo apt install -y git python3-venv python3-pip

# Cloner le dépôt
cd /var/www
sudo git clone https://github.com/nico2511/NovaBot.git novabot
# Dossier final : /var/www/novabot

# Permissions (www-data est standard pour /var/www, ou root)
sudo chown -R www-data:www-data /var/www/novabot
cd /var/www/novabot

# Créer l'environnement virtuel
sudo -u www-data python3 -m venv venv

# Installer les dépendances
sudo -u www-data ./venv/bin/pip install -r requirements.txt
```

## 3. Configuration des Secrets (.env)

⚠️ **Important :** Vous devez recréer le fichier `.env` sur le serveur car il n'est pas dans Git pour des raisons de sécurité.

**Méthode Rapide (Copier-Coller) :**
Depuis votre machine locale, affichez votre `.env` et copiez le contenu :
```bash
cat .env
```
Puis sur le serveur Proxmox :
```bash
sudo nano /var/www/novabot/.env
# Collez le contenu, puis Ctrl+X, Y, Entrée.
# Sécuriser le fichier (lecture seule pour le user)
sudo chown www-data:www-data /var/www/novabot/.env
sudo chmod 600 /var/www/novabot/.env
```

## 4. Création du Service Systemd (`novabot`)

Nous allons créer un service qui lance Streamlit automatiquement au démarrage.

Créez le fichier `/etc/systemd/system/novabot.service` :

```bash
sudo nano /etc/systemd/system/novabot.service
```

Collez-y ceci :

```ini
[Unit]
Description=NovaBot Trading Engine (Streamlit)
After=network.target

[Service]
# Utilisateur (www-data pour /var/www est recommandé)
User=www-data
WorkingDirectory=/var/www/novabot
Environment="PATH=/var/www/novabot/venv/bin"

# Commande de lancement (Streamlit)
ExecStart=/var/www/novabot/venv/bin/streamlit run main.py --server.port 8501 --server.headless true --server.address 0.0.0.0

# Redémarrage automatique en cas de crash
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

## 5. Démarrage et Vérification

```bash
# Recharger systemd
sudo systemctl daemon-reload

# Activer au démarrage
sudo systemctl enable novabot

# Démarrer maintenant
sudo systemctl start novabot

# Vérifier le statut
sudo systemctl status novabot
```

## 🔍 Accès et Debug

*   **Interface Web :** `http://<IP_DU_CONTAINER>:8501`
*   **Logs en direct :**
    ```bash
    sudo journalctl -u novabot -f
    ```
