'use client'

import React from 'react'
import useSWR from 'swr'
import ClientOnly from './ClientOnly'
import { useTradeHistory, Trade } from '../hooks/useTradeHistory'
import axios from 'axios'

const fetcher = (url: string) => axios.get(url).then(res => res.data)

export default function TradeHistory() {
    // 1. Get Historical Trades (Merged Local + Hyperliquid)
    const { trades, stats, isLoading } = useTradeHistory()

    // 2. Get Open Positions (for Unrealized PNL)
    const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8001'
    const { data: positionsData } = useSWR(`${API_BASE_URL}/api/positions`, fetcher, {
        refreshInterval: 3000
    })

    const positions = positionsData?.positions || []

    // Calculate PNL
    const unrealizedPnl = positions.reduce((sum: number, pos: any) => sum + (pos.pnl || 0), 0)
    const realizedPnl = stats.totalPnL // From the hook

    console.log('[TradeHistory] Render. Trades:', trades.length, 'Unrealized:', unrealizedPnl)

    return (
        <ClientOnly>
            <div className="space-y-6">
                {/* PNL Stats */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div className="bg-surface/50 backdrop-blur border border-border/30 rounded-xl p-6">
                        <div className="text-sm text-gray-400 mb-1">Unrealized PNL</div>
                        <div className={`text-3xl font-bold ${unrealizedPnl >= 0 ? 'text-success' : 'text-error'}`}>
                            ${unrealizedPnl.toFixed(2)}
                        </div>
                        <div className="text-xs text-gray-500 mt-1">From open positions</div>
                    </div>
                    <div className="bg-surface/50 backdrop-blur border border-border/30 rounded-xl p-6">
                        <div className="text-sm text-gray-400 mb-1">Realized PNL</div>
                        <div className={`text-3xl font-bold ${realizedPnl >= 0 ? 'text-success' : 'text-error'}`}>
                            ${realizedPnl.toFixed(2)}
                        </div>
                        <div className="text-xs text-gray-500 mt-1">From closed trades</div>
                    </div>
                </div>

                {/* Trade History Table */}
                <div className="bg-surface/50 backdrop-blur border border-border/30 rounded-xl overflow-hidden">
                    <div className="p-4 border-b border-border/30">
                        <h3 className="text-lg font-semibold">📜 Trade History</h3>
                    </div>

                    {trades.length === 0 ? (
                        <div className="p-8 text-center text-gray-400">
                            {isLoading ? 'Loading...' : 'No trade history yet'}
                        </div>
                    ) : (
                        <div className="overflow-x-auto max-h-[600px] overflow-y-auto">
                            <table className="w-full">
                                <thead className="bg-background/50 sticky top-0">
                                    <tr className="text-left text-xs text-gray-400 uppercase">
                                        <th className="p-3">Time</th>
                                        <th className="p-3">Symbol</th>
                                        <th className="p-3">Side</th>
                                        <th className="p-3">Entry</th>
                                        <th className="p-3">Exit</th>
                                        <th className="p-3">Size</th>
                                        <th className="p-3">PNL</th>
                                    </tr>
                                </thead>
                                <tbody className="divide-y divide-border/20">
                                    {trades.map((trade: Trade, idx: number) => {
                                        // Normalize data (hook handles some, but be safe)
                                        const side = trade.side === 'B' ? 'BUY' : (trade.side === 'S' ? 'SELL' : trade.side)
                                        const displaySide = side === 'BUY' || side === 'LONG' ? 'LONG' : 'SHORT'
                                        const pnl = trade.pnl || 0

                                        // Timestamp handling
                                        let dateStr = '-'
                                        try {
                                            const ts = trade.exit_time || trade.timestamp || trade.entry_time
                                            if (ts) {
                                                dateStr = new Date(ts).toLocaleString()
                                            }
                                        } catch (e) {
                                            console.error('Date parse error', e)
                                        }

                                        return (
                                            <tr key={idx} className="hover:bg-background/30 transition-colors">
                                                <td className="p-3 text-sm text-gray-400" suppressHydrationWarning>
                                                    {dateStr}
                                                </td>
                                                <td className="p-3 text-sm font-medium">{trade.symbol}</td>
                                                <td className="p-3">
                                                    <span className={`text-xs px-2 py-1 rounded ${displaySide === 'LONG'
                                                        ? 'bg-success/20 text-success'
                                                        : 'bg-error/20 text-error'
                                                        }`}>
                                                        {displaySide}
                                                    </span>
                                                </td>
                                                <td className="p-3 text-sm font-mono">${Number(trade.entry_price).toFixed(4)}</td>
                                                <td className="p-3 text-sm font-mono">
                                                    {Number(trade.exit_price) > 0 ? `$${Number(trade.exit_price).toFixed(4)}` : '-'}
                                                </td>
                                                <td className="p-3 text-sm">{trade.size || 0}</td>
                                                <td className="p-3">
                                                    <span className={`text-sm font-bold ${pnl >= 0 ? 'text-success' : 'text-error'
                                                        }`}>
                                                        ${pnl.toFixed(2)}
                                                    </span>
                                                </td>
                                            </tr>
                                        )
                                    })}
                                </tbody>
                            </table>
                        </div>
                    )}
                </div>
            </div>
        </ClientOnly>
    )
}
