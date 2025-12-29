'use client'

import useSWR from 'swr'
import axios from 'axios'

const API_URL = ''
const fetcher = (url: string) => axios.get(url).then(res => res.data)

export default function RecentSignals() {
    const { data: signalsData } = useSWR(`${API_URL}/api/signals`, fetcher, {
        refreshInterval: 3000
    })

    const signals = signalsData?.signals || []
    const recentSignals = signals.slice(0, 5) // Last 5 signals

    return (
        <div className="bg-surface/50 backdrop-blur border border-border/30 rounded-2xl p-6">
            <h3 className="text-lg font-semibold mb-4">📊 Recent Signals</h3>

            {recentSignals.length === 0 ? (
                <p className="text-gray-400 text-sm text-center py-8">No signals yet</p>
            ) : (
                <div className="space-y-3">
                    {recentSignals.map((signal: any, idx: number) => (
                        <div
                            key={idx}
                            className="flex items-center justify-between p-3 bg-background/50 rounded-lg border border-border/20 hover:border-border/40 transition-colors"
                        >
                            <div className="flex items-center gap-3">
                                <div className={`w-2 h-2 rounded-full ${signal.signal === 'BUY' ? 'bg-success' : 'bg-error'
                                    }`} />
                                <div>
                                    <div className="font-medium text-sm">
                                        {signal.symbol} {signal.signal}
                                    </div>
                                    <div className="text-xs text-gray-400">
                                        {signal.strategy} • {new Date(signal.timestamp).toLocaleTimeString()}
                                    </div>
                                </div>
                            </div>
                            <div className="text-right">
                                <div className="text-sm font-mono">${signal.price?.toFixed(4)}</div>
                                {signal.manual_approval && (
                                    <div className="text-xs text-warning">⚠️ Manual</div>
                                )}
                            </div>
                        </div>
                    ))}
                </div>
            )}
        </div>
    )
}
