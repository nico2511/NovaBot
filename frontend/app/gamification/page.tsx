'use client'

import { useEffect, useState } from 'react'
import Link from 'next/link'
import { Trophy, TrendingUp, Shield, Zap, Lock, ChevronRight, ArrowLeft } from 'lucide-react'

interface GamificationStatus {
    level: string
    balance: number
    allowed_tiers: string[]
    max_leverage: number
    max_position_size: number | null
    progress: {
        current_level: string
        next_level: string | null
        progress_percent: number
        remaining: number
    }
}

export default function GamificationPage() {
    const [gamStatus, setGamStatus] = useState<GamificationStatus | null>(null)

    useEffect(() => {
        fetchGamificationStatus()
    }, [])

    const fetchGamificationStatus = async () => {
        try {
            const res = await fetch('/api/gamification_status')
            const data = await res.json()
            if (data.status === 'success') {
                setGamStatus(data.gamification)
            }
        } catch (error) {
            console.error('Error fetching gamification:', error)
        }
    }

    const getLevelEmoji = (level: string) => {
        switch (level) {
            case 'Goblin': return '👺'
            case 'Mercenary': return '⚔️'
            case 'Whale': return '🐋'
            default: return '🎮'
        }
    }

    const getLevelColor = (level: string) => {
        switch (level) {
            case 'Goblin': return 'from-red-500 to-orange-500'
            case 'Mercenary': return 'from-blue-500 to-cyan-500'
            case 'Whale': return 'from-purple-500 to-pink-500'
            default: return 'from-gray-500 to-gray-600'
        }
    }

    return (
        <div className="min-h-screen bg-background text-white p-6">
            <div className="max-w-6xl mx-auto space-y-8">
                {/* Header */}
                <div className="flex items-center justify-between">
                    <div>
                        <h1 className="text-4xl font-bold bg-gradient-to-r from-purple-400 to-pink-400 bg-clip-text text-transparent">
                            🎮 Système de Gamification
                        </h1>
                        <p className="text-gray-400 mt-2">Progression basée sur votre capital</p>
                    </div>
                    <Link href="/" className="flex items-center gap-2 px-4 py-2 bg-white/5 hover:bg-white/10 rounded-lg transition-colors border border-white/10">
                        <ArrowLeft className="w-4 h-4" />
                        Dashboard
                    </Link>
                </div>

                {/* Current Status */}
                {gamStatus && (
                    <div className={`bg-gradient-to-br ${getLevelColor(gamStatus.level)} p-1 rounded-2xl`}>
                        <div className="bg-background rounded-xl p-6">
                            {/* Important Notice */}
                            <div className="mb-6 p-4 bg-blue-500/10 border border-blue-500/30 rounded-lg">
                                <div className="flex items-start gap-3">
                                    <Shield className="w-5 h-5 text-blue-400 mt-0.5" />
                                    <div className="flex-1">
                                        <h3 className="font-semibold text-blue-300 mb-1">La gamification guide, ne bloque pas!</h3>
                                        <p className="text-sm text-gray-300">
                                            ✅ <strong>Trades MANUELS</strong>: Vous pouvez trader <strong>n'importe quel actif</strong> manuellement (BTC, ETH, etc.)
                                            <br />
                                            ⚙️ <strong>Automatismes</strong>: Les restrictions ci-dessous s'appliquent uniquement aux <strong>signaux automatiques</strong>
                                        </p>
                                    </div>
                                </div>
                            </div>

                            <div className="flex items-center justify-between mb-4">
                                <div className="flex items-center gap-4">
                                    <span className="text-6xl">{getLevelEmoji(gamStatus.level)}</span>
                                    <div>
                                        <h2 className="text-3xl font-bold">{gamStatus.level}</h2>
                                        <p className="text-gray-400">Balance: ${gamStatus.balance.toFixed(2)} USDC</p>
                                    </div>
                                </div>
                                <div className="text-right">
                                    <div className="text-sm text-gray-400">Leverage Max</div>
                                    <div className="text-2xl font-bold">{gamStatus.max_leverage}x</div>
                                </div>
                            </div>

                            {gamStatus.progress.next_level && (
                                <div className="mt-6">
                                    <div className="flex items-center justify-between text-sm mb-2">
                                        <span className="text-gray-400">Progression vers {gamStatus.progress.next_level}</span>
                                        <span className="font-bold">{gamStatus.progress.progress_percent.toFixed(0)}%</span>
                                    </div>
                                    <div className="w-full bg-gray-700 rounded-full h-3">
                                        <div
                                            className={`bg-gradient-to-r ${getLevelColor(gamStatus.progress.next_level)} h-full rounded-full transition-all`}
                                            style={{ width: `${gamStatus.progress.progress_percent}%` }}
                                        />
                                    </div>
                                    <p className="text-xs text-gray-500 mt-2">
                                        ${gamStatus.progress.remaining.toFixed(2)} restants
                                    </p>
                                </div>
                            )}
                        </div>
                    </div>
                )}

                {/* Levels Overview */}
                <div className="grid md:grid-cols-3 gap-6">
                    {/* Goblin */}
                    <div className="bg-gradient-to-br from-red-900/20 to-orange-900/20 rounded-xl p-6 border border-red-500/30">
                        <div className="flex items-center gap-3 mb-4">
                            <span className="text-4xl">👺</span>
                            <div>
                                <h3 className="text-xl font-bold">Goblin</h3>
                                <p className="text-sm text-gray-400">$0 - $100</p>
                            </div>
                        </div>

                        <div className="space-y-3 text-sm">
                            <div className="flex items-center gap-2">
                                <Zap className="w-4 h-4 text-yellow-400" />
                                <span>Leverage: <strong>3x max</strong></span>
                            </div>
                            <div className="flex items-center gap-2">
                                <Shield className="w-4 h-4 text-blue-400" />
                                <span>Position: <strong>$50 max</strong></span>
                            </div>
                            <div className="flex items-center gap-2">
                                <Trophy className="w-4 h-4 text-orange-400" />
                                <span>Tier: <strong>Casino</strong> (10 tokens)</span>
                            </div>
                        </div>

                        <div className="mt-4 p-3 bg-black/30 rounded-lg">
                            <p className="text-xs text-gray-300">
                                Focus sur les memecoins volatils pour maximiser les gains avec un petit capital
                            </p>
                        </div>

                        <div className="mt-4 space-y-1">
                            <p className="text-xs text-gray-400 font-semibold">Actifs disponibles:</p>
                            <div className="flex flex-wrap gap-1">
                                {['PEPE', 'DOGE', 'WIF', 'BONK'].map(token => (
                                    <span key={token} className="px-2 py-0.5 bg-red-500/20 text-red-300 rounded text-xs">
                                        {token}
                                    </span>
                                ))}
                                <span className="text-xs text-gray-500">+6 autres</span>
                            </div>
                        </div>
                    </div>

                    {/* Mercenary */}
                    <div className="bg-gradient-to-br from-blue-900/20 to-cyan-900/20 rounded-xl p-6 border border-blue-500/30">
                        <div className="flex items-center gap-3 mb-4">
                            <span className="text-4xl">⚔️</span>
                            <div>
                                <h3 className="text-xl font-bold">Mercenary</h3>
                                <p className="text-sm text-gray-400">$100 - $500</p>
                            </div>
                        </div>

                        <div className="space-y-3 text-sm">
                            <div className="flex items-center gap-2">
                                <Zap className="w-4 h-4 text-yellow-400" />
                                <span>Leverage: <strong>5x max</strong></span>
                            </div>
                            <div className="flex items-center gap-2">
                                <Shield className="w-4 h-4 text-blue-400" />
                                <span>Position: <strong>$250 max</strong></span>
                            </div>
                            <div className="flex items-center gap-2">
                                <Trophy className="w-4 h-4 text-cyan-400" />
                                <span>Tiers: <strong>Casino + Growth</strong> (24 tokens)</span>
                            </div>
                        </div>

                        <div className="mt-4 p-3 bg-black/30 rounded-lg">
                            <p className="text-xs text-gray-300">
                                Diversifiez entre memecoins (scalp) et altcoins établis (swing)
                            </p>
                        </div>

                        <div className="mt-4 space-y-1">
                            <p className="text-xs text-gray-400 font-semibold">Nouveaux actifs:</p>
                            <div className="flex flex-wrap gap-1">
                                {['SOL', 'AVAX', 'NEAR', 'ARB'].map(token => (
                                    <span key={token} className="px-2 py-0.5 bg-blue-500/20 text-blue-300 rounded text-xs">
                                        {token}
                                    </span>
                                ))}
                                <span className="text-xs text-gray-500">+10 autres</span>
                            </div>
                        </div>
                    </div>

                    {/* Whale */}
                    <div className="bg-gradient-to-br from-purple-900/20 to-pink-900/20 rounded-xl p-6 border border-purple-500/30">
                        <div className="flex items-center gap-3 mb-4">
                            <span className="text-4xl">🐋</span>
                            <div>
                                <h3 className="text-xl font-bold">Whale</h3>
                                <p className="text-sm text-gray-400">$500+</p>
                            </div>
                        </div>

                        <div className="space-y-3 text-sm">
                            <div className="flex items-center gap-2">
                                <Zap className="w-4 h-4 text-yellow-400" />
                                <span>Leverage: <strong>10x max</strong></span>
                            </div>
                            <div className="flex items-center gap-2">
                                <Shield className="w-4 h-4 text-blue-400" />
                                <span>Position: <strong>Illimitée</strong></span>
                            </div>
                            <div className="flex items-center gap-2">
                                <Trophy className="w-4 h-4 text-purple-400" />
                                <span>Tiers: <strong>Tous</strong> (26 tokens)</span>
                            </div>
                        </div>

                        <div className="mt-4 p-3 bg-black/30 rounded-lg">
                            <p className="text-xs text-gray-300">
                                Accès complet: BTC/ETH pour stabilité, altcoins pour croissance
                            </p>
                        </div>

                        <div className="mt-4 space-y-1">
                            <p className="text-xs text-gray-400 font-semibold">Accès exclusif:</p>
                            <div className="flex flex-wrap gap-1">
                                {['BTC', 'ETH'].map(token => (
                                    <span key={token} className="px-2 py-0.5 bg-purple-500/20 text-purple-300 rounded text-xs font-bold">
                                        👑 {token}
                                    </span>
                                ))}
                            </div>
                        </div>
                    </div>
                </div>

                {/* Asset Tiers */}
                <div className="bg-surface/50 rounded-xl p-6 border border-border/30">
                    <h2 className="text-2xl font-bold mb-6">📊 Tiers d'Actifs</h2>

                    <div className="grid md:grid-cols-3 gap-6">
                        <div>
                            <div className="flex items-center gap-2 mb-3">
                                <span className="text-2xl">🎰</span>
                                <h3 className="font-bold text-lg">Casino</h3>
                            </div>
                            <p className="text-sm text-gray-400 mb-3">Memecoins volatils - Risque très élevé</p>
                            <div className="space-y-1">
                                <div className="flex items-center gap-2 text-xs">
                                    <TrendingUp className="w-3 h-3 text-red-400" />
                                    <span>Volatilité: ±20-50% / jour</span>
                                </div>
                                <div className="flex items-center gap-2 text-xs">
                                    <Zap className="w-3 h-3 text-yellow-400" />
                                    <span>Stratégie: Scalp rapide</span>
                                </div>
                            </div>
                        </div>

                        <div>
                            <div className="flex items-center gap-2 mb-3">
                                <span className="text-2xl">🌱</span>
                                <h3 className="font-bold text-lg">Growth Engines</h3>
                            </div>
                            <p className="text-sm text-gray-400 mb-3">Altcoins établis - Risque modéré</p>
                            <div className="space-y-1">
                                <div className="flex items-center gap-2 text-xs">
                                    <TrendingUp className="w-3 h-3 text-orange-400" />
                                    <span>Volatilité: ±10-20% / jour</span>
                                </div>
                                <div className="flex items-center gap-2 text-xs">
                                    <Zap className="w-3 h-3 text-yellow-400" />
                                    <span>Stratégie: Swing trading</span>
                                </div>
                            </div>
                        </div>

                        <div>
                            <div className="flex items-center gap-2 mb-3">
                                <span className="text-2xl">👑</span>
                                <h3 className="font-bold text-lg">Kings</h3>
                            </div>
                            <p className="text-sm text-gray-400 mb-3">Blue chips - Risque faible</p>
                            <div className="space-y-1">
                                <div className="flex items-center gap-2 text-xs">
                                    <TrendingUp className="w-3 h-3 text-green-400" />
                                    <span>Volatilité: ±5-10% / jour</span>
                                </div>
                                <div className="flex items-center gap-2 text-xs">
                                    <Zap className="w-3 h-3 text-yellow-400" />
                                    <span>Stratégie: Position trading</span>
                                </div>
                                <div className="flex items-center gap-2 text-xs">
                                    <Lock className="w-3 h-3 text-purple-400" />
                                    <span className="text-purple-400">Whale uniquement</span>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>

                {/* FAQ */}
                <div className="bg-surface/50 rounded-xl p-6 border border-border/30">
                    <h2 className="text-2xl font-bold mb-6">❓ Questions Fréquentes</h2>

                    <div className="space-y-4">
                        <div>
                            <h3 className="font-semibold mb-2">Pourquoi je suis "Goblin" avec $0?</h3>
                            <p className="text-sm text-gray-400">
                                C'est normal! Goblin est le <strong>premier palier</strong> ($0-100). Il n'y a pas de "niveau zéro".
                                Tout le monde commence Goblin.
                            </p>
                        </div>

                        <div>
                            <h3 className="font-semibold mb-2">Comment monter de niveau?</h3>
                            <p className="text-sm text-gray-400">
                                Votre niveau se met à jour automatiquement selon votre balance:
                                <br />• Goblin → Mercenary: Atteindre $100 USDC
                                <br />• Mercenary → Whale: Atteindre $500 USDC
                            </p>
                        </div>

                        <div>
                            <h3 className="font-semibold mb-2">Puis-je trader BTC en tant que Goblin?</h3>
                            <p className="text-sm text-gray-400">
                                Non, BTC est réservé aux Whales ($500+). Tradez des memecoins pour faire croître votre capital rapidement.
                            </p>
                        </div>

                        <div>
                            <h3 className="font-semibold mb-2">Que se passe-t-il si je perds de l'argent?</h3>
                            <p className="text-sm text-gray-400">
                                Si votre balance descend sous le seuil, vous redescendez de niveau.
                                Ex: Mercenary avec $90 → redevient Goblin.
                            </p>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    )
}
