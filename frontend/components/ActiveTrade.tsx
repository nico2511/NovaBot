'use client'

import { useEffect, useState } from 'react'
import axios from 'axios'

const API_URL = ''

interface Trade {
    symbol: string
    side: 'BUY' | 'SELL'
    entry: number
    sl: number
    tp: number
    strategy: string
    leverage?: number
    ai_analysis?: any
}

// CRITICAL FIX: Dynamic price formatting based on value
const formatPrice = (price: number): string => {
    if (price === 0) return '$0.00'

    // For very small prices (< $0.01), use up to 6 decimals
    if (Math.abs(price) < 0.01) {
        return `$${price.toFixed(6).replace(/\.?0+$/, '')}`
    }
    // For small prices (< $1), use 4 decimals
    else if (Math.abs(price) < 1) {
        return `$${price.toFixed(4)}`
    }
    // For medium prices (< $100), use 3 decimals
    else if (Math.abs(price) < 100) {
        return `$${price.toFixed(3)}`
    }
    // For large prices, use 2 decimals
    else {
        return `$${price.toFixed(2)}`
    }
}

export default function ActiveTrade() {
    const [trade, setTrade] = useState<Trade | null>(null)
    const [currentPrice, setCurrentPrice] = useState<number>(0)

    useEffect(() => {
        const fetchData = async () => {
            try {
                // Fetch active trade
                const tradeResponse = await axios.get(`${API_URL}/api/active_trade`)
                setTrade(tradeResponse.data.active_trade)

                // Fetch current price
                const marketResponse = await axios.get(`${API_URL}/api/market/data`)
                setCurrentPrice(marketResponse.data.price)
            } catch (error) {
                console.error('Failed to fetch trade data:', error)
            }
        }

        fetchData()
        const interval = setInterval(fetchData, 2000)

        return () => clearInterval(interval)
    }, [])

    const closeTrade = async () => {
        try {
            await axios.post(`${API_URL}/api/close_trade`)
            setTrade(null)
        } catch (error) {
            console.error('Failed to close trade:', error)
        }
    }

    if (!trade) {
        return (
            <div className="bg-surface/50 backdrop-blur border border-border/30 rounded-2xl p-6">
                <h3 className="text-lg font-semibold mb-4">💼 Active Trade</h3>
                <div className="text-center py-12">
                    <div className="text-4xl mb-3">📊</div>
                    <div className="text-gray-400">No active trade</div>
                    <div className="text-sm text-gray-500 mt-2">
                        Waiting for signal from strategies
                    </div>
                </div>
            </div>
        )
    }

    const pnl = trade.side === 'BUY'
        ? currentPrice - trade.entry
        : trade.entry - currentPrice
    const pnlPercent = (pnl / trade.entry) * 100
    const isProfitable = pnl > 0

    const distanceToSL = Math.abs(currentPrice - trade.sl)
    const distanceToTP = Math.abs(currentPrice - trade.tp)
    const totalDistance = Math.abs(trade.tp - trade.sl)
    const progressPercent = ((currentPrice - trade.sl) / totalDistance) * 100

    return (
        <div className="bg-surface/50 backdrop-blur border border-border/30 rounded-2xl p-6">
            <div className="flex items-center justify-between mb-6">
                <h3 className="text-lg font-semibold">💼 Active Trade</h3>
                <button
                    onClick={closeTrade}
                    className="px-4 py-2 bg-error/20 hover:bg-error/30 text-error border border-error/30 rounded-lg text-sm font-semibold transition-all"
                >
                    Close Trade
                </button>
            </div>

            <div className="space-y-4">
                {/* Trade Header */}
                <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                        <div className={`w-12 h-12 rounded-full flex items-center justify-center ${trade.side === 'BUY' ? 'bg-success/20 text-success' : 'bg-error/20 text-error'
                            }`}>
                            {trade.side === 'BUY' ? '📈' : '📉'}
                        </div>
                        <div>
                            <div className="text-xl font-bold">{trade.side} {trade.symbol}</div>
                            <div className="text-sm text-gray-400">{trade.strategy}</div>
                        </div>
                    </div>
                    <div className="text-right">
                        <div className={`text-2xl font-bold ${isProfitable ? 'text-success' : 'text-error'}`}>
                            {isProfitable ? '+' : ''}{formatPrice(pnl).replace('$', '')}
                        </div>
                        <div className={`text-sm ${isProfitable ? 'text-success' : 'text-error'}`}>
                            {isProfitable ? '+' : ''}{pnlPercent.toFixed(2)}%
                        </div>
                    </div>
                </div>

                {/* Price Levels */}
                <div className="grid grid-cols-3 gap-4">
                    <div className="bg-background/50 rounded-lg p-3 border border-border/20">
                        <div className="text-xs text-gray-400 mb-1">Entry</div>
                        <div className="text-lg font-semibold">{formatPrice(trade.entry)}</div>
                    </div>
                    <div className="bg-background/50 rounded-lg p-3 border border-border/20">
                        <div className="text-xs text-gray-400 mb-1">Current</div>
                        <div className="text-lg font-semibold">{formatPrice(currentPrice)}</div>
                    </div>
                    <div className="bg-background/50 rounded-lg p-3 border border-success/20">
                        <div className="text-xs text-success mb-1">Take Profit</div>
                        <div className="text-lg font-semibold text-success">{formatPrice(trade.tp)}</div>
                    </div>
                </div>

                {/* Progress Bar */}
                <div className="space-y-2">
                    <div className="flex justify-between text-xs text-gray-400">
                        <span>SL: {formatPrice(trade.sl)}</span>
                        <span>TP: {formatPrice(trade.tp)}</span>
                    </div>
                    <div className="w-full bg-background/50 rounded-full h-3 overflow-hidden">
                        <div
                            className={`h-full transition-all ${isProfitable ? 'bg-success' : 'bg-error'}`}
                            style={{ width: `${Math.max(0, Math.min(100, progressPercent))}%` }}
                        />
                    </div>
                </div>

                {/* Stats */}
                <div className="grid grid-cols-3 gap-4 pt-4 border-t border-border/20">
                    <div>
                        <div className="text-xs text-gray-400">Distance to SL</div>
                        <div className="text-sm font-semibold">{formatPrice(distanceToSL)}</div>
                    </div>
                    <div>
                        <div className="text-xs text-gray-400">Distance to TP</div>
                        <div className="text-sm font-semibold">{formatPrice(distanceToTP)}</div>
                    </div>
                    <div>
                        <div className="text-xs text-gray-400">Leverage</div>
                        <div className="text-sm font-semibold text-primary">{trade.leverage ? `${trade.leverage}x` : '1x'}</div>
                    </div>
                </div>

                {/* AI Analysis Section */}
                {trade.ai_analysis && (
                    <div className="mt-4 pt-4 border-t border-border/20">
                        <div className="flex items-center justify-between mb-3">
                            <div className="flex items-center gap-2">
                                <span className="text-xl">🤖</span>
                                <h4 className="text-sm font-bold text-gray-200">AI Position Analysis</h4>
                            </div>
                            {trade.ai_analysis.risk_level && (
                                <span className={`px-2 py-1 rounded text-[10px] font-bold border ${trade.ai_analysis.risk_level === 'HIGH' || trade.ai_analysis.risk_level === 'CRITICAL' ? 'bg-red-500/20 text-red-400 border-red-500/30' :
                                        trade.ai_analysis.risk_level === 'MEDIUM' ? 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30' :
                                            'bg-green-500/20 text-green-400 border-green-500/30'
                                    }`}>
                                    RISK: {trade.ai_analysis.risk_level}
                                </span>
                            )}
                        </div>

                        <div className="bg-black/20 rounded-lg p-4 space-y-3">
                            {/* Reasoning */}
                            <p className="text-gray-300 text-xs leading-relaxed italic border-l-2 border-primary/50 pl-3">
                                "{trade.ai_analysis.reasoning || trade.ai_analysis.explanation}"
                            </p>

                            {/* Recommendations */}
                            {trade.ai_analysis.recommendations && Array.isArray(trade.ai_analysis.recommendations) && (
                                <div className="space-y-1">
                                    <p className="text-[10px] text-gray-500 font-bold uppercase tracking-wider">Recommendations</p>
                                    <ul className="space-y-1">
                                        {trade.ai_analysis.recommendations.map((rec: string, idx: number) => (
                                            <li key={idx} className="text-xs text-gray-400 flex items-start gap-2">
                                                <span className="text-primary mt-0.5">•</span>
                                                <span>{rec}</span>
                                            </li>
                                        ))}
                                    </ul>
                                </div>
                            )}

                            {/* Action */}
                            <div className="flex items-center justify-between bg-black/30 rounded p-2 mt-2">
                                <span className="text-gray-500 text-xs">Suggested Action:</span>
                                <span className={`font-bold text-sm ${trade.ai_analysis.actions === 'CLOSE' ? 'text-red-400' :
                                        trade.ai_analysis.actions === 'HOLD' ? 'text-blue-400' : 'text-gray-300'
                                    }`}>
                                    {trade.ai_analysis.actions || trade.ai_analysis.recommendations}
                                </span>
                            </div>
                        </div>
                    </div>
                )}
            </div>
        </div>
    )
}
