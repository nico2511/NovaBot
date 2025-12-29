'use client'

import { useEffect, useState, useMemo } from 'react'
import axios from 'axios'
import useSWR from 'swr'
import Link from 'next/link'
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ReferenceLine } from 'recharts'

interface Trade {
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

const fetcher = (url: string) => fetch(url).then(res => res.json())

export default function TradesPage() {
    const [tradeSource, setTradeSource] = useState<'local' | 'hyperliquid' | 'all'>('all')

    // Fetch both sources
    const { data: localData, error: localError } = useSWR('/api/trades', fetcher, { refreshInterval: 5000 })
    const { data: hlData, error: hlError } = useSWR('/api/trades/hyperliquid?limit=100', fetcher, { refreshInterval: 30000 })

    // Merge and deduplicate trades
    const allTrades = useMemo(() => {
        const local = localData?.trades || []
        const hl = hlData?.trades || []

        let tradesToProcess: Trade[] = []

        if (tradeSource === 'local') {
            tradesToProcess = local
        } else if (tradeSource === 'hyperliquid') {
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

        // Sort by exit_time (or timestamp) descending for display in table
        return tradesToProcess.sort((a, b) => {
            const timeA = new Date(a.exit_time || a.timestamp || 0).getTime()
            const timeB = new Date(b.exit_time || b.timestamp || 0).getTime()
            return timeB - timeA
        })
    }, [localData, hlData, tradeSource])

    const { data: statsData } = useSWR('/api/stats', fetcher, { refreshInterval: 5000 })

    const [trades, setTrades] = useState<Trade[]>([])
    const [chartData, setChartData] = useState<any[]>([])
    const [cumulativePnL, setCumulativePnL] = useState(0)

    useEffect(() => {
        if (allTrades && allTrades.length > 0) {
            // allTrades is already sorted descending, reverse for chart (oldest first)
            const sortedForChart = [...allTrades].reverse()
            setTrades(allTrades) // Already sorted newest first for table

            // Process chart data (cumulative PnL)
            let runningPnL = 0
            const cData = sortedForChart.map(t => {
                const pnl = t.pnl ?? 0
                runningPnL += pnl
                return {
                    time: new Date(t.exit_time || t.timestamp || '').toLocaleDateString() + ' ' + new Date(t.exit_time || t.timestamp || '').toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }),
                    pnl: runningPnL,
                    trade_pnl: pnl
                }
            })
            setChartData(cData)
            setCumulativePnL(runningPnL)
        }
    }, [allTrades])

    const stats = statsData?.stats || {
        total_trades: 0,
        win_rate: 0,
        total_pnl: 0,
        profit_factor: 0
    }

    if (localError || hlError) return <div className="p-8 text-center text-red-400">Failed to load trade data. Is the backend running?</div>

