import useSWR from 'swr'
import axios from 'axios'

const API_URL = ''
const fetcher = (url: string) => axios.get(url).then(res => res.data)

export interface DashboardStatus {
    active_symbol: string
    symbol_data: {
        price: number
        volume_24h: number
        change_24h: number
    }
    trading_enabled: boolean
    is_running: boolean
    active_trade: any | null
    active_strategy_name: string
    market_regime: string
    regime_score: number
}

export function useDashboard() {
    const { data: status, error, isLoading } = useSWR<DashboardStatus>(
        `${API_URL}/api/status`,
        fetcher,
        { refreshInterval: 1000 } // Fast refresh for dashboard
    )

    // Derived state
    const activeTrade = status?.active_trade || null
    const isTradingEnabled = status?.trading_enabled || false
    const isActive = status?.is_running || false

    return {
        status,
        activeTrade,
        isTradingEnabled,
        isActive,
        isLoading: isLoading || !status,
        error
    }
}
