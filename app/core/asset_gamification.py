"""
Asset Gamification Module - REFACTORED

Système de niveaux et tiers d'actifs pour guider les traders selon leur capital.
Optimisé pour Hyperliquid avec gestion des préfixes (k-assets) et liste mise à jour.

Niveaux:
- Goblin ($0-100): Débutant, capital limité
- Mercenary ($100-500): Intermédiaire, capital modéré  
- Whale ($500+): Avancé, capital important

Tiers d'Actifs:
- Casino: Memecoins volatils (PEPE, DOGE, HYPE, TRUMP, etc.)
- Growth Engines: Altcoins établis (SOL, AVAX, NEAR, SUI, ARB)
- Kings: Blue chips (BTC, ETH)
"""
import os
from typing import Dict, List, Tuple, Set
from enum import Enum

class AccountLevel(Enum):
    """Niveaux de compte basés sur le capital"""
    GOBLIN = "Goblin"  # $0-100
    MERCENARY = "Mercenary"  # $100-500
    WHALE = "Whale"  # $500+

class AssetTier(Enum):
    """Tiers d'actifs par risque/volatilité"""
    CASINO = "Casino"  # Memecoins
    GROWTH = "Growth Engines"  # Altcoins
    KINGS = "Kings"  # BTC/ETH

# Définition des actifs par tier (MISE À JOUR 2026)
ASSET_TIERS = {
    AssetTier.CASINO: [
        # Memecoins classiques
        "PEPE", "DOGE", "SHIB", "WIF", "BONK", "FLOKI",
        # Nouveaux memecoins Hyperliquid (2024-2026)
        "HYPE", "TRUMP", "MELANIA", "FARTCOIN", "MAGA",
        "VINE", "GOAT", "MOODENG", "SPX", "POPCAT", 
        "PURR", "KHEOWZOO", "PENGU", "PEOPLE", "BRETT",
        "PNUT", "CHILLGUY", "NEIRO", "MEW", "YZY",
        "BOME", "TST", "AIXBT", "MEME", "PEPE2",
        "WOJAK", "TURBO",
        # Variantes avec préfixe k (Hyperliquid)
        "kPEPE", "kBONK", "kSHIB", "kWIF", "kFLOKI", "kDOGE",
        "kTRUMP", "kMELANIA", "kBRETT", "kPNUT", "kGOAT"
    ],
    AssetTier.GROWTH: [
        "SOL", "AVAX", "NEAR", "SUI", "ARB", "OP", "MATIC",
        "ATOM", "DOT", "LINK", "UNI", "AAVE", "FTM", "INJ",
        "HYPE", "VRID", "AIXBT", "BNB", "ADA", "XRP",
        "ALGO", "SAND", "MANA", "APT", "SEI"
    ],
    AssetTier.KINGS: [
        "BTC", "ETH", "SOL"
    ]
}

# Règles d'accès par niveau
ACCESS_RULES: Dict[AccountLevel, Dict[str, any]] = {
    AccountLevel.GOBLIN: {
        "allowed_tiers": [AssetTier.CASINO],
        "max_leverage": 3,
        "max_position_size_usdc": 50,
        "description": "Niveau Goblin: Focus sur les memecoins pour maximiser les gains avec un petit capital",
        "recommendation": "Tradez des memecoins volatils avec un leverage modéré (max 3x)"
    },
    AccountLevel.MERCENARY: {
        "allowed_tiers": [AssetTier.CASINO, AssetTier.GROWTH],
        "max_leverage": 5,
        "max_position_size_usdc": 250,
        "description": "Niveau Mercenary: Accès aux altcoins établis pour diversifier",
        "recommendation": "Combinez memecoins et altcoins selon votre stratégie"
    },
    AccountLevel.WHALE: {
        "allowed_tiers": [AssetTier.CASINO, AssetTier.GROWTH, AssetTier.KINGS],
        "max_leverage": 10,
        "max_position_size_usdc": None,  # Pas de limite
        "description": "Niveau Whale: Accès complet à tous les actifs",
        "recommendation": "Tradez BTC/ETH pour la stabilité ou altcoins pour la croissance"
    }
}

# XP et progression
XP_THRESHOLDS = {
    AccountLevel.GOBLIN: 0,
    AccountLevel.MERCENARY: 100,  # $100 USDC
    AccountLevel.WHALE: 500  # $500 USDC
}

