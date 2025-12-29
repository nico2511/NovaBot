'use client'

import { useEffect, useState } from 'react'
import axios from 'axios'

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
        <div className="flex items-center gap-3">
            <span className="text-2xl">{getLevelEmoji(gamData.level)}</span>
            <div className="min-w-0">
                <div className="flex items-center gap-2">
                    <span className={`text-sm font-bold ${getLevelColor(gamData.level)}`}>
                        {gamData.level}
                    </span>
                    <span className="text-xs text-gray-400">
                        {gamData.allowed_tiers.join(', ')}
                    </span>
                </div>
                {gamData.progress.next_level && (
                    <div className="flex items-center gap-2 mt-1">
                        <div className="w-24 bg-gray-700 rounded-full h-1.5 overflow-hidden">
                            <div
                                className="bg-gradient-to-r from-primary to-blue-400 h-full transition-all duration-500"
                                style={{ width: `${gamData.progress.progress_percent}%` }}
                            />
                        </div>
                        <span className="text-xs text-gray-500 whitespace-nowrap">
                            {gamData.progress.progress_percent.toFixed(0)}%
                        </span>
                    </div>
                )}
            </div>
        </div>
    )
}
