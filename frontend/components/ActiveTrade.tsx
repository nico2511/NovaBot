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
const formatPrice = (inputPrice: number | string | undefined | null): string => {
    const price = Number(inputPrice)
    if (inputPrice === undefined || inputPrice === null || isNaN(price) || price === 0) return '$0.00'

    // For very small prices (< $0.01), use up to 8 decimals
    if (Math.abs(price) < 0.01) {
        return `$${price.toFixed(8).replace(/\.?0+$/, '')}`
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

// ... imports

export default function ActiveTrade({ embedded = false }: { embedded?: boolean }) {
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

    // CRITICAL: Don't render if no active trade
    if (!trade) {
        return null
    }

    const closeTrade = async () => {
        try {
            await axios.post(`${API_URL}/api/close_trade`)
            setTrade(null)
        } catch (error) {
            console.error('Failed to close trade:', error)
        }
    }

    if (!trade) {
        if (embedded) {
            return (
                <div className="h-full flex flex-col items-center justify-center text-gray-400">
                    <div className="text-4xl mb-3 opacity-50">📊</div>
                    <div>No active trade</div>
                    <div className="text-xs text-gray-500 mt-2">Waiting for signal</div>
                </div>
            )
        }
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

    // Progress Calculation (0% at Entry, 100% at TP)
    let progressPercent = 0
    const totalMove = Math.abs(trade.tp - trade.entry)
    const currentMove = Math.abs(currentPrice - trade.entry)

    if (trade.side === 'BUY') {
        if (currentPrice > trade.entry) {
            progressPercent = Math.min((currentMove / totalMove) * 100, 100)
        }
    } else {
        if (currentPrice < trade.entry) {
            progressPercent = Math.min((currentMove / totalMove) * 100, 100)
        }
    }

    // Dynamic Background Gradient based on PnL %
    // Shifts from neutral to Green/Red as PnL increases
    // Dynamic Background Gradient based on PnL %
    // Shifts from neutral to Green/Red as PnL increases
    // Base opacity 0.2 (20%) + dynamic part up to 0.4 (40%)
    const opacity = 0.2 + Math.min(Math.abs(pnlPercent) / 10, 0.4)

    // Use stronger colors for the gradient
    const bgStyle = isProfitable
        ? `linear-gradient(135deg, rgba(6, 95, 70, ${opacity}) 0%, rgba(6, 78, 59, 0.2) 100%)` // Emerald-900ish
        : `linear-gradient(135deg, rgba(127, 29, 29, ${opacity}) 0%, rgba(69, 10, 10, 0.2) 100%)` // Red-900ish

    if (embedded) {
        return (
            <div className={`w-full flex flex-col justify-between rounded-xl overflow-hidden relative border ${isProfitable ? 'border-emerald-500/30 shadow-[0_0_15px_rgba(16,185,129,0.1)]' : 'border-red-500/30 shadow-[0_0_15px_rgba(239,68,68,0.1)]'}`}
                style={{ background: bgStyle }}>

                {/* Header */}
                <div className="relative z-10 p-4 pb-2">
                    <div className="flex justify-between items-start mb-1">
                        <div className="flex items-center gap-3">
                            <div className={`w-9 h-9 rounded-lg flex items-center justify-center text-xl shadow-lg border border-white/10 ${trade.side === 'BUY' ? 'bg-emerald-500/20 text-emerald-400' : 'bg-red-500/20 text-red-400'}`}>
                                {trade.side === 'BUY' ? '📈' : '📉'}
                            </div>
                            <div>
                                <h3 className="font-bold text-white text-base leading-none mb-1">
                                    {trade.side} {trade.symbol}
                                </h3>
                                <div className="flex items-center gap-2">
                                    <span className="text-[10px] text-gray-400 font-bold bg-black/20 px-1.5 py-0.5 rounded uppercase tracking-wider">{trade.strategy}</span>
                                </div>
                            </div>
                        </div>

                        <div className="text-right">
                            <div className={`text-[10px] uppercase font-bold tracking-wider mb-0.5 ${isProfitable ? 'text-emerald-400/80' : 'text-red-400/80'}`}>Current PnL</div>
                            <div className={`font-black text-xl leading-none mb-0.5 ${isProfitable ? 'text-emerald-300 drop-shadow-[0_2px_4px_rgba(0,0,0,0.5)]' : 'text-red-300 drop-shadow-[0_2px_4px_rgba(0,0,0,0.5)]'}`}>
                                {isProfitable ? '+' : ''}{formatPrice(pnl).replace('$', '')}
                            </div>
                            <div className={`text-xs font-bold ${isProfitable ? 'text-emerald-500' : 'text-red-500'}`}>
                                {pnlPercent.toFixed(2)}%
                            </div>
                        </div>
                    </div>
                </div>

                {/* Quest Progress Section */}
                <div className="relative z-10 px-4 flex-1 flex flex-col justify-center">
                    <div className="flex justify-between text-[10px] text-gray-400 font-bold uppercase tracking-wider mb-2 opacity-90">
                        <span>ENTRY: {formatPrice(trade.entry)}</span>
                        <span>TP: {formatPrice(trade.tp)}</span>
                    </div>

                    {/* Thicker Bar with Glass Effect */}
                    <div className="w-full bg-black/40 rounded-full h-5 overflow-hidden border border-white/10 relative shadow-inner backdrop-blur-sm">
                        {/* Markers */}
                        <div className="absolute left-0 top-0 bottom-0 w-px bg-white/20 z-20"></div>
                        <div className="absolute right-0 top-0 bottom-0 w-px bg-white/20 z-20"></div>

                        {/* The Bar */}
                        <div
                            className={`h-full transition-all duration-700 ease-out shadow-[0_0_15px_rgba(0,0,0,0.3)] relative overflow-hidden ${isProfitable ? 'bg-gradient-to-r from-emerald-500 to-teal-400' : 'bg-gradient-to-r from-red-600 to-orange-500'
                                }`}
                            style={{ width: `${Math.max(5, progressPercent)}%` }}
                        >
                            {/* Shine animation */}
                            <div className="absolute top-0 right-0 bottom-0 w-full h-full bg-gradient-to-b from-white/20 to-transparent"></div>
                            <div className="absolute top-0 right-0 bottom-0 w-10 bg-gradient-to-r from-transparent to-white/30 transform skew-x-[-20deg] animate-pulse"></div>
                        </div>
                        {/* Centered % */}
                        <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
                            <span className="text-[10px] font-bold text-white drop-shadow-md">{progressPercent.toFixed(0)}% Completed</span>
                        </div>
                    </div>

                    <div className="flex justify-between text-[10px] font-medium mt-2">
                        <div className="flex items-center gap-1 text-red-400/80">
                            <span>SL: {formatPrice(trade.sl)}</span>
                        </div>
                        <div className={`flex items-center gap-1 ${isProfitable ? 'text-emerald-400' : 'text-gray-400'}`}>
                            <span>Target Reward</span>
                        </div>
                    </div>
                </div>

                {/* Close Button Area */}
                <div className="p-3 bg-black/20 border-t border-white/5 mt-auto">
                    <button
                        onClick={closeTrade}
                        className="w-full py-2.5 bg-white/5 hover:bg-white/10 active:bg-white/15 border border-white/10 rounded-lg text-xs font-bold text-gray-300 transition-all uppercase tracking-wide hover:shadow-lg flex items-center justify-center gap-2 group"
                    >
                        <span>Close Position</span>
                        <span className="group-hover:translate-x-1 transition-transform">→</span>
                    </button>
                </div>
            </div>
        )
    }

    // Full View (Standard)
    return (
        <div className="bg-surface/50 backdrop-blur border border-border/30 rounded-2xl p-6 relative overflow-hidden"
            style={{ backgroundImage: bgStyle }}>

            <div className="relative z-10">
                <div className="flex items-center justify-between mb-6">
                    <h3 className="text-lg font-semibold flex items-center gap-2">
                        💼 Active Trade
                        <span className="text-xs font-normal text-gray-500 px-2 py-0.5 bg-white/5 rounded-full">{trade.strategy}</span>
                    </h3>
                    <button
                        onClick={closeTrade}
                        className="px-4 py-2 bg-error/20 hover:bg-error/30 text-error border border-error/30 rounded-lg text-sm font-semibold transition-all shadow-lg hover:shadow-error/20"
                    >
                        Close Trade
                    </button>
                </div>

                {/* Main Stats Quest Card */}
                <div className="bg-black/40 rounded-xl p-5 border border-white/5 backdrop-blur-md shadow-inner">
                    <div className="flex justify-between items-center mb-6">
                        <div className="flex items-center gap-4">
                            <div className={`w-14 h-14 rounded-2xl flex items-center justify-center text-3xl shadow-lg border border-white/10 ${trade.side === 'BUY' ? 'bg-gradient-to-br from-emerald-900 to-emerald-700' : 'bg-gradient-to-br from-red-900 to-red-700'}`}>
                                {trade.side === 'BUY' ? '🐂' : '🐻'}
                            </div>
                            <div>
                                <h2 className="text-2xl font-bold text-white tracking-tight">{trade.symbol} <span className="text-lg font-medium text-gray-400">{trade.side}</span></h2>
                                <div className="flex items-center gap-2 text-sm text-gray-400">
                                    <span className="bg-white/10 px-1.5 py-0.5 rounded text-xs">x{trade.leverage || 1}</span>
                                    <span>Entry: {formatPrice(trade.entry)}</span>
                                </div>
                            </div>
                        </div>

                        <div className="text-right">
                            <div className={`text-3xl font-bold tracking-tighter filter drop-shadow-md ${isProfitable ? 'text-transparent bg-clip-text bg-gradient-to-r from-emerald-400 to-teal-300' : 'text-red-400'}`}>
                                {isProfitable ? '+' : ''}{formatPrice(pnl).replace('$', '')}
                            </div>
                            <div className={`text-sm font-medium ${isProfitable ? 'text-emerald-500' : 'text-red-500'}`}>
                                {isProfitable ? '+' : ''}{pnlPercent.toFixed(2)}%
                            </div>
                        </div>
                    </div>

                    {/* Quest Progress Bar Large */}
                    <div className="space-y-2 mb-2">
                        <div className="flex justify-between text-xs font-bold text-gray-400 uppercase tracking-widest">
                            <span>Start</span>
                            <span>Target (+{formatPrice(Math.abs(trade.tp - trade.entry)).replace('$', '')})</span>
                        </div>
                        <div className="w-full bg-gray-900 rounded-full h-6 overflow-hidden border border-white/10 relative shadow-inner">
                            {/* Markers */}
                            <div className="absolute left-0 top-0 bottom-0 w-px bg-white/20 z-20"></div>

                            {/* The Bar */}
                            <div
                                className={`h-full transition-all duration-1000 ease-out relative ${isProfitable ? 'bg-gradient-to-r from-emerald-600 via-teal-500 to-emerald-400' : 'bg-gradient-to-r from-red-900 via-red-700 to-orange-700'
                                    }`}
                                style={{ width: `${Math.max(2, progressPercent)}%` }} // Min 2% visibility
                            >
                                {/* Shine effect */}
                                <div className="absolute top-0 right-0 bottom-0 w-8 bg-gradient-to-r from-transparent to-white/30 skew-x-[-20deg] animate-pulse"></div>
                            </div>
                        </div>
                        <div className="flex justify-between text-xs text-gray-500 font-mono">
                            <span>Current: {formatPrice(currentPrice)}</span>
                            <span className={isProfitable ? 'text-teal-400' : 'text-gray-500'}>Goal: {formatPrice(trade.tp)}</span>
                        </div>
                    </div>
                </div>

                {/* Secondary Info Grid */}
                <div className="grid grid-cols-2 gap-4 mt-4">
                    <div className="bg-black/20 rounded-lg p-3 border border-white/5 flex justify-between items-center">
                        <span className="text-sm text-gray-400">Stop Loss</span>
                        <span className="text-sm font-mono text-red-400 border border-red-500/30 bg-red-500/10 px-2 py-0.5 rounded">{formatPrice(trade.sl)}</span>
                    </div>
                    <div className="bg-black/20 rounded-lg p-3 border border-white/5 flex justify-between items-center">
                        <span className="text-sm text-gray-400">Take Profit</span>
                        <span className="text-sm font-mono text-emerald-400 border border-emerald-500/30 bg-emerald-500/10 px-2 py-0.5 rounded">{formatPrice(trade.tp)}</span>
                    </div>
                </div>

                {/* AI Analysis Section (Preserved) */}
                {trade.ai_analysis && (
                    <div className="mt-4 pt-4 border-t border-white/10">
                        {/* ... (Keep existing AI display or adapt slightly) ... */}
                        <div className="flex items-center justify-between mb-3">
                            <div className="flex items-center gap-2">
                                <span className="text-xl">🤖</span>
                                <h4 className="text-sm font-bold text-gray-200">AI Insight</h4>
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
                        <div className="bg-black/20 rounded-lg p-3 border border-indigo-500/20 shadow-[0_0_15px_rgba(99,102,241,0.1)]">
                            <p className="text-indigo-200/80 text-xs italic">
                                "{trade.ai_analysis.reasoning || trade.ai_analysis.explanation}"
                            </p>
                        </div>
                    </div>
                )}
            </div>
        </div>
    )
}
