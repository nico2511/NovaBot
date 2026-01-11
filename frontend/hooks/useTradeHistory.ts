import { useMemo } from 'react'
import useSWR from 'swr'
import axios from 'axios'
import { getApiUrl } from '../utils/apiConfig'

const fetcher = (path: string) => {
    const url = `${getApiUrl()}${path}`
    console.log('[useTradeHistory] Fetching:', url)
    return axios.get(url).then(res => res.data)
}

export interface Trade {
    id: string
    symbol: string
    side: string
    entry_price: number
    exit_price: number
    pnl: number
    pnl_percent: number
    entry_time: string
    exit_time: string
    strategy: string
    exit_reason: string
    timestamp?: string
    size: number
    fee?: number
    leverage?: number
}

export interface TradeStats {
    totalTrades: number
    winRate: number
    totalPnL: number
    profitFactor: number
}

export function useTradeHistory() {
    const { data, isLoading } = useSWR('/api/trade_history', fetcher, { refreshInterval: 5000 })

    const trades = useMemo(() => {
        const rawTrades = data?.trades || []

        return rawTrades.sort((a: Trade, b: Trade) => {
            const timeA = new Date(a.exit_time || a.timestamp || 0).getTime()
            const timeB = new Date(b.exit_time || b.timestamp || 0).getTime()
            return timeB - timeA
        })
    }, [data])

    const stats: TradeStats = useMemo(() => {
        if (trades.length === 0) return { totalTrades: 0, winRate: 0, totalPnL: 0, profitFactor: 0 }

        const totalTrades = trades.length
        const totalPnL = trades.reduce((acc: number, t: Trade) => acc + (t.pnl || 0), 0)
        const wins = trades.filter((t: Trade) => (t.pnl || 0) > 0).length
        const winRate = (wins / totalTrades) * 100

        const grossProfit = trades.filter((t: Trade) => (t.pnl || 0) > 0).reduce((acc: number, t: Trade) => acc + (t.pnl || 0), 0)
        const grossLoss = Math.abs(trades.filter((t: Trade) => (t.pnl || 0) < 0).reduce((acc: number, t: Trade) => acc + (t.pnl || 0), 0))
        const profitFactor = grossLoss === 0 ? (grossProfit > 0 ? Infinity : 0) : grossProfit / grossLoss

        return { totalTrades, winRate, totalPnL, profitFactor }
    }, [trades])

    return {
        trades,
        isLoading,
        stats
    }
}
