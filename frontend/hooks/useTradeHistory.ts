import { useState, useMemo } from 'react'
import useSWR from 'swr'
import axios from 'axios'

const fetcher = (url: string) => axios.get(url).then(res => res.data)

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
    timestamp?: string // For Hyperliquid trades
}

export interface TradeStats {
    totalTrades: number
    winRate: number
    totalPnL: number
    profitFactor: number
}

export function useTradeHistory() {
    const [source, setSource] = useState<'local' | 'hyperliquid' | 'all'>('all')

    // Fetch both sources
    const { data: localData, isLoading: localLoading } = useSWR('/api/trades', fetcher, { refreshInterval: 5000 })
    const { data: hlData, isLoading: hlLoading } = useSWR('/api/trades/hyperliquid?limit=100', fetcher, { refreshInterval: 30000 })

    const trades = useMemo(() => {
        const local = localData?.trades || []
        const hl = hlData?.trades || []

        let tradesToProcess: Trade[] = []

        if (source === 'local') {
            tradesToProcess = local
        } else if (source === 'hyperliquid') {
            tradesToProcess = hl
        } else { // 'all'
            // Merge and deduplicate by timestamp + symbol
            const merged = [...local, ...hl]
            const uniqueMap = new Map<string, Trade>()

            merged.forEach(trade => {
                // Use exit_time if available, otherwise timestamp
                const timeKey = trade.exit_time || trade.timestamp;
                if (timeKey) {
                    const key = `${trade.symbol}_${timeKey}`;
                    // Prioritize local trades if both exist for the same key (or just take the first one)
                    if (!uniqueMap.has(key)) {
                        uniqueMap.set(key, trade);
                    }
                }
            })
            tradesToProcess = Array.from(uniqueMap.values())
        }

        // Sort by exit_time (or timestamp) descending (newest first)
        return tradesToProcess.sort((a, b) => {
            const timeA = new Date(a.exit_time || a.timestamp || 0).getTime()
            const timeB = new Date(b.exit_time || b.timestamp || 0).getTime()
            return timeB - timeA
        })
    }, [localData, hlData, source])

    // Derived Stats
    const stats: TradeStats = useMemo(() => {
        if (trades.length === 0) return { totalTrades: 0, winRate: 0, totalPnL: 0, profitFactor: 0 }

        const totalTrades = trades.length
        const totalPnL = trades.reduce((acc, t) => acc + (t.pnl || 0), 0)
        const wins = trades.filter(t => (t.pnl || 0) > 0).length
        const winRate = (wins / totalTrades) * 100

        const grossProfit = trades.filter(t => (t.pnl || 0) > 0).reduce((acc, t) => acc + (t.pnl || 0), 0)
        const grossLoss = Math.abs(trades.filter(t => (t.pnl || 0) < 0).reduce((acc, t) => acc + (t.pnl || 0), 0))
        const profitFactor = grossLoss === 0 ? (grossProfit > 0 ? Infinity : 0) : grossProfit / grossLoss

        return { totalTrades, winRate, totalPnL, profitFactor }
    }, [trades])

    return {
        trades,
        isLoading: localLoading || hlLoading,
        source,
        setSource,
        stats
    }
}
