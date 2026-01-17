# 🧠 Personas et Profils de Risque NovaBot

Ce document explique le fonctionnement du système de "Personnalité" et de "Gestion de Risque" de l'IA NovaBot. Ces paramètres influencent directement la prise de décision de l'IA lors de la validation des signaux.

---

## 🎭 1. Personas du Bot (Bot Persona)

Le **Bot Persona** définit le "style psychologique" de l'IA. C'est la lentille à travers laquelle l'IA analyse le marché.

### Pourquoi ces profils ?
Chaque trader a un style différent. Le Persona permet d'aligner l'IA avec VOTRE style de trading, ou de la forcer à adopter une discipline spécifique.

### Les Profils Disponibles

| Persona | Description | Comportement IA |
|:---|:---|:---|
| **Conservative Scalper** (Défaut) | Prudence avant tout. | - Cherche 3+ indicateurs confirmants<br>- Rejette les signaux en zone incertaine<br>- Vise des petits gains rapides (Hit & Run)<br>- **Idéal pour :** Marchés calmes ou préservation de capital. |
| **Aggressive Day Trader** | Chasseur de momentum. | - Accepte plus de risques si le trend est fort<br>- Joue les breakouts<br>- Stop-loss plus larges pour laisser respirer le trade<br>- **Idéal pour :** Marchés volatils et tendances fortes. |
| **Sniper** | La perfection ou rien. | - Rejette 90% des signaux<br>- Attend des setups textbook (S/R majeurs, Fibonacci)<br>- Fréquence de trade très faible mais taux de succès visé élevé.<br>- **Idéal pour :** Éviter l'overtrading. |

---

## 🛡️ 2. Profils de Risque (Risk Profile)

Le **Risk Profile** définit les limites strictes de gestion du capital (Money Management).

### Pourquoi ces profils ?
Pour empêcher l'IA (ou l'humain) de prendre des décisions émotionnelles concernant la taille de position ou le levier.

### Les Profils Disponibles

| Profil | Règles de Gestion | Détails |
|:---|:---|:---|
| **Capital Preservation First** (Défaut) | Survie > Profit. | - Risque max : 1-2% par trade<br>- Levier Max : 3x<br>- R:R Minimum : 2:1<br>- Stop Loss **OBLIGATOIRE** |
| **Balanced Growth** | Équilibre classique. | - Risque max : 2-5% par trade<br>- Levier Max : 5x<br>- R:R Minimum : 1.5:1<br>- Accepte un peu de drawdown pour suivre le trend |
| **High Volatility Hunter** | Risque élevé, récompense élevée. | - Risque max : 5-10% par trade<br>- Levier Max : 10x<br>- R:R Minimum : 1:1 (si conviction forte)<br>- **Attention :** Risque de drawdown important. |

---

## ⚙️ 3. Comment les mettre en place ?

### Via l'Interface (Futur)
Un menu "Settings" dans le Frontend permettra de sélectionner ces profils via les menus déroulants connectés à l'API `/api/settings/global`.

### Via Configuration (`bot_state.json` / API)
Actuellement, ces paramètres sont accessibles via l'API ou éditables dans le fichier d'état.

**Exemple de Payload API (`POST /api/settings/global`) :**

```json
{
  "bot_persona": "Aggressive Day Trader",
  "risk_profile": "Balanced Growth",
  "max_positions": 3,
  "daily_stop_loss": 100.0,
  "trading_timeframe": "5m",
  "ai_conf_threshold": 60
}
```

### Impact Immédiat
Dès que vous changez le profil :
1. L'IA recharge son **System Prompt**.
2. La prochaine analyse de signal utilisera les nouvelles règles.
3. Les trades en cours **gardent** leur gestion initiale (pas de changement rétroactif).

---

## 🧩 4. Stratégies vs Personas

Attention à ne pas confondre **Stratégie** (L'algo mathématique) et **Persona** (L'analyseur IA).

*   **Stratégie** : "Le RSI croise 30, j'envoie un signal."
*   **Persona** : "Je vois le signal RSI, mais en tant que *Conservative Scalper*, je refuse car on est sous la résistance majeure daily."

> Le Persona est le **filtre final** avant l'exécution.
