'use client'

import { useEffect, useState } from 'react'
import axios from 'axios'
import Link from 'next/link'

interface GamificationData {
    level: string
    balance: number
    allowed_tiers: string[]
    max_leverage: number
    max_position_size: number | null
    description: string
    recommendation: string
    progress: {
        current_level: string
        next_level: string | null
        current_balance: number
        required_balance: number | null
        progress_percent: number
        remaining: number
    }
    recommendations: string[]
}

export default function GamificationWidget() {
    const [gamData, setGamData] = useState<GamificationData | null>(null)
    const [loading, setLoading] = useState(true)
    const [mounted, setMounted] = useState(false)

    useEffect(() => { setMounted(true) }, [])

    useEffect(() => {
        const fetchGamification = async () => {
            try {
                const response = await axios.get('/api/gamification_status')
                if (response.data.status === 'success') {
                    setGamData(response.data.gamification)
                }
            } catch (error) {
                console.error('Failed to fetch gamification:', error)
            } finally {
                setLoading(false)
            }
        }

        fetchGamification()
        const interval = setInterval(fetchGamification, 10000) // Update every 10s
        return () => clearInterval(interval)
    }, [])

    if (!mounted) return null;

    if (loading || !gamData) {
        return (
            <div className="bg-surface/50 backdrop-blur border border-border/30 rounded-2xl p-6 animate-pulse">
                <div className="h-6 bg-gray-700 rounded w-1/3 mb-4"></div>
                <div className="h-4 bg-gray-700 rounded w-2/3"></div>
            </div>
        )
    }

    const getLevelColor = (level: string) => {
        switch (level) {
            case 'Goblin': return 'text-green-400'
            case 'Mercenary': return 'text-blue-400'
            case 'Whale': return 'text-purple-400'
            default: return 'text-gray-400'
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

    // Compact version for header
    return (
        <div className="group relative">
            <Link href="/gamification" className="flex items-center gap-3 px-3 py-1.5 rounded-lg hover:bg-white/5 transition-colors cursor-pointer">
                <span className="text-2xl filter drop-shadow-md transition-transform group-hover:scale-110 duration-200">
                    {getLevelEmoji(gamData.level)}
                </span>
                <div className="min-w-0">
                    <div className="flex items-center gap-2">
                        <span className={`text-sm font-bold ${getLevelColor(gamData.level)}`}>
                            {gamData.level}
                        </span>
                        <span className="text-xs text-gray-500">
                            • {Array.isArray(gamData.allowed_tiers) ? gamData.allowed_tiers.length : 0} Tiers Unlocked
                        </span>
                    </div>

                    {gamData.progress.next_level ? (
                        <div className="flex flex-col gap-0.5 mt-0.5">
                            <div className="flex items-center gap-2 w-32">
                                <div className="flex-1 h-1.5 bg-gray-800 rounded-full overflow-hidden">
                                    <div
                                        className="h-full bg-gradient-to-r from-primary to-blue-400 shadow-[0_0_10px_rgba(59,130,246,0.5)]"
                                        style={{ width: `${gamData.progress.progress_percent}%` }}
                                    />
                                </div>
                            </div>
                            <span className="text-[10px] text-gray-400">
                                ${gamData.progress.remaining.toFixed(2)} to {gamData.progress.next_level}
                            </span>
                        </div>
                    ) : (
                        <div className="text-xs text-yellow-500 font-medium mt-0.5">
                            Max Level reached! 👑
                        </div>
                    )}
                </div>
            </Link>

            {/* Hover Tooltip (Updated to indicate Clickability) */}
            <div className="absolute top-full right-0 mt-2 w-64 p-4 bg-gray-900/95 backdrop-blur-xl border border-gray-700 rounded-xl shadow-2xl opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all duration-200 z-50 transform translate-y-2 group-hover:translate-y-0 pointer-events-none">
                <div className="flex items-center justify-between mb-3">
                    <h3 className={`font-bold text-lg ${getLevelColor(gamData.level)}`}>
                        {gamData.level} Rank
                    </h3>
                    <span className="text-2xl">{getLevelEmoji(gamData.level)}</span>
                </div>

                <p className="text-xs text-gray-300 mb-3 italic leading-relaxed">
                    "{gamData.description}"
                </p>

                <div className="space-y-3">
                    <div>
                        <div className="text-xs font-semibold text-gray-400 mb-1 uppercase tracking-wider">
                            Market Access
                        </div>
                        <div className="flex flex-wrap gap-1">
                            {(Array.isArray(gamData.allowed_tiers) ? gamData.allowed_tiers : []).map(tier => (
                                <span key={tier} className="px-2 py-0.5 text-[10px] bg-gray-800 border border-gray-700 rounded text-gray-300">
                                    {tier}
                                </span>
                            ))}
                        </div>
                    </div>

                    <div className="grid grid-cols-2 gap-2">
                        <div className="bg-gray-800/50 p-2 rounded-lg border border-gray-700/50">
                            <div className="text-[10px] text-gray-500">Max Leverage</div>
                            <div className="text-sm font-bold text-white">{gamData.max_leverage}x</div>
                        </div>
                        <div className="bg-gray-800/50 p-2 rounded-lg border border-gray-700/50">
                            <div className="text-[10px] text-gray-500">Max Size</div>
                            <div className="text-sm font-bold text-white">
                                {gamData.max_position_size ? `$${gamData.max_position_size}` : 'Unlimited'}
                            </div>
                        </div>
                    </div>

                    <div className="pt-2 border-t border-gray-800 text-center text-[10px] text-gray-400">
                        Click to view full journey ↗️
                    </div>
                </div>
            </div>
        </div>
    )
}
