# ⚠️ SÉCURITÉ: TOKEN GITHUB EXPOSÉ

## 🚨 ACTION IMMÉDIATE REQUISE

Votre token GitHub `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` a été partagé publiquement.

### 1. RÉVOQUER LE TOKEN MAINTENANT

```
1. Aller sur: https://github.com/settings/tokens
2. Trouver le token: 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
3. Cliquer sur "Delete" ou "Revoke"
```

### 2. Créer un nouveau token (après déploiement)

```
1. GitHub → Settings → Developer settings → Personal access tokens → Tokens (classic)
2. Generate new token
3. Sélectionner scope: "repo" (accès complet au repo)
4. Copier le nouveau token
5. NE JAMAIS le partager publiquement
```

---

## 📦 Déploiement sur le Serveur

### Option 1: Avec le token actuel (RAPIDE - puis révoquer)

```bash
# Sur le serveur
cd /tmp
wget https://raw.githubusercontent.com/nico2511/NovaBot/master/deploy_with_token.sh
chmod +x deploy_with_token.sh
./deploy_with_token.sh
```

**PUIS IMMÉDIATEMENT:** Révoquer le token sur GitHub!

---

### Option 2: Sans token (RECOMMANDÉ - plus sûr)

```bash
# Sur le serveur
cd /var/www/novabot
git pull  # Entrer username + token quand demandé
./deploy_rebuild.sh
```

---

### Option 3: Configurer SSH (MEILLEUR - une fois pour toutes)

```bash
# Sur le serveur
ssh-keygen -t ed25519 -C "votre@email.com"
cat ~/.ssh/id_ed25519.pub

# Copier la clé publique
# Aller sur GitHub → Settings → SSH keys → Add SSH key
# Coller la clé

# Tester
ssh -T git@github.com

# Changer remote en SSH
cd /var/www/novabot
git remote set-url origin git@github.com:nico2511/NovaBot.git

# Maintenant git pull fonctionne sans mot de passe!
```

---

## 🔒 Bonnes Pratiques de Sécurité

### ❌ NE JAMAIS FAIRE:
- Partager un token dans un chat/email
- Commiter un token dans le code
- Utiliser le même token partout
- Garder un token exposé actif

### ✅ TOUJOURS FAIRE:
- Utiliser SSH keys pour les serveurs
- Créer des tokens avec permissions minimales
- Révoquer immédiatement si exposé
- Utiliser des variables d'environnement
- Rotation régulière des tokens

---

## 📝 Checklist Post-Déploiement

```
[ ] Déploiement réussi
[ ] Token GitHub révoqué
[ ] SSH keys configurées (optionnel mais recommandé)
[ ] Services PM2 en ligne
[ ] Frontend accessible
[ ] API fonctionnelle
```

---

## 🆘 Si le Token est Déjà Révoqué

Utilisez `deploy_rebuild.sh` qui ne nécessite pas de re-cloner:

```bash
cd /var/www/novabot
git pull  # Entrer credentials manuellement
./deploy_rebuild.sh
```

---

**RAPPEL:** Révoquez `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` dès que possible! 🔐
