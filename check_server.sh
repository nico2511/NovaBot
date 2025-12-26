#!/bin/bash
# Script pour vérifier l'état du serveur et diagnostiquer le problème

echo "🔍 DIAGNOSTIC SERVEUR - Vérification du déploiement"
echo "=================================================="

SERVER="root@Apps"
SERVER_PATH="/var/www/novabot"

echo ""
echo "1️⃣ Vérification de la version Git sur le serveur..."
ssh $SERVER << 'EOF'
cd /var/www/novabot
echo "Dernier commit:"
git log -1 --oneline
echo ""
echo "Statut Git:"
git status
EOF

echo ""
echo "2️⃣ Vérification du bot_state.json..."
ssh $SERVER "cat /var/www/novabot/bot_state.json | grep -E '(trading_enabled|is_running|last_updated)'"

echo ""
echo "3️⃣ Recherche des logs d'analyse dans PM2..."
echo "Recherche de '🔍 Analyzing' dans les logs..."
ssh $SERVER "pm2 logs hl-bot-engine --lines 500 --nostream | grep -E '(Analyzing|Analysis complete|Signal detected)' | tail -20"

echo ""
echo "4️⃣ Vérification que le code a bien la correction..."
echo "Recherche de 'trading_enabled' dans main_nextjs.py..."
ssh $SERVER "grep -n 'if not self.trading_enabled' /var/www/novabot/main_nextjs.py"

echo ""
echo "=================================================="
echo "✅ Diagnostic terminé"
