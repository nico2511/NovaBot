import { Trade } from '@/hooks/useTradeHistory'

interface TradesTableProps {
    trades: Trade[]
    loading: boolean
}

const PnLBadge = ({ value, percent }: { value: number, percent: number }) => {
    const isWin = value >= 0
    return (
        <div className="flex flex-col items-end">
            <span className={`font-bold ${isWin ? 'text-green-400' : 'text-red-400'}`}>
                {isWin ? '+' : ''}{value.toFixed(2)}
            </span>
            <span className={`text-xs ${isWin ? 'text-green-500/70' : 'text-red-500/70'}`}>
                {percent.toFixed(2)}%
            </span>
        </div>
    )
}

const ExitReasonBadge = ({ reason }: { reason: string }) => {
    let color = 'bg-blue-500/20 text-blue-400'
    if (reason === 'TP') color = 'bg-green-500/20 text-green-400'
    if (reason === 'SL') color = 'bg-red-500/20 text-red-400'

    return (
        <span className={`px-2 py-1 rounded text-xs font-bold ${color}`}>
            {reason}
        </span>
    )
}

export default function TradesTable({ trades, loading }: TradesTableProps) {
    if (loading) {
        return (
            <div className="p-12 text-center text-gray-400">
                <div className="animate-spin w-8 h-8 border-4 border-blue-500 border-t-transparent rounded-full mx-auto mb-4"></div>
                Loading trades...
            </div>
        )
    }

    if (trades.length === 0) {
        return (
            <div className="p-12 text-center text-gray-500 bg-white/5 rounded-xl">
                No trades found for this source.
            </div>
        )
    }

    return (
        <div className="overflow-x-auto">
            <table className="w-full text-sm">
                <thead>
                    <tr className="bg-white/5 text-left text-gray-400">
                        <th className="p-4 rounded-tl-xl">Time</th>
                        <th className="p-4">Symbol</th>
                        <th className="p-4">Side</th>
                        <th className="p-4">Strategy</th>
                        <th className="p-4 text-right">Entry</th>
                        <th className="p-4 text-right">Exit</th>
                        <th className="p-4 text-right">PnL</th>
                        <th className="p-4 rounded-tr-xl">Reason</th>
                    </tr>
                </thead>
                <tbody className="divide-y divide-white/5">
                    {trades.map((trade) => {
                        const time = new Date(trade.exit_time || trade.timestamp || 0).toLocaleString()

                        return (
                            <tr key={trade.id || `${trade.symbol}_${trade.timestamp}`} className="hover:bg-white/5 transition-colors">
                                <td className="p-4 text-gray-400" suppressHydrationWarning>{time}</td>
                                <td className="p-4 font-bold">{trade.symbol}</td>
                                <td className="p-4">
                                    <span className={`px-2 py-1 rounded text-xs font-bold ${trade.side === 'BUY' ? 'bg-green-500/20 text-green-400' : 'bg-red-500/20 text-red-400'}`}>
                                        {trade.side}
                                    </span>
                                </td>
                                <td className="p-4 text-gray-300 font-mono text-xs">{trade.strategy || 'N/A'}</td>
                                <td className="p-4 text-right font-mono text-gray-300">${(trade.entry_price ?? 0).toFixed(4)}</td>
                                <td className="p-4 text-right font-mono text-gray-300">${(trade.exit_price ?? 0).toFixed(4)}</td>
                                <td className="p-4 text-right">
                                    <PnLBadge value={trade.pnl ?? 0} percent={trade.pnl_percent ?? 0} />
                                </td>
                                <td className="p-4">
                                    <ExitReasonBadge reason={trade.exit_reason || 'Unknown'} />
                                </td>
                            </tr>
                        )
                    })}
                </tbody>
            </table>
        </div>
    )
}
