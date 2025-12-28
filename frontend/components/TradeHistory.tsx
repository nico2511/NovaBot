'use client'

import { useEffect, useState } from 'react'

interface Signal {
    timestamp: string
    strategy: string
    side: 'BUY' | 'SELL'
    price: number
    symbol: string
    manual_approval?: boolean
}

export default function TradeHistory() {
    const [signals, setSignals] = useState<Signal[]>([])

    useEffect(() => {
        const fetchSignals = async () => {
            try {
                const response = await fetch('/api/signals')
                const data = await response.json()
                setSignals(data.signals || [])
            } catch (error) {
                console.error('Failed to fetch signals:', error)
            }
        }

        fetchSignals()
        const interval = setInterval(fetchSignals, 5000)

        return () => clearInterval(interval)
    }, [])

    const handleExecute = (signal: Signal) => {
        // TODO: Call API to execute trade
        alert(`Executing ${signal.side} ${signal.symbol} @ $${signal.price}\nStrategy: ${signal.strategy}`)
    }

    return (
        <div className="bg-surface/50 backdrop-blur border border-border/30 rounded-2xl p-6">
            <div className="flex items-center justify-between mb-6">
                <h3 className="text-lg font-semibold">📊 Recent Signals</h3>
                <div className="text-sm text-gray-400">
                    {signals.length} signal{signals.length !== 1 ? 's' : ''}
                </div>
            </div>

            {signals.length === 0 ? (
                <div className="text-center py-12">
                    <div className="text-4xl mb-3">📡</div>
                    <div className="text-gray-400">No signals yet</div>
                    <div className="text-sm text-gray-500 mt-2">
                        Automatic signals will appear here
                    </div>
                </div>
            ) : (
                <div className="space-y-3">
                    {signals.slice(0, 10).map((signal, index) => (
                        <div
                            key={index}
                            className={`rounded-lg p-4 border transition-all ${signal.manual_approval
                                ? 'bg-orange-500/10 border-orange-500/30 hover:border-orange-500/50'
                                : 'bg-background/50 border-border/20 hover:border-primary/20'
                                }`}
                        >
                            <div className="flex items-center justify-between">
                                <div className="flex items-center gap-3">
                                    <div className={`w-10 h-10 rounded-full flex items-center justify-center ${signal.side === 'BUY'
                                        ? 'bg-success/20 text-success'
                                        : 'bg-error/20 text-error'
                                        }`}>
                                        {signal.side === 'BUY' ? '📈' : '📉'}
                                    </div>
                                    <div>
                                        <div className="flex items-center gap-2">
                                            <span className="font-semibold">
                                                {signal.side} {signal.symbol}
                                            </span>
                                            {signal.manual_approval && (
                                                <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-orange-500/20 text-orange-400 border border-orange-500/30">
                                                    VALIDATION NEEDED
                                                </span>
                                            )}
                                        </div>
                                        <div className="text-sm text-gray-400">{signal.strategy}</div>
                                    </div>
                                </div>
                                <div className="text-right flex items-center gap-3">
                                    <div>
                                        <div className="font-semibold">${signal.price.toLocaleString()}</div>
                                        <div className="text-xs text-gray-500">
                                            {new Date(signal.timestamp).toLocaleTimeString('fr-FR')}
                                        </div>
                                    </div>

                                    {signal.manual_approval && (
                                        <button
                                            onClick={() => handleExecute(signal)}
                                            className="px-3 py-1.5 bg-orange-500 hover:bg-orange-600 text-white rounded-md text-sm font-semibold transition-colors shadow-lg shadow-orange-500/20"
                                        >
                                            EXECUTE
                                        </button>
                                    )}
                                </div>
                            </div>
                        </div>
                    ))}
                </div>
            )}
        </div>
    )
}
