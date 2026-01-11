import { useState, useMemo } from 'react'
import useSWR from 'swr'
import axios from 'axios'

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8001'

const fetcher = (url: string) => axios.get(url).then(res => {
    console.log(`[useTradeHistory] Fetched ${url}:`, res.data)
    return res.data
}).catch(err => {
    console.error(`[useTradeHistory] Error fetching ${url}:`, err)
    throw err
})

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
    const [source, setSource] = useState<'local' | 'hyperliquid' | 'all'>('all')

    // Fetch both sources using absolute URLs
    const { data: localData, isLoading: localLoading } = useSWR(`${API_BASE_URL}/api/trades`, fetcher, { refreshInterval: 5000 })
    const { data: hlData, isLoading: hlLoading } = useSWR(`${API_BASE_URL}/api/trades/hyperliquid?limit=100`, fetcher, { refreshInterval: 30000 })

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
                // Use ID if available, otherwise composite key
                const uniqueId = trade.id || trade.oid || `${trade.symbol}_${timeKey}`;

                if (uniqueId) {
                    // Prioritize local trades (CSV) if duplicates found
                    if (!uniqueMap.has(uniqueId)) {
                        uniqueMap.set(uniqueId, trade);
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
