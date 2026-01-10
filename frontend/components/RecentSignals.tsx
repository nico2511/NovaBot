'use client'

import { useState } from 'react'
import useSWR from 'swr'
import api from '@/lib/api'
import ClientOnly from './ClientOnly'

const API_URL = ''
const fetcher = (url: string) => api.get(url).then(res => res.data)

export default function RecentSignals({ hideHeader = false, embedded = false }: { hideHeader?: boolean, embedded?: boolean }) {
    const [executing, setExecuting] = useState<number | null>(null)

    const { data: signalsData, mutate } = useSWR(`${API_URL}/api/signals`, fetcher, {
        refreshInterval: 3000
    })

    const signals = Array.isArray(signalsData?.signals) ? signalsData.signals : []
    const recentSignals = signals.slice(0, 10) // Last 10 signals

    const handleExecute = async (signal: any, idx: number) => {
        setExecuting(idx)
        try {
            await api.post(`${API_URL}/api/execute_manual_signal`, {
                signal: signal.signal,
                symbol: signal.symbol,
                price: signal.price,
                strategy: signal.strategy,
                sl: signal.sl,
                tp: signal.tp
            })
            mutate() // Refresh signals list
        } catch (error) {
            console.error('Failed to execute signal:', error)
            alert('Failed to execute signal')
        } finally {
            setExecuting(null)
        }
    }

    const containerClass = embedded
        ? "space-y-4"
        : "bg-surface/50 backdrop-blur border border-border/30 rounded-2xl p-6"

    return (
        <ClientOnly>
            <div className={containerClass}>
                {!hideHeader && <h3 className="text-lg font-semibold mb-4">📊 Recent Signals</h3>}

                {recentSignals.length === 0 ? (
                    <p className="text-gray-400 text-sm text-center py-8">No signals yet</p>
                ) : (
                    <div className="space-y-3">
                        {recentSignals.map((signal: any, idx: number) => (
                            <div
                                key={idx}
                                className="flex items-center justify-between p-3 bg-background/50 rounded-lg border border-border/20 hover:border-border/40 transition-colors"
                            >
                                <div className="flex items-center gap-3 flex-1">
                                    <div className={`w-2 h-2 rounded-full ${signal.signal === 'BUY' ? 'bg-success' : 'bg-error'
                                        }`} />
                                    <div className="flex-1">
                                        <div className="font-medium text-sm">
                                            {signal.symbol} {signal.signal}
                                        </div>
                                        <div className="text-xs text-gray-400">
                                            {signal.strategy} • <span suppressHydrationWarning>{new Date(signal.timestamp).toLocaleString()}</span>
                                        </div>
                                    </div>
                                </div>
                                <div className="flex items-center gap-3">
                                    <div className="text-right">
                                        <div className="text-sm font-mono">${signal.price?.toFixed(4)}</div>
                                        {signal.manual_approval && (
                                            <div className="text-xs text-warning">⚠️ Manual</div>
                                        )}
                                    </div>
                                    {signal.manual_approval && (
                                        <button
                                            onClick={() => handleExecute(signal, idx)}
                                            disabled={executing === idx}
                                            className="px-3 py-1 bg-primary hover:bg-primary/80 disabled:bg-gray-600 disabled:cursor-not-allowed text-white text-xs font-medium rounded transition-colors"
                                        >
                                            {executing === idx ? '...' : 'Execute'}
                                        </button>
                                    )}
                                </div>
                            </div>
                        ))}
                    </div>
                )}
            </div>
        </ClientOnly>
    )
}
