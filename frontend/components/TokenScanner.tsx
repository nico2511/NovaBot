'use client'
import { useState } from 'react'
import axios from 'axios'
import useSWR from 'swr'

const fetcher = (url: string) => fetch(url).then(res => res.json())

interface Opportunity {
    symbol: string
    score: number
    volume_24h: number
    momentum_24h: number
    atr_pct: number
    rsi: number
    trend: string
    current_price: number
    reasons: string[]
}

export default function TokenScanner({ hideHeader = false }: { hideHeader?: boolean }) {
    const [isScanning, setIsScanning] = useState(false)
    const [topN, setTopN] = useState(10)

    // ... (rest of the state hooks)
    const { data, error, mutate } = useSWR<{
        success: boolean
        opportunities: Opportunity[]
    }>(
        isScanning ? `/api/scanner/opportunities?top_n=${topN}` : null,
        fetcher,
        {
            revalidateOnFocus: false,
            revalidateOnReconnect: false
        }
    )

    const handleScan = () => {
        setIsScanning(true)
        mutate()
    }

    const getStars = (score: number) => {
        if (score >= 80) return '⭐⭐⭐'
        if (score >= 60) return '⭐⭐'
        return '⭐'
    }

    const handleTrade = async (symbol: string) => {
        try {
            // Call switch endpoint
            await axios.post('/api/symbol/switch', { symbol })

            alert(`✅ Switched to ${symbol}! Go to Overview to trade.`)
            window.scrollTo({ top: 0, behavior: 'smooth' })
        } catch (error) {
            console.error('Failed to switch symbol:', error)
            alert('❌ Failed to switch symbol')
        }
    }

    const getTrendColor = (trend: string) => {
        return trend === 'UP' ? 'text-green-400' : trend === 'DOWN' ? 'text-red-400' : 'text-gray-400'
    }

    return (
        <div className="space-y-6">
            {/* Header */}
            <div className="flex items-center justify-between">
                <div>
                    {!hideHeader && (
                        <>
                            <h2 className="text-2xl font-bold text-white">🔍 Token Scanner</h2>
                            <p className="text-gray-400 text-sm mt-1">
                                Scan Hyperliquid for best trading opportunities
                            </p>
                        </>
                    )}
                </div>

                <div className="flex items-center gap-4">
                    <div className="flex items-center gap-2">
                        <label className="text-sm text-gray-400">Top</label>
                        <select
                            value={topN}
                            onChange={(e) => setTopN(Number(e.target.value))}
                            className="bg-surface border border-border/30 rounded-lg px-3 py-2 text-sm"
                        >
                            <option value={5}>5</option>
                            <option value={10}>10</option>
                            <option value={20}>20</option>
                        </select>
                    </div>

                    <button
                        onClick={handleScan}
                        disabled={isScanning && !data}
                        className="bg-primary hover:bg-primary/80 disabled:bg-primary/50 text-white px-4 py-1.5 rounded-lg text-sm font-medium transition-all shadow-lg shadow-primary/20"
                    >
                        {isScanning && !data ? '🔄 Scanning...' : '🚀 Scan Now'}
                    </button>
                </div>
            </div>

            {/* Results */}
            {error && (
                <div className="bg-red-500/10 border border-red-500/30 rounded-lg p-4">
                    <p className="text-red-400">❌ Error: {error.message}</p>
                </div>
            )}

            {isScanning && !data && (
                <div className="bg-surface/50 border border-border/30 rounded-lg p-8 text-center">
                    <div className="animate-spin text-4xl mb-4">🔄</div>
                    <p className="text-gray-400">Scanning {topN} best opportunities...</p>
                    <p className="text-sm text-gray-500 mt-2">This may take 30-60 seconds</p>
                </div>
            )}

            {data?.opportunities && (
                <div className="space-y-4">
                    <div className="text-sm text-gray-400">
                        Found {data.opportunities.length} opportunities
                    </div>

                    {data.opportunities.map((opp, index) => (
                        <div
                            key={opp.symbol}
                            className="bg-gradient-to-br from-surface/80 to-background/40 border border-border/30 rounded-xl p-6 hover:border-primary/50 transition-all"
                        >
                            {/* Header */}
                            <div className="flex items-start justify-between mb-4">
                                <div className="flex items-center gap-3">
                                    <div className="text-3xl font-bold text-white">
                                        {index + 1}.
                                    </div>
                                    <div>
                                        <div className="flex items-center gap-2">
                                            {/* Token Icon */}
                                            <img
                                                src={`https://oss.now.github.io/cryptocurrency-icons/32/color/${opp.symbol.toLowerCase()}.png`}
                                                alt={opp.symbol}
                                                className="w-8 h-8 rounded-full bg-white/10"
                                                onError={(e) => {
                                                    (e.target as HTMLImageElement).src = `https://ui-avatars.com/api/?name=${opp.symbol}&background=random&color=fff&size=32`;
                                                }}
                                            />
                                            <h3 className="text-xl font-bold text-white">
                                                {opp.symbol}
                                            </h3>
                                            <span className="text-2xl">{getStars(opp.score)}</span>
                                        </div>
                                        <p className="text-sm text-gray-400 pl-10">
                                            Score: {opp.score.toFixed(0)}/100
                                        </p>
                                    </div>
                                </div>

                                <div className="text-right">
                                    <div className="text-2xl font-bold text-white">
                                        ${opp.current_price.toFixed(4)}
                                    </div>
                                    <div className={`text-sm font-medium ${getTrendColor(opp.trend)}`}>
                                        {opp.momentum_24h > 0 ? '+' : ''}{opp.momentum_24h.toFixed(2)}%
                                    </div>
                                </div>
                            </div>

                            {/* Metrics */}
                            <div className="grid grid-cols-4 gap-4 mb-4">
                                <div className="bg-background/50 rounded-lg p-3">
                                    <div className="text-xs text-gray-400 mb-1">Volume 24h</div>
                                    <div className="text-sm font-bold text-white">
                                        ${(opp.volume_24h / 1e6).toFixed(1)}M
                                    </div>
                                </div>

                                <div className="bg-background/50 rounded-lg p-3">
                                    <div className="text-xs text-gray-400 mb-1">ATR</div>
                                    <div className="text-sm font-bold text-white">
                                        {opp.atr_pct.toFixed(2)}%
                                    </div>
                                </div>

                                <div className="bg-background/50 rounded-lg p-3">
                                    <div className="text-xs text-gray-400 mb-1">RSI</div>
                                    <div className="text-sm font-bold text-white">
                                        {opp.rsi.toFixed(0)}
                                    </div>
                                </div>

                                <div className="bg-background/50 rounded-lg p-3">
                                    <div className="text-xs text-gray-400 mb-1">Trend</div>
                                    <div className={`text-sm font-bold ${getTrendColor(opp.trend)}`}>
                                        {opp.trend}
                                    </div>
                                </div>
                            </div>

                            {/* Reasons and Action */}
                            <div className="flex items-end justify-between mt-4">
                                <div className="space-y-1 flex-1">
                                    {opp.reasons && opp.reasons.length > 0 && (
                                        <>
                                            <div className="text-xs text-gray-400 mb-2">✅ Why this is a good opportunity:</div>
                                            {opp.reasons.map((reason, i) => (
                                                <div key={i} className="text-sm text-gray-300 flex items-start gap-2">
                                                    <span className="text-primary">•</span>
                                                    <span>{reason}</span>
                                                </div>
                                            ))}
                                        </>
                                    )}
                                </div>

                                <button
                                    onClick={() => handleTrade(opp.symbol)}
                                    className="bg-primary hover:bg-primary/80 text-white px-6 py-2 rounded-lg font-bold shadow-lg shadow-primary/20 transition-all transform hover:scale-105 ml-6"
                                >
                                    🚀 Trade {opp.symbol}
                                </button>
                            </div>
                        </div>
                    ))}
                </div>
            )}
        </div>
    )
}
