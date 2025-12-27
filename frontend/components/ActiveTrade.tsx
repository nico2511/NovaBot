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
                            {isProfitable ? '+' : ''}{pnl.toFixed(2)}
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
                        <div className="text-lg font-semibold">${trade.entry.toFixed(2)}</div>
                    </div>
                    <div className="bg-background/50 rounded-lg p-3 border border-border/20">
                        <div className="text-xs text-gray-400 mb-1">Current</div>
                        <div className="text-lg font-semibold">${currentPrice.toFixed(2)}</div>
                    </div>
                    <div className="bg-background/50 rounded-lg p-3 border border-success/20">
                        <div className="text-xs text-success mb-1">Take Profit</div>
                        <div className="text-lg font-semibold text-success">${trade.tp.toFixed(2)}</div>
                    </div>
                </div>

                {/* Progress Bar */}
                <div className="space-y-2">
                    <div className="flex justify-between text-xs text-gray-400">
                        <span>SL: ${trade.sl.toFixed(2)}</span>
                        <span>TP: ${trade.tp.toFixed(2)}</span>
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
                        <div className="text-sm font-semibold">${distanceToSL.toFixed(2)}</div>
                    </div>
                    <div>
                        <div className="text-xs text-gray-400">Distance to TP</div>
                        <div className="text-sm font-semibold">${distanceToTP.toFixed(2)}</div>
                    </div>
                    <div>
                        <div className="text-xs text-gray-400">Leverage</div>
                        <div className="text-sm font-semibold text-primary">{trade.leverage ? `${trade.leverage}x` : '1x'}</div>
                    </div>
                </div>
            </div>
        </div>
    )
}
