'use client'

import useSWR from 'swr'
import axios from 'axios'
import ClientOnly from './ClientOnly'

const API_URL = ''
const fetcher = (url: string) => axios.get(url).then(res => res.data)

export default function TradeHistory() {
    const { data: historyData, error: historyError } = useSWR(`${API_URL}/api/trade_history?limit=50`, fetcher, {
        refreshInterval: 5000,
        onError: (err) => console.error('Trade history fetch error:', err)
    })

    const { data: positionsData } = useSWR(`${API_URL}/api/positions`, fetcher, {
        refreshInterval: 3000
    })

    const trades = historyData?.trades || []
    const positions = positionsData?.positions || []

    // Calculate PNL - handle both formats
    const unrealizedPnl = positions.reduce((sum: number, pos: any) => sum + (pos.pnl || 0), 0)
    const realizedPnl = trades.reduce((sum: number, trade: any) => sum + (trade.pnl || trade.closedPnl || 0), 0)

    console.log('TradeHistory - trades:', trades.length, 'positions:', positions.length, 'realizedPnl:', realizedPnl)

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
                            No trade history yet
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
                                    {trades.map((trade: any, idx: number) => {
                                        // Handle both API formats
                                        const symbol = trade.coin || trade.symbol || '-'
                                        const side = trade.side === 'A' || trade.side === 'BUY' || trade.dir === 'Open Long' ? 'LONG' : 'SHORT'
                                        const entryPrice = trade.px || trade.entry_price || trade.entryPx || 0
                                        const exitPrice = trade.closedPx || trade.exit_price || 0
                                        const size = trade.sz || trade.szi || trade.size || 0
                                        const pnl = trade.closedPnl || trade.pnl || 0
                                        const timestamp = trade.time || trade.closedTime || trade.timestamp || trade.entry_time

                                        return (
                                            <tr key={idx} className="hover:bg-background/30 transition-colors">
                                                <td className="p-3 text-sm text-gray-400" suppressHydrationWarning>
                                                    {new Date(timestamp).toLocaleString()}
                                                </td>
                                                <td className="p-3 text-sm font-medium">{symbol}</td>
                                                <td className="p-3">
                                                    <span className={`text-xs px-2 py-1 rounded ${side === 'LONG'
                                                        ? 'bg-success/20 text-success'
                                                        : 'bg-error/20 text-error'
                                                        }`}>
                                                        {side}
                                                    </span>
                                                </td>
                                                <td className="p-3 text-sm font-mono">${entryPrice.toFixed(4)}</td>
                                                <td className="p-3 text-sm font-mono">{exitPrice > 0 ? `$${exitPrice.toFixed(4)}` : '-'}</td>
                                                <td className="p-3 text-sm">{size}</td>
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
