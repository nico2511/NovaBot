'use client'

import { useState, useEffect } from 'react'
import { createPortal } from 'react-dom'
import axios from 'axios'
import { TrendingUp, TrendingDown, Minus, ArrowUp, ArrowDown, Zap } from 'lucide-react'

interface MarketCardProps {
    symbol?: string
    price?: number
    regime?: string
    rsi?: number
    adx?: number
    atr?: number
    volume_24h?: number
    open_interest?: number
    rvol?: number
    trend_aligned?: boolean
    trends?: {
        [key: string]: {
            adx: number
            trend: string
        }
    }
}

const TrendArrow = ({ trend, timeframe }: { trend: string, timeframe: string }) => {
    let color = 'text-gray-500'
    let Icon = Minus

    if (trend === 'BULLISH') {
        color = 'text-green-400'
        Icon = TrendingUp
    } else if (trend === 'BEARISH') {
        color = 'text-red-400'
        Icon = TrendingDown
    } else if (trend.includes('RANGING')) {
        color = 'text-blue-400'
        Icon = Minus
    }

    return (
        <div className="flex flex-col items-center gap-1">
            <div className={`p-2 rounded-lg bg-white/5 ${color}`}>
                <Icon size={16} />
            </div>
            <span className="text-[10px] font-mono text-gray-400 uppercase">{timeframe}</span>
        </div>
    )
}

const formatNumber = (num: number) => {
    if (num >= 1000000) return `$${(num / 1000000).toFixed(2)}M`
    if (num >= 1000) return `$${(num / 1000).toFixed(2)}K`
    return `$${num.toFixed(2)}`
}

