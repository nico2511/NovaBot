'use client'

import { useState } from 'react'
import api from '@/lib/api'

interface ManualSignal {
    strategy: string
    symbol: string
    action: 'BUY' | 'SELL'
    price: number
    sl: number
    tp: number
    timestamp: string
    comment?: string
}

interface Props {
    signal: ManualSignal | null
    onDismiss: () => void
}

export default function ManualTradeWidget({ signal, onDismiss }: Props) {
    const [executing, setExecuting] = useState(false)
    const [error, setError] = useState<string | null>(null)

    if (!signal) return null

    // Calculs
    const riskDistance = Math.abs(signal.price - signal.sl)
    const rewardDistance = Math.abs(signal.tp - signal.price)
    const riskReward = rewardDistance / riskDistance
    const slPercent = (riskDistance / signal.price) * 100
    const tpPercent = (rewardDistance / signal.price) * 100

    // Validation du R:R
    const isGoodRR = riskReward >= 1.5
    const rrColor = riskReward >= 2.0 ? 'text-green-400' : riskReward >= 1.5 ? 'text-yellow-400' : 'text-red-400'

    const handleTakeTrade = async () => {
        setExecuting(true)
        setError(null)

        try {
            const response = await api.post('/api/execute_manual_trade', {
                symbol: signal.symbol,
                action: signal.action,
                price: signal.price,
                sl: signal.sl,
                tp: signal.tp,
                strategy: signal.strategy
            })

            if (response.data.status === 'success') {
                onDismiss()
            } else {
                setError(response.data.message || 'Failed to execute trade')
            }
        } catch (e: any) {
            console.error(e)
            setError(e.response?.data?.message || 'Network error')
        } finally {
            setExecuting(false)
        }
    }

    return (
        <div className="fixed bottom-4 right-4 z-50 bg-gradient-to-br from-purple-900 to-indigo-900 border-2 border-purple-500 rounded-2xl p-6 shadow-2xl max-w-md animate-in slide-in-from-bottom">
            {/* Header */}
            <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-2">
                    <span className="text-2xl">🔎</span>
                    <h3 className="font-bold text-white text-lg">Validation Requise</h3>
                </div>
                <button
                    onClick={onDismiss}
                    className="text-gray-400 hover:text-white transition-colors"
                    disabled={executing}
                >
                    ✕
                </button>
            </div>

            {/* Strategy Badge */}
            <div className="bg-blue-500/20 border border-blue-500/50 rounded-lg px-3 py-1 inline-block mb-4">
                <span className="text-blue-300 font-bold text-sm">{signal.strategy}</span>
            </div>

            {/* Trade Details */}
            <div className="space-y-3 mb-6">
                <div className="flex justify-between items-center">
                    <span className="text-gray-400">Symbol</span>
                    <span className="text-white font-bold text-lg">{signal.symbol}</span>
                </div>

                <div className="flex justify-between items-center">
                    <span className="text-gray-400">Action</span>
                    <span className={`font-bold text-lg ${signal.action === 'BUY' ? 'text-green-400' : 'text-red-400'}`}>
                        {signal.action === 'BUY' ? '📈 LONG' : '📉 SHORT'}
                    </span>
                </div>

                <div className="flex justify-between items-center">
                    <span className="text-gray-400">Entry Price</span>
                    <span className="text-white font-mono">${signal.price.toFixed(2)}</span>
                </div>

                {/* SL/TP Grid */}
                <div className="grid grid-cols-2 gap-4 mt-4 p-4 bg-black/20 rounded-lg">
                    <div>
                        <div className="text-red-400 text-xs mb-1">Stop Loss</div>
                        <div className="text-white font-mono text-sm">${signal.sl.toFixed(2)}</div>
                        <div className="text-red-300 text-xs">-{slPercent.toFixed(2)}%</div>
                    </div>
                    <div>
                        <div className="text-green-400 text-xs mb-1">Take Profit</div>
                        <div className="text-white font-mono text-sm">${signal.tp.toFixed(2)}</div>
                        <div className="text-green-300 text-xs">+{tpPercent.toFixed(2)}%</div>
                    </div>
                </div>

                {/* Risk/Reward */}
                <div className={`flex justify-between items-center p-3 rounded-lg border ${isGoodRR ? 'bg-green-500/10 border-green-500/30' : 'bg-yellow-500/10 border-yellow-500/30'
                    }`}>
                    <span className={isGoodRR ? 'text-green-300 font-bold' : 'text-yellow-300 font-bold'}>
                        Risk:Reward
                    </span>
                    <span className={`font-bold text-lg ${rrColor}`}>
                        1:{riskReward.toFixed(2)}
                    </span>
                </div>

                {/* Warning si R:R faible */}
                {!isGoodRR && (
                    <div className="bg-yellow-500/10 border border-yellow-500/30 rounded-lg p-2 text-yellow-300 text-xs">
                        ⚠️ R:R inférieur à 1:1.5 - Trade risqué
                    </div>
                )}

                {/* Comment */}
                {signal.comment && (
                    <div className="text-gray-400 text-sm italic border-l-2 border-gray-600 pl-3">
                        {signal.comment}
                    </div>
                )}
            </div>

            {/* Error Message */}
            {error && (
                <div className="mb-4 bg-red-500/20 border border-red-500/50 rounded-lg p-3 text-red-300 text-sm">
                    ❌ {error}
                </div>
            )}

            {/* Actions */}
            <div className="flex gap-3">
                <button
                    onClick={onDismiss}
                    disabled={executing}
                    className="flex-1 bg-gray-700 hover:bg-gray-600 text-white py-3 rounded-lg font-bold transition-colors disabled:opacity-50"
                >
                    Ignorer
                </button>
                <button
                    onClick={handleTakeTrade}
                    disabled={executing}
                    className="flex-1 bg-gradient-to-r from-green-600 to-emerald-600 hover:from-green-500 hover:to-emerald-500 text-white py-3 rounded-lg font-bold shadow-lg transition-transform active:scale-95 disabled:opacity-50"
                >
                    {executing ? (
                        <span className="flex items-center justify-center gap-2">
                            <span className="animate-spin">⏳</span>
                            Exécution...
                        </span>
                    ) : (
                        '✅ Prendre le Trade'
                    )}
                </button>
            </div>

            {/* Timestamp */}
            <div className="mt-3 text-center text-gray-500 text-xs" suppressHydrationWarning>
                Signal reçu: {new Date(signal.timestamp).toLocaleTimeString()}
            </div>
        </div>
    )
}
