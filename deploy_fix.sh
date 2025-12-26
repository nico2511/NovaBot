#!/bin/bash
# Script de déploiement rapide sur le serveur
# Usage: ./deploy_fix.sh

echo "🚀 Déploiement des corrections sur le serveur"
echo "=============================================="

# Variables (à adapter)
SERVER="root@Apps"
SERVER_PATH="/var/www/novabot"

echo ""
echo "📡 Connexion au serveur et pull des changements..."
ssh $SERVER << 'EOF'
cd /var/www/novabot
git pull origin master
echo "✅ Code mis à jour"

echo ""
echo "🔄 Redémarrage du bot..."
pm2 restart hl-bot-engine

echo ""
echo "📊 Vérification des logs (10 dernières lignes)..."
pm2 logs hl-bot-engine --lines 10 --nostream

echo ""
echo "✅ Déploiement terminé!"
echo ""
echo "📋 Prochaines étapes:"
echo "   1. Ouvrir http://votre-serveur:3000"
echo "   2. Activer le toggle 'Trading Enabled'"
echo "   3. Surveiller les logs: pm2 logs hl-bot-engine"
EOF

echo ""
echo "🎉 Déploiement terminé avec succès!"