export default function MarketCard({
    symbol = 'BTC',
    price = 0,
    regime = 'UNKNOWN',
    rsi = 50,
    adx = 0,
    atr = 0,
    volume_24h = 0,
    open_interest = 0,
    rvol = 0,
    trend_aligned = false,
    trends = {
        "15m": { trend: "NEUTRAL", adx: 0 },
        "1h": { trend: "NEUTRAL", adx: 0 },
        "4h": { trend: "NEUTRAL", adx: 0 },
        "1d": { trend: "NEUTRAL", adx: 0 }
    }
}: MarketCardProps) {

    const [isAnalyzing, setIsAnalyzing] = useState(false)
    const [aiReport, setAiReport] = useState<any>(null)
    const [showModal, setShowModal] = useState(false)
    const [mounted, setMounted] = useState(false)

    useEffect(() => {
        setMounted(true)
    }, [])

    const handleAskAi = async () => {
        setIsAnalyzing(true)
        setAiReport(null)
        setShowModal(true)
        try {
            const res = await axios.post('/api/ai_analysis', { symbol })
            if (res.data) {
                let data = res.data
                if (data.raw_output) {
                    try {
                        data = JSON.parse(data.raw_output)
                    } catch (e) { }
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
            <div className="bg-black/40 backdrop-blur border border-white/5 rounded-xl overflow-hidden shadow-2xl p-6 relative group">
                {/* Background Glow based on Regime AND Alignment */}
                <div className={`absolute -top-20 -right-20 w-40 h-40 rounded-full blur-[80px] opacity-20 transition-colors duration-1000 ${trend_aligned ? 'bg-purple-500' : regime === 'TREND' ? 'bg-green-500' : 'bg-blue-500'
                    }`}></div>

                <div className="flex flex-col md:flex-row items-stretch justify-between gap-6 relative z-10">

                    {/* LEFT: Asset Info & Price */}
                    <div className="flex flex-col justify-between min-w-[140px]">
                        <div>
                            <h2 className="text-2xl font-black text-transparent bg-clip-text bg-gradient-to-r from-white to-gray-400">
                                {symbol}
                            </h2>
                            <div className="flex items-center gap-2 mt-1">
                                <span className={`text-xs font-bold px-2 py-0.5 rounded-full border ${regime === 'TREND'
                                    ? 'bg-green-500/10 text-green-400 border-green-500/20'
                                    : 'bg-blue-500/10 text-blue-400 border-blue-500/20'
                                    }`}>
                                    {regime}
                                </span>
                                {trend_aligned && (
                                    <span className="text-[10px] font-bold px-1.5 py-0.5 rounded bg-purple-500/20 text-purple-300 border border-purple-500/30 flex items-center gap-1">
                                        <Zap size={8} /> ALIGNED
                                    </span>
                                )}
                            </div>
                        </div>
                        <div className="mt-4">
                            <div className="text-3xl font-mono font-bold text-white tracking-tighter">
                                ${price < 0.01
                                    ? price.toFixed(8).replace(/\.?0+$/, '')
                                    : price < 1
                                        ? price.toFixed(6).replace(/\.?0+$/, '')
                                        : price.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                            </div>
                        </div>
                    </div>

                    {/* CENTER: Trend Grid */}
                    <div className="flex-1 bg-white/[0.02] rounded-lg border border-white/5 p-4 flex justify-around items-center">
                        <TrendArrow timeframe="15M" trend={trends["15m"]?.trend} />
                        <div className="w-px h-8 bg-white/10"></div>
                        <TrendArrow timeframe="1H" trend={trends["1h"]?.trend} />
                        <div className="w-px h-8 bg-white/10"></div>
                        <TrendArrow timeframe="4H" trend={trends["4h"]?.trend} />
                        <div className="w-px h-8 bg-white/10"></div>
                        <TrendArrow timeframe="1D" trend={trends["1d"]?.trend} />
                    </div>

                    {/* RIGHT: Technical Health */}
                    <div className="flex flex-col gap-3 min-w-[180px]">
                        <div className="grid grid-cols-2 gap-2 text-xs">
                            <div className="bg-white/[0.02] p-2 rounded-lg border border-white/5">
                                <div className="text-gray-500 mb-1">RSI</div>
                                <div className={`font-mono font-bold ${rsi > 70 ? 'text-red-400' : rsi < 30 ? 'text-green-400' : 'text-gray-300'}`}>
                                    {rsi.toFixed(0)}
                                </div>
                            </div>
                            <div className="bg-white/[0.02] p-2 rounded-lg border border-white/5">
                                <div className="text-gray-500 mb-1">ADX</div>
                                <div className={`font-mono font-bold ${adx > 25 ? 'text-yellow-400' : 'text-gray-300'}`}>
                                    {adx.toFixed(0)}
                                </div>
                            </div>
                            <div className="bg-white/[0.02] p-2 rounded-lg border border-white/5">
                                <div className="text-gray-500 mb-1">Vol 24h</div>
                                <div className="font-mono font-bold text-gray-300">
                                    {formatNumber(volume_24h)}
                                </div>
                            </div>
                            {/* RVOL: Replaces Open Interest */}
                            <div className="bg-white/[0.02] p-2 rounded-lg border border-white/5">
                                <div className="text-gray-500 mb-1">RVol</div>
                                <div className={`font-mono font-bold ${rvol > 1.5 ? 'text-yellow-400' : 'text-gray-300'}`}>
                                    {rvol > 0 ? rvol.toFixed(1) + 'x' : '--'}
                                </div>
                            </div>
                        </div>

                        <button
                            onClick={handleAskAi}
                            className="w-full bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-500 hover:to-indigo-500 text-white py-2 rounded-lg text-xs font-bold shadow-lg transition-transform active:scale-95 flex items-center justify-center gap-2"
                        >
                            ✨ Ask AI
                        </button>
                    </div>

                </div>
            </div>

            {/* AI Modal (Copied from CrystalWeather) */}
            {showModal && mounted && createPortal(
                <div className="fixed inset-0 z-[9999] flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm">
                    <div className="bg-gray-900 border border-purple-500/30 w-full max-w-lg rounded-2xl shadow-2xl overflow-hidden animate-in fade-in zoom-in-95 duration-200 relative">
                        {/* Header */}
                        <div className="bg-gradient-to-r from-purple-900/50 to-indigo-900/50 p-4 flex items-center justify-between border-b border-white/10">
                            <div className="flex items-center gap-2">
                                <span className="text-2xl">✨</span>
                                <h3 className="font-bold text-lg text-white">Gemini Market Analysis</h3>
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
                                        </>
                                    )}
                                </div>
                            ) : (
                                <p className="text-red-400 text-center">Failed to load analysis.</p>
                            )}
                        </div>
                    </div>
                </div>,
                document.body
            )}
        </>
    )
}
