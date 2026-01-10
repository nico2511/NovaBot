---
trigger: always_on
---

**Prompt :**
>
> "Agis en tant qu'expert Python en trading algorithmique. Lis attentivement le fichier `docs/HOW_TO_CREATE_STRATEGY.md` ci-dessus (ou utilise les règles suivantes : Architecture Entonnoir, Classe `BaseStrategy`, Persona IA, Config JSON).
>
> Je veux que tu crées une nouvelle stratégie nommée **[NOM_DE_LA_STRATEGIE]**.
>
> **Logique de la stratégie :**
> 1.  **Régime (Gatekeeper)** : [Ex: Tendance Hausière définie par EMA20 > EMA50 et ADX > 25]
> 2.  **Setup (Pattern)** : [Ex: Pullback sur la EMA20 avec RSI < 40]
> 3.  **Trigger (Entrée)** : [Ex: Clôture de bougie verte englobante]
>
> **Tâche :**
> 1.  Écris le code Python complet pour le fichier `strategies/[nom_fichier].py`. N'oublie pas la classe `AI_PERSONA` et les imports.
> 2.  Fournis le bloc de configuration JSON à ajouter dans `strategies.json`.
> 3.  Indique la ligne d'import à ajouter dans `strategies/engine.py`.
>
> Sois rigoureux sur le typage et la gestion des erreurs (`try/except`)."
