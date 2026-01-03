'use client'

import { useState, useEffect } from 'react'
import { createPortal } from 'react-dom'
import axios from 'axios'

interface CryptoWeatherProps {
    regime: string
    adx: number
    trend?: string
    rsi?: number
    ema_20?: number
    ema_50?: number
    atr?: number
    symbol?: string
}

export default function CryptoWeather({ regime, adx, trend, rsi, ema_20, ema_50, atr, symbol = 'BTC' }: CryptoWeatherProps) {
    let weatherIcon = '☁️' // Cloudy (Range)
    let weatherText = 'Overcast (Range)'
    let color = 'text-gray-400'

    if (regime === 'TREND') {
        if (adx > 40) {
            weatherIcon = '🌪️' // Stormy/Strong Trend
            weatherText = 'Turbulent (Strong Trend)'
            color = 'text-yellow-400'
        } else {
            weatherIcon = '☀️' // Sunny
            weatherText = 'Clear Skies (Trending)'
            color = 'text-yellow-500'
        }
    } else if (regime === 'RANGE') {
        if (adx < 15) {
            weatherIcon = '🌫️' // Foggy
            weatherText = 'Foggy (Low Volatility)'
            color = 'text-blue-300'
        }
    }


    const [isAnalyzing, setIsAnalyzing] = useState(false)
    const [aiReport, setAiReport] = useState<any>(null)
    const [showModal, setShowModal] = useState(false)
    const [mounted, setMounted] = useState(false)

    // Scanner V2 metrics
    const [rvol, setRvol] = useState<number | null>(null)
    const [trendAligned, setTrendAligned] = useState<boolean | null>(null)

    useEffect(() => {
        setMounted(true)

        // Fetch Scanner V2 metrics
        const fetchMetrics = async () => {
            try {
                const res = await axios.get(`/api/market_metrics?symbol=${symbol}`)
                if (res.data && !res.data.error) {
                    setRvol(res.data.rvol)
                    setTrendAligned(res.data.trend_aligned)
                }
            } catch (e) {
                console.error('Failed to fetch market metrics:', e)
            }
        }

        fetchMetrics()

        // Refresh every 30 seconds
        const interval = setInterval(fetchMetrics, 30000)
        return () => clearInterval(interval)
    }, [symbol])

    const handleAskAi = async () => {
        setIsAnalyzing(true)
        setAiReport(null)
        setShowModal(true)
        try {
            const res = await axios.post('/api/ai_analysis', { symbol })
            if (res.data) {
                // Parse if string
                let data = res.data
                if (data.raw_output) {
                    try {
                        data = JSON.parse(data.raw_output)
                    } catch (e) {
                        // raw_output might be just text if json parse fails
                    }
                }
                setAiReport(data)
            }
        } catch (e) {
            console.error(e)
            setAiReport({ error: "Failed to fetch analysis" })
        } finally {
            setIsAnalyzing(false)
        }
    }

    return (
        <>
            {/* Météo Container - Responsive Mobile */}
            <div className="bg-gradient-to-br from-blue-900/30 to-surface border border-white/10 rounded-xl p-3 shadow-xl backdrop-blur-md relative">
                {/* Container avec flex-wrap pour mobile */}
                <div className="flex flex-wrap items-center gap-3 lg:gap-6">

                    {/* Weather Icon & Main Status - INDÉPENDANT DE L'IA */}
                    <div className="flex items-center gap-3 border-r border-white/10 pr-3 lg:pr-6">
                        <div className="text-3xl lg:text-4xl filter drop-shadow-lg animate-pulse-slow">
                            {weatherIcon}
                        </div>
                        <div>
                            <h3 className="text-[9px] lg:text-[10px] font-bold text-gray-400 uppercase tracking-wider">Market Weather</h3>
                            <div className={`text-xs lg:text-sm font-bold ${color} leading-tight`}>
                                {weatherText}
                            </div>
                        </div>
                    </div>

                    {/* Metrics Grid - Responsive */}
                    <div className="flex flex-wrap items-center gap-3 lg:gap-6 text-xs flex-1">
                        {/* RSI */}
                        <div className="text-center min-w-[50px]">
                            <div className="text-gray-500 mb-0.5 text-[10px]">RSI</div>
                            <div className={`font-mono font-bold text-xs ${rsi && rsi < 30 ? 'text-success' : rsi && rsi > 70 ? 'text-error' : 'text-gray-300'}`}>
                                {rsi?.toFixed(0) || '--'}
                            </div>
                        </div>

                        {/* ADX */}
                        <div className="text-center min-w-[50px]">
                            <div className="text-gray-500 mb-0.5 text-[10px]">ADX</div>
                            <div className="font-mono font-bold text-xs text-gray-300">
                                {adx?.toFixed(0) || '--'}
                            </div>
                        </div>

                        {/* EMAs - Hidden on very small screens */}
                        <div className="hidden sm:block text-center border-l border-white/10 pl-3 lg:pl-6 min-w-[100px]">
                            <div className="text-gray-500 mb-0.5 text-[10px]">EMA 20/50</div>
                            <div className="font-mono font-bold text-xs">
                                <span className="text-blue-400">
                                    {ema_20 ? (ema_20 < 10 ? ema_20.toFixed(4) : ema_20.toFixed(0)) : '-'}
                                </span>
                                <span className="text-gray-600 mx-1">/</span>
                                <span className="text-purple-400">
                                    {ema_50 ? (ema_50 < 10 ? ema_50.toFixed(4) : ema_50.toFixed(0)) : '-'}
                                </span>
                            </div>
                        </div>

                        {/* ATR */}
                        <div className="text-center min-w-[50px]">
                            <div className="text-gray-500 mb-0.5 text-[10px]">ATR</div>
                            <div className="font-mono font-bold text-xs text-gray-300">
                                {atr ? (atr < 1 ? atr.toFixed(4) : atr.toFixed(2)) : '--'}
                            </div>
                        </div>

                        {/* Scanner V2 Metrics - Hidden on small screens */}
                        <div className="hidden md:block text-center border-l border-white/10 pl-3 lg:pl-6 min-w-[60px]">
                            <div className="text-gray-500 mb-0.5 text-[10px]">RVol</div>
                            <div className={`font-mono font-bold text-xs ${rvol && rvol > 1.5 ? 'text-yellow-400' : 'text-gray-400'}`}>
                                {rvol ? rvol.toFixed(1) + 'x' : '--'}
                            </div>
                        </div>

                        <div className="hidden lg:block text-center min-w-[70px]">
                            <div className="text-gray-500 mb-0.5 text-[10px]">Trend</div>
                            <div className={`font-mono font-bold text-xs ${trendAligned ? 'text-green-400' : 'text-red-400'}`}>
                                {trendAligned === null ? '--' : trendAligned ? '✓ Aligned' : '✗ Choppy'}
                            </div>
                        </div>
                    </div>

                    {/* AI Button - Always visible */}
                    <button
                        onClick={handleAskAi}
                        className="flex items-center gap-2 bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-500 hover:to-indigo-500 text-white px-3 py-1.5 rounded-lg text-xs font-bold shadow-lg transition-transform active:scale-95 whitespace-nowrap"
                    >
                        ✨ <span className="hidden sm:inline">Ask AI</span>
                    </button>
                </div>
            </div>

            {/* AI Modal */}
            {showModal && mounted && createPortal(
                <div className="fixed inset-0 z-[9999] flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm">
                    <div className="bg-gray-900 border border-purple-500/30 w-full max-w-lg rounded-2xl shadow-2xl overflow-hidden animate-in fade-in zoom-in-95 duration-200 relative">
                        {/* Header */}
                        <div className="bg-gradient-to-r from-purple-900/50 to-indigo-900/50 p-4 flex items-center justify-between border-b border-white/10">
                            <div className="flex items-center gap-2">
                                <span className="text-2xl">✨</span>
                                <h3 className="font-bold text-lg text-white">AI Market Analysis</h3>
                            </div>
                            <button onClick={() => setShowModal(false)} className="text-gray-400 hover:text-white transition-colors">✕</button>
                        </div>

                        {/* Content */}
                        <div className="p-6">
                            {isAnalyzing ? (
                                <div className="flex flex-col items-center justify-center py-8 gap-4">
                                    <div className="w-12 h-12 border-4 border-purple-500 border-t-transparent rounded-full animate-spin"></div>
                                    <p className="text-purple-300 animate-pulse">Analyzing market structure...</p>
                                </div>
                            ) : aiReport ? (
                                <div className="space-y-4">
                                    {aiReport.error ? (
                                        <div className="bg-red-500/20 border border-red-500/50 p-4 rounded-xl text-red-200 text-center">
                                            <p className="font-bold">Analysis Failed</p>
                                            <p className="text-sm mt-2">{aiReport.error}</p>
                                            {aiReport.details && <p className="text-xs mt-2 text-red-300 overflow-auto max-h-20">{JSON.stringify(aiReport.details)}</p>}
                                        </div>
                                    ) : (
                                        <>
                                            <div className="flex items-center gap-4 mb-4">
                                                <div className={`px-3 py-1 rounded-full text-xs font-bold border ${aiReport.risk_level === 'HIGH' ? 'bg-red-500/20 text-red-400 border-red-500/50' :
                                                    aiReport.risk_level === 'MEDIUM' ? 'bg-yellow-500/20 text-yellow-400 border-yellow-500/50' :
                                                        'bg-green-500/20 text-green-400 border-green-500/50'
                                                    }`}>
                                                    RISK: {aiReport.risk_level}
                                                </div>
                                                <div className="px-3 py-1 rounded-full text-xs font-bold bg-blue-500/20 text-blue-400 border border-blue-500/50">
                                                    TREND: {aiReport.trend}
                                                </div>
                                            </div>

                                            <div className="bg-black/20 p-4 rounded-xl border border-white/5">
                                                <p className="text-gray-200 leading-relaxed text-sm">
                                                    {aiReport.summary || aiReport.raw_output}
                                                </p>
                                            </div>

                                            {aiReport.reasoning && (
                                                <div>
                                                    <h4 className="text-xs font-bold text-gray-500 uppercase mb-2">Key Factors</h4>
                                                    <ul className="space-y-2">
                                                        {aiReport.reasoning.map((r: string, i: number) => (
                                                            <li key={i} className="flex gap-2 text-sm text-gray-400">
                                                                <span className="text-purple-400">•</span>
                                                                {r}
                                                            </li>
                                                        ))}
                                                    </ul>
                                                </div>
                                            )}
                                        </>
                                    )}
                                </div>
                            ) : (
                                <p className="text-red-400 text-center">Failed to load analysis.</p>
                            )}
                        </div>
                    </div>
                </div>

                , document.body)
            }
        </>
    )

}
