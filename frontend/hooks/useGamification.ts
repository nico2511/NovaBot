import useSWR from 'swr'
import axios from 'axios'

const fetcher = (url: string) => axios.get(url).then(res => res.data)

export interface GamificationStatus {
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

export function useGamification() {
    const { data, error, isLoading } = useSWR('/api/gamification_status', fetcher, {
        refreshInterval: 10000
    })

    const gamStatus: GamificationStatus | null = data?.status === 'success' ? data.gamification : null

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

    return {
        gamStatus,
        isLoading,
        error,
        getLevelEmoji,
        getLevelColor
    }
}