    return (
        <div className="min-h-screen bg-background text-white p-6">
            <div className="max-w-7xl mx-auto space-y-6">

                {/* Header */}
                <div className="flex items-center justify-between">
                    <div>
                        <h1 className="text-3xl font-bold bg-gradient-to-r from-blue-400 to-purple-400 bg-clip-text text-transparent">
                            Trade Analysis
                        </h1>
                        <p className="text-gray-400 text-sm">Detailed performance metrics and history</p>
                    </div>
                    <Link href="/" className="px-4 py-2 bg-white/5 hover:bg-white/10 rounded-lg text-sm transition-colors border border-white/10">
                        ← Back to Dashboard
                    </Link>
                </div>

                {/* KPI Cards */}
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                    <div className="bg-surface/50 backdrop-blur border border-white/5 p-4 rounded-xl">
                        <div className="text-gray-400 text-xs uppercase tracking-wider mb-1">Total PnL</div>
                        <div className={`text-2xl font-bold ${stats.total_pnl >= 0 ? 'text-success' : 'text-error'}`}>
                            ${stats.total_pnl.toFixed(2)}
                        </div>
                    </div>
                    <div className="bg-surface/50 backdrop-blur border border-white/5 p-4 rounded-xl">
                        <div className="text-gray-400 text-xs uppercase tracking-wider mb-1">Win Rate</div>
                        <div className={`text-2xl font-bold ${stats.win_rate >= 50 ? 'text-blue-400' : 'text-yellow-500'}`}>
                            {stats.win_rate.toFixed(1)}%
                        </div>
                    </div>
                    <div className="bg-surface/50 backdrop-blur border border-white/5 p-4 rounded-xl">
                        <div className="text-gray-400 text-xs uppercase tracking-wider mb-1">Profit Factor</div>
                        <div className="text-2xl font-bold text-gray-200">
                            {stats.profit_factor === Infinity ? '∞' : stats.profit_factor.toFixed(2)}
                        </div>
                    </div>
                    <div className="bg-surface/50 backdrop-blur border border-white/5 p-4 rounded-xl">
                        <div className="text-gray-400 text-xs uppercase tracking-wider mb-1">Total Trades</div>
                        <div className="text-2xl font-bold text-gray-200">
                            {stats.total_trades}
                        </div>
                    </div>
                </div>

                {/* PnL Chart */}
                <div className="bg-surface/50 backdrop-blur border border-white/5 p-6 rounded-xl h-[400px]">
                    <h3 className="text-lg font-semibold mb-4">Cumulative PnL Performance</h3>
                    <ResponsiveContainer width="100%" height="100%">
                        <LineChart data={chartData}>
                            <CartesianGrid strokeDasharray="3 3" stroke="#ffffff10" />
                            <XAxis dataKey="time" stroke="#6b7280" fontSize={12} tick={{ fill: '#6b7280' }} minTickGap={30} />
                            <YAxis stroke="#6b7280" fontSize={12} tick={{ fill: '#6b7280' }} />
                            <Tooltip
                                contentStyle={{ backgroundColor: '#1f2937', borderColor: '#374151', borderRadius: '8px' }}
                                itemStyle={{ color: '#fff' }}
                            />
                            <ReferenceLine y={0} stroke="#ffffff30" />
                            <Line
                                type="monotone"
                                dataKey="pnl"
                                stroke="#8b5cf6"
                                strokeWidth={2}
                                dot={false}
                                activeDot={{ r: 6 }}
                            />
                        </LineChart>
                    </ResponsiveContainer>
                </div>

                {/* Trade History Table */}
                <div className="bg-surface/50 backdrop-blur border border-white/5 rounded-xl overflow-hidden">
                    <div className="p-6 border-b border-white/5 flex items-center justify-between">
                        <h2 className="text-xl font-semibold">Trade History</h2>

                        {/* Source Toggle */}
                        <div className="flex items-center gap-2 bg-background/50 rounded-lg p-1">
                            <button
                                onClick={() => setTradeSource('all')}
                                className={`px-3 py-1.5 rounded text-sm font-medium transition-colors ${tradeSource === 'all'
                                    ? 'bg-primary text-white'
                                    : 'text-gray-400 hover:text-white'
                                    }`}
                            >
                                All
                            </button>
                            <button
                                onClick={() => setTradeSource('local')}
                                className={`px-3 py-1.5 rounded text-sm font-medium transition-colors ${tradeSource === 'local'
                                    ? 'bg-blue-500 text-white'
                                    : 'text-gray-400 hover:text-white'
                                    }`}
                            >
                                🤖 Bot
                            </button>
                            <button
                                onClick={() => setTradeSource('hyperliquid')}
                                className={`px-3 py-1.5 rounded text-sm font-medium transition-colors ${tradeSource === 'hyperliquid'
                                    ? 'bg-purple-500 text-white'
                                    : 'text-gray-400 hover:text-white'
                                    }`}
                            >
                                📊 Hyperliquid
                            </button>
                        </div>
                    </div>
                    <div className="overflow-x-auto">
                        <table className="w-full text-sm">
                            <thead>
                                <tr className="bg-white/5 text-left text-gray-400">
                                    <th className="p-4">Time</th>
                                    <th className="p-4">Symbol</th>
                                    <th className="p-4">Side</th>
                                    <th className="p-4">Strategy</th>
                                    <th className="p-4 text-right">Entry</th>
                                    <th className="p-4 text-right">Exit</th>
                                    <th className="p-4 text-right">PnL ($)</th>
                                    <th className="p-4 text-right">PnL (%)</th>
                                    <th className="p-4">Reason</th>
                                </tr>
                            </thead>
                            <tbody className="divide-y divide-white/5">
                                {trades.map((trade) => (
                                    <tr key={trade.id} className="hover:bg-white/5 transition-colors">
                                        <td className="p-4 text-gray-400">
                                            {new Date(trade.exit_time).toLocaleString()}
                                        </td>
                                        <td className="p-4 font-bold">{trade.symbol}</td>
                                        <td className="p-4">
                                            <span className={`px-2 py-1 rounded text-xs font-bold ${trade.side === 'BUY' ? 'bg-success/20 text-success' : 'bg-error/20 text-error'}`}>
                                                {trade.side}
                                            </span>
                                        </td>
                                        <td className="p-4 text-gray-300">{trade.strategy}</td>
                                        <td className="p-4 text-right font-mono">${(trade.entry_price ?? 0).toFixed(4)}</td>
                                        <td className="p-4 text-right font-mono">${(trade.exit_price ?? 0).toFixed(4)}</td>
                                        <td className={`p-4 text-right font-bold ${(trade.pnl ?? 0) >= 0 ? 'text-success' : 'text-error'}`}>
                                            {(trade.pnl ?? 0) >= 0 ? '+' : ''}{(trade.pnl ?? 0).toFixed(2)}
                                        </td>
                                        <td className={`p-4 text-right font-bold ${(trade.pnl ?? 0) >= 0 ? 'text-success' : 'text-error'}`}>
                                            {(trade.pnl_percent ?? 0).toFixed(2)}%
                                        </td>
                                        <td className="p-4">
                                            <span className={`px-2 py-1 rounded text-xs ${trade.exit_reason === 'TP' ? 'bg-green-500/20 text-green-400' :
                                                trade.exit_reason === 'SL' ? 'bg-red-500/20 text-red-400' :
                                                    'bg-blue-500/20 text-blue-400'
                                                }`}>
                                                {trade.exit_reason}
                                            </span>
                                        </td>
                                    </tr>
                                ))}
                                {trades.length === 0 && (
                                    <tr>
                                        <td colSpan={9} className="p-8 text-center text-gray-500">
                                            No trades recorded yet.
                                        </td>
                                    </tr>
                                )}
                            </tbody>
                        </table>
                    </div>
                </div>

            </div>
        </div>
    )
}