class AssetGamification:
    """Gestionnaire de gamification des actifs - REFACTORÉ"""
    
    def __init__(self, account_balance_usdc: float = 0):
        """Initialize gamification based on account value"""
        self.account_balance = account_balance_usdc
        self.level = self._calculate_level()
        
        # Cache pour éviter les recalculs
        self._all_known_assets_cache: Set[str] = None
    
    def _calculate_level(self) -> AccountLevel:
        """Calcule le niveau basé sur le capital"""
        if self.account_balance >= XP_THRESHOLDS[AccountLevel.WHALE]:
            return AccountLevel.WHALE
        elif self.account_balance >= XP_THRESHOLDS[AccountLevel.MERCENARY]:
            return AccountLevel.MERCENARY
        else:
            return AccountLevel.GOBLIN
    
    def _get_all_known_assets(self) -> Set[str]:
        """Retourne tous les assets connus (cache)"""
        if self._all_known_assets_cache is None:
            all_assets = []
            for tier_assets in ASSET_TIERS.values():
                all_assets.extend(tier_assets)
            self._all_known_assets_cache = set(all_assets)
        return self._all_known_assets_cache
    
    def _normalize_symbol(self, symbol: str) -> str:
        """
        Nettoie et normalise un symbole pour comparaison
        
        Gère:
        - Suffixes -USD, -USDC
        - Préfixe k (ex: kPEPE -> PEPE pour matching)
        - Casse (uppercase)
        
        Returns:
            Symbole normalisé (ex: "kPEPE-USD" -> "PEPE")
        """
        # Nettoyage de base
        s = symbol.upper().replace("-USD", "").replace("-USDC", "").strip()
        
        # Gestion du préfixe k (Hyperliquid memecoins)
        # Si c'est un k-asset ET que la version sans k existe dans nos tiers
        if s.startswith("K") and len(s) > 2:
            base_symbol = s[1:]  # Retire le 'k'
            if base_symbol in self._get_all_known_assets():
                return base_symbol
        
        return s
    
    def update_balance(self, new_balance: float):
        """Met à jour le solde et recalcule le niveau"""
        self.account_balance = new_balance
        old_level = self.level
        self.level = self._calculate_level()
        
        # Retourne True si level up
        return self.level != old_level
    
    def get_allowed_assets(self) -> List[str]:
        """
        Retourne la liste des actifs autorisés pour le niveau actuel
        
        IMPORTANT: Retourne TOUTES les variantes (avec et sans k)
        pour assurer la compatibilité avec l'API Hyperliquid
        """
        allowed_tiers = ACCESS_RULES[self.level]["allowed_tiers"]
        assets = []
        for tier in allowed_tiers:
            assets.extend(ASSET_TIERS[tier])
        
        # Déduplique (au cas où un asset serait dans plusieurs tiers)
        return list(set(assets))
    
    def is_asset_allowed(self, symbol: str) -> Tuple[bool, str]:
        """
        Vérifie si un actif est autorisé pour le niveau actuel
        
        Args:
            symbol: Symbole brut (peut contenir k-prefix, -USD, etc.)
        
        Returns:
            (bool, str): (autorisé, raison si refusé)
        """
        # Normaliser le symbole
        normalized = self._normalize_symbol(symbol)
        
        allowed_assets = self.get_allowed_assets()
        
        # Vérifier avec le symbole normalisé
        # ET avec le symbole original (pour les k-assets explicites)
        clean_original = symbol.upper().replace("-USD", "").replace("-USDC", "").strip()
        
        if normalized in allowed_assets or clean_original in allowed_assets:
            return True, ""
        
        # Trouver le tier de l'actif pour message personnalisé
        asset_tier = None
        for tier, assets in ASSET_TIERS.items():
            if normalized in assets or clean_original in assets:
                asset_tier = tier
                break
        
        if asset_tier is None:
            return False, f"Actif {symbol} non reconnu dans la gamification"
        
        # Message personnalisé selon le tier
        if asset_tier == AssetTier.KINGS:
            required_level = AccountLevel.WHALE
            return False, f"🔒 {symbol} réservé aux Whales ($500+). Niveau actuel: {self.level.value} (${self.account_balance:.2f})"
        elif asset_tier == AssetTier.GROWTH:
            required_level = AccountLevel.MERCENARY
            return False, f"🔒 {symbol} réservé aux Mercenaries ($100+). Niveau actuel: {self.level.value} (${self.account_balance:.2f})"
        
        return False, f"Actif {symbol} non autorisé"
    
    def get_asset_tier(self, symbol: str) -> AssetTier:
        """Retourne le tier d'un actif"""
        normalized = self._normalize_symbol(symbol)
        
        for tier, assets in ASSET_TIERS.items():
            if normalized in assets:
                return tier
        
        return None
    
    def get_max_leverage(self) -> int:
        """Retourne le leverage maximum pour le niveau actuel"""
        return ACCESS_RULES[self.level]["max_leverage"]
    
    def get_max_position_size(self) -> float:
        """Retourne la taille de position max en USDC"""
        return ACCESS_RULES[self.level]["max_position_size_usdc"]
    
    def get_progress_to_next_level(self) -> Dict:
        """Retourne la progression vers le niveau suivant"""
        if self.level == AccountLevel.WHALE:
            return {
                "current_level": self.level.value,
                "next_level": None,
                "current_balance": self.account_balance,
                "required_balance": None,
                "progress_percent": 100,
                "remaining": 0
            }
        
        next_level = AccountLevel.MERCENARY if self.level == AccountLevel.GOBLIN else AccountLevel.WHALE
        required = XP_THRESHOLDS[next_level]
        current = self.account_balance
        
        if self.level == AccountLevel.GOBLIN:
            start = 0
        else:
            start = XP_THRESHOLDS[AccountLevel.MERCENARY]
        
        progress = ((current - start) / (required - start)) * 100
        remaining = required - current
        
        return {
            "current_level": self.level.value,
            "next_level": next_level.value,
            "current_balance": current,
            "required_balance": required,
            "progress_percent": min(100, max(0, progress)),
            "remaining": max(0, remaining)
        }
    
    def get_recommendations(self) -> List[str]:
        """Retourne des recommandations d'actifs pour le niveau actuel"""
        tier_recommendations = {
            AccountLevel.GOBLIN: [
                "PEPE - Memecoin populaire avec forte volatilité",
                "DOGE - Classique des memecoins",
                "HYPE - Token natif Hyperliquid, très liquide",
                "TRUMP - Memecoin politique tendance",
                "WIF - Nouveau memecoin tendance"
            ],
            AccountLevel.MERCENARY: [
                "SOL - Blockchain rapide, bon potentiel",
                "AVAX - Concurrent d'Ethereum",
                "HYPE - Token Hyperliquid avec forte liquidité",
                "SUI - Nouveau L1 prometteur",
                "PEPE - Toujours accessible pour du scalping"
            ],
            AccountLevel.WHALE: [
                "BTC - Roi des cryptos, moins volatil",
                "ETH - Leader des smart contracts",
                "SOL - Pour de la croissance",
                "Tous les actifs disponibles selon votre stratégie"
            ]
        }
        
        return tier_recommendations[self.level]
    
    def get_status_summary(self) -> Dict:
        """Retourne un résumé complet du statut gamification"""
        progress = self.get_progress_to_next_level()
        
        return {
            "level": self.level.value,
            "balance": self.account_balance,
            "allowed_tiers": [tier.value for tier in ACCESS_RULES[self.level]["allowed_tiers"]],
            "allowed_assets_count": len(self.get_allowed_assets()),
            "max_leverage": self.get_max_leverage(),
            "max_position_size": self.get_max_position_size(),
            "description": ACCESS_RULES[self.level]["description"],
            "recommendation": ACCESS_RULES[self.level]["recommendation"],
            "progress": progress,
            "recommendations": self.get_recommendations()
        }
    
    def debug_whitelist(self) -> str:
        """
        🔍 DEBUG: Affiche les informations de whitelist pour diagnostic
        
        Utile pour comprendre pourquoi le scanner ne trouve que certains tokens
        """
        allowed = self.get_allowed_assets()
        
        debug_info = f"""
╔══════════════════════════════════════════════════════════════╗
║              🎮 GAMIFICATION DEBUG WHITELIST                 ║
╠══════════════════════════════════════════════════════════════╣
║ Niveau Actuel    : {self.level.value:<40} ║
║ Capital Détecté  : ${self.account_balance:<38.2f} ║
║ Tiers Autorisés  : {', '.join([t.value for t in ACCESS_RULES[self.level]['allowed_tiers']]):<38} ║
║ Nombre d'Assets  : {len(allowed):<40} ║
╠══════════════════════════════════════════════════════════════╣
║ 🎯 PREMIERS 10 ASSETS AUTORISÉS:                            ║
╠══════════════════════════════════════════════════════════════╣
"""
        for i, asset in enumerate(allowed[:10], 1):
            debug_info += f"║ {i:2d}. {asset:<55} ║\n"
        
        if len(allowed) > 10:
            debug_info += f"║ ... et {len(allowed) - 10} autres                                      ║\n"
        
        debug_info += "╚══════════════════════════════════════════════════════════════╝"
        
        return debug_info

# Fonction helper pour utilisation facile
def check_asset_access(symbol: str, account_balance: float) -> Tuple[bool, str, Dict]:
    """
    Vérifie l'accès à un actif et retourne des infos
    
    Returns:
        (allowed, message, gamification_status)
    """
    gam = AssetGamification(account_balance)
    allowed, reason = gam.is_asset_allowed(symbol)
    status = gam.get_status_summary()
    
    return allowed, reason, status
