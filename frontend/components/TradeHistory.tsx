'use client'

import useSWR from 'swr'
import axios from 'axios'
import ClientOnly from './ClientOnly'

const API_URL = ''
const fetcher = (url: string) => axios.get(url).then(res => res.data)

export default function TradeHistory() {
    const { data: historyData } = useSWR(`${API_URL}/api/trade_history?limit=50`, fetcher, {
        refreshInterval: 5000
    })

    const { data: positionsData } = useSWR(`${API_URL}/api/positions`, fetcher, {
        refreshInterval: 3000
    })

    const trades = historyData?.trades || []
    const positions = positionsData?.positions || []

    // Calculate PNL
    const unrealizedPnl = positions.reduce((sum: number, pos: any) => sum + (pos.pnl || 0), 0)
    const realizedPnl = trades.reduce((sum: number, trade: any) => sum + (trade.closedPnl || 0), 0)

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
                                    {trades.map((trade: any, idx: number) => (
                                        <tr key={idx} className="hover:bg-background/30 transition-colors">
                                            <td className="p-3 text-sm text-gray-400" suppressHydrationWarning>
                                                {new Date(trade.time || trade.closedTime).toLocaleString()}
                                            </td>
                                            <td className="p-3 text-sm font-medium">{trade.coin || trade.symbol}</td>
                                            <td className="p-3">
                                                <span className={`text-xs px-2 py-1 rounded ${trade.side === 'A' || trade.dir === 'Open Long'
                                                        ? 'bg-success/20 text-success'
                                                        : 'bg-error/20 text-error'
                                                    }`}>
                                                    {trade.side === 'A' ? 'LONG' : trade.side === 'B' ? 'SHORT' : trade.dir}
                                                </span>
                                            </td>
                                            <td className="p-3 text-sm font-mono">${trade.px?.toFixed(4) || trade.entryPx?.toFixed(4) || '-'}</td>
                                            <td className="p-3 text-sm font-mono">${trade.closedPx?.toFixed(4) || '-'}</td>
                                            <td className="p-3 text-sm">{trade.sz || trade.szi || '-'}</td>
                                            <td className="p-3">
                                                <span className={`text-sm font-bold ${(trade.closedPnl || 0) >= 0 ? 'text-success' : 'text-error'
                                                    }`}>
                                                    {trade.closedPnl ? `$${trade.closedPnl.toFixed(2)}` : '-'}
                                                </span>
                                            </td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    )}
                </div>
            </div>
        </ClientOnly>
    )
}
