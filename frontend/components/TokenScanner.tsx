'use client'
import { useState } from 'react'
import axios from 'axios'
import useSWR from 'swr'

// Custom fetcher with error handling
const fetcher = async (url: string) => {
    try {
        const res = await fetch(url)
        if (!res.ok) throw new Error(`HTTP ${res.status}`)
        const text = await res.text()
        try {
            return JSON.parse(text)
        } catch (e) {
            console.error("Invalid JSON response:", text.substring(0, 100))
            throw new Error("Invalid Server Response (Not JSON)")
        }
    } catch (e) {
        throw e
    }
}

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
    dist_ma200_pct?: number // New field
}

export default function TokenScanner({ hideHeader = false }: { hideHeader?: boolean }) {
    // ... (rest of component unchanged until Metrics)

                                <div className="bg-background/50 rounded-lg p-3">
                                    <div className="text-xs text-gray-400 mb-1">RSI</div>
                                    <div className="text-sm font-bold text-white">
                                        {opp.rsi.toFixed(0)}
                                    </div>
                                </div>

                                <div className="bg-background/50 rounded-lg p-3">
                                    <div className="text-xs text-gray-400 mb-1">Trend (vs MA200)</div>
                                    <div className="flex flex-col">
                                        <span className={`text-sm font-bold ${getTrendColor(opp.trend)}`}>
                                            {opp.trend}
                                        </span>
                                        {opp.dist_ma200_pct !== undefined && (
                                            <span className={`text-[10px] ${opp.dist_ma200_pct > 0 ? 'text-green-400' : 'text-red-400'}`}>
                                                {opp.dist_ma200_pct > 0 ? '+' : ''}{opp.dist_ma200_pct.toFixed(1)}%
                                            </span>
                                        )}
                                    </div>
                                </div>
                            </div >
    const [isScanning, setIsScanning] = useState(false)
    const [isMomentumScanning, setIsMomentumScanning] = useState(false)
    const [momentumResults, setMomentumResults] = useState<any>(null)
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

                    <button
                        onClick={async () => {
                            setIsMomentumScanning(true)
                            try {
                                const res = await axios.post('/api/momentum_ranking', { top_n: 3 })
                                setMomentumResults(res.data.ranking)
                            } catch (error) {
                                console.error('Momentum scan failed:', error)
                            }
                            setIsMomentumScanning(false)
                        }}
                        disabled={isMomentumScanning}
                        className="bg-amber-500/20 hover:bg-amber-500/30 disabled:bg-amber-500/10 text-amber-300 border border-amber-500/30 px-4 py-1.5 rounded-lg text-sm font-medium transition-all shadow-lg"
                    >
                        {isMomentumScanning ? '🔄 Ranking...' : '🎯 Momentum Ranking'}
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

            {/* Momentum Ranking Results */}
            {momentumResults && momentumResults.selected && momentumResults.selected.length > 0 && (
                <div className="bg-gradient-to-br from-amber-500/10 to-orange-500/5 border border-amber-500/30 rounded-xl p-6">
                    <div className="flex items-center gap-2 mb-4">
                        <span className="text-2xl">🎯</span>
                        <h3 className="text-lg font-bold text-amber-300">Momentum Ranking (Top 3)</h3>
                        <span className="text-xs text-gray-400 ml-auto">Cross-Sectional • 30d ROC + Regression</span>
                    </div>

                    <div className="grid grid-cols-3 gap-4">
                        {momentumResults.selected.map((symbol: string, idx: number) => (
                            <div key={symbol} className="bg-black/30 rounded-lg p-4 border border-amber-500/20">
                                <div className="text-center">
                                    <div className="text-3xl font-bold text-white mb-1">#{idx + 1}</div>
                                    <div className="text-xl font-bold text-amber-300 mb-2">{symbol}</div>
                                    <div className="text-sm text-gray-400 mb-1">Score: {momentumResults.scores[symbol]?.toFixed(4)}</div>
                                    <div className="text-xs text-gray-500">Weight: {(momentumResults.weights[symbol] * 100).toFixed(0)}%</div>
                                </div>
                            </div>
                        ))}
                    </div>

                    <div className="mt-4 text-xs text-gray-400 text-center">
                        💡 These tokens have the strongest momentum over the last 30 days with confirmed uptrend (MA200 filter)
                    </div>
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
                                        ${opp.current_price < 0.01 ? opp.current_price.toFixed(8) : opp.current_price.toFixed(4)}
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
