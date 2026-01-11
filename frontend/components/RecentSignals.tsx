'use client'


import useSWR from 'swr'
import api from '@/lib/api'
import ClientOnly from './ClientOnly'

const API_URL = ''
const fetcher = (url: string) => api.get(url).then(res => res.data)

export default function RecentSignals({ hideHeader = false, embedded = false }: { hideHeader?: boolean, embedded?: boolean }) {
    const { data: tradesData } = useSWR(`${API_URL}/api/trade_history`, fetcher, {
        refreshInterval: 60000, // 60s cache/refresh
        revalidateOnFocus: true,
        dedupingInterval: 50000
    })

    const recentTrades = Array.isArray(tradesData?.trades) ? tradesData.trades : []

    const containerClass = embedded
        ? "space-y-4"
        : "bg-surface/50 backdrop-blur border border-border/30 rounded-2xl p-6"

    return (
        <ClientOnly>
            <div className={containerClass}>
                {recentTrades.length === 0 ? (
                    <p className="text-gray-400 text-sm text-center py-8">No executed trades recorded yet</p>
                ) : (
                    <div className="overflow-x-auto max-h-[400px]">
                        <table className="w-full text-sm text-left">
                            <thead className="text-xs text-gray-400 uppercase bg-background/50 sticky top-0">
                                <tr>
                                    <th className="px-4 py-3">Time</th>
                                    <th className="px-4 py-3">Strategy</th>
                                    <th className="px-4 py-3">Symbol</th>
                                    <th className="px-4 py-3">Side</th>
                                    <th className="px-4 py-3">Size</th>
                                    <th className="px-4 py-3">Entry</th>
                                    <th className="px-4 py-3">Exit</th>
                                    <th className="px-4 py-3">PnL</th>
                                </tr>
                            </thead>
                            <tbody className="divide-y divide-border/20">
                                {recentTrades.map((trade: any, idx: number) => {
                                    const pnl = parseFloat(trade.pnl || '0')
                                    const isWin = pnl >= 0

                                    return (
                                        <tr key={idx} className="hover:bg-background/30 transition-colors border-b border-border/10">
                                            <td className="px-4 py-3 text-gray-400 whitespace-nowrap text-xs">{trade.time}</td>
                                            <td className="px-4 py-3 text-xs">{trade.strategy || '-'}</td>
                                            <td className="px-4 py-3 font-medium">{trade.symbol}</td>
                                            <td className="px-4 py-3">
                                                <span className={`text-xs px-2 py-0.5 rounded ${trade.side?.toUpperCase() === 'BUY'
                                                    ? 'bg-success/20 text-success'
                                                    : 'bg-error/20 text-error'
                                                    }`}>
                                                    {trade.side}
                                                </span>
                                            </td>
                                            <td className="px-4 py-3">{trade.size}</td>
                                            <td className="px-4 py-3 font-mono text-gray-300">{trade.entry_price}</td>
                                            <td className="px-4 py-3 font-mono text-gray-300">{trade.exit_price || '-'}</td>
                                            <td className={`px-4 py-3 font-bold font-mono ${isWin ? 'text-success' : 'text-error'}`}>
                                                {pnl !== 0 ? `$${pnl.toFixed(2)}` : '-'}
                                            </td>
                                        </tr>
                                    )
                                })}
                            </tbody>
                        </table>
                    </div>
                )}
            </div>
        </ClientOnly>
    )
}
