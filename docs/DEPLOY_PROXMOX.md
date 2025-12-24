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

## 2. Installation de NovaBot

Nous allons installer le bot dans `/opt/novabot`.

```bash
# Installer Git et Python venv (si nécessaire)
sudo apt update && sudo apt install -y git python3-venv python3-pip

# Cloner le dépôt (ou git pull si déjà présent)
sudo git clone https://github.com/nico2511/NovaBot.git /opt/novabot
# Si le dossier existe déjà : cd /opt/novabot && sudo git pull

# Configurer les permissions (remplacer 'root' par votre user si besoin)
sudo chown -R root:root /opt/novabot
cd /opt/novabot

# Créer l'environnement virtuel
python3 -m venv venv

# Installer les dépendances
./venv/bin/pip install -r requirements.txt
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
nano /opt/novabot/.env
# Collez le contenu, puis Ctrl+X, Y, Entrée.
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
# Utilisateur qui lance le bot (root ou votre user)
User=root
WorkingDirectory=/opt/novabot
Environment="PATH=/opt/novabot/venv/bin"

# Commande de lancement (Streamlit)
# Port 8501 par défaut
ExecStart=/opt/novabot/venv/bin/streamlit run main.py --server.port 8501 --server.headless true --server.address 0.0.0.0

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
