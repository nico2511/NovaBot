import useSWR from 'swr'
import axios from 'axios'
import { useWebSocket } from './useWebSocket'
import { useEffect, useState } from 'react'

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
    const [gamStatus, setGamStatus] = useState<GamificationStatus | null>(null)
    const [useWebSocketMode, setUseWebSocketMode] = useState(true)

    // WebSocket connection
    const wsUrl = process.env.NEXT_PUBLIC_WS_URL || 'ws://localhost:8000'
    const { isConnected, lastMessage } = useWebSocket(`${wsUrl}/ws/gamification`, {
        onMessage: (data) => {
            if (data.type === 'TIER_UPDATE') {
                // Update gamification status from WebSocket
                console.log('Received tier update via WebSocket:', data)
                // TODO: Update gamStatus with new data
            }
        },
        onError: () => {
            console.warn('WebSocket failed, falling back to polling')
            setUseWebSocketMode(false)
        }
    })

    // Fallback to polling if WebSocket fails
    const { data, error, isLoading } = useSWR(
        useWebSocketMode ? null : '/api/gamification_status',
        fetcher,
        {
            refreshInterval: useWebSocketMode ? 0 : 10000 // Only poll if WebSocket is disabled
        }
    )

    // Update gamStatus from polling data
    useEffect(() => {
        if (data?.status === 'success') {
            setGamStatus(data.gamification)
        }
    }, [data])

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
            case 'Goblin': return 'from-gray-500 to-gray-600'        // NEBULA
            case 'Mercenary': return 'from-gray-300 to-gray-400'     // PROTOSTAR
            case 'Whale': return 'from-yellow-600 to-yellow-700'     // SUPERNOVA
            default: return 'from-gray-500 to-gray-600'
        }
    }

    return {
        gamStatus,
        isLoading: isLoading && !gamStatus,
        error,
        isWebSocketConnected: isConnected,
        getLevelEmoji,
        getLevelColor
    }
}
