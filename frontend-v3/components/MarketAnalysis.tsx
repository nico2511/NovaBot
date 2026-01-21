'use client';

import { BarChart2, Zap, Activity, TrendingUp, TrendingDown } from 'lucide-react';

interface MarketAnalysisProps {
    analysis: Record<string, any>;
}

export default function MarketAnalysis({ analysis }: MarketAnalysisProps) {
    if (!analysis || Object.keys(analysis).length === 0) {
        return null; // Or skeleton loader
    }

    const {
        symbol = "BTC",
        close,
        rsi_14,
        adx_14,
        regime = "RANGE",
        market_bias = "NEUTRAL",
        current_volume,
        volume_ratio,
        recent_closes = []
    } = analysis;

    // --- Helpers ---
    const formatNumber = (num: number) => new Intl.NumberFormat('en-US', { notation: "compact", maximumFractionDigits: 1 }).format(num);

    // Sparkline Generator
    const renderSparkline = (data: number[]) => {
        if (!data || data.length < 2) return null;
        const min = Math.min(...data);
        const max = Math.max(...data);
        const range = max - min;
        const width = 120;
        const height = 40;

        // Normalize points
        const points = data.map((val, i) => {
            const x = (i / (data.length - 1)) * width;
            const y = height - ((val - min) / range) * height;
            return `${x},${y}`;
        }).join(' ');

        const isGreen = data[data.length - 1] > data[0];
        const color = isGreen ? '#22c55e' : '#ef4444';

        return (
            <svg width={width} height={height} className="overflow-visible">
                <polyline
                    fill="none"
                    stroke={color}
                    strokeWidth="2"
                    points={points}
                />
            </svg>
        );
    };

    // Color Logic
    const biasColor = market_bias === "BULLISH" ? "text-green-400 bg-green-900/30 border-green-800" : market_bias === "BEARISH" ? "text-red-400 bg-red-900/30 border-red-800" : "text-gray-400 bg-gray-800 border-gray-700";
    const regimeColor = regime.includes("TREND") ? "text-purple-400 bg-purple-900/30 border-purple-800" : "text-blue-400 bg-blue-900/30 border-blue-800";

    return (
        <div className="bg-[#111] border border-[#333] rounded-2xl p-6 mt-6">
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6 divide-y md:divide-y-0 md:divide-x divide-[#333]">

                {/* 1. Symbol & Badges */}
                <div className="flex flex-col justify-center pr-4">
                    <h2 className="text-3xl font-black text-white tracking-widest mb-4">{symbol}</h2>
                    <div className="flex gap-2 mb-4">
                        <span className={`px-3 py-1 rounded text-xs font-bold border ${biasColor}`}>
                            {market_bias}
                        </span>
                        <span className={`px-3 py-1 rounded text-xs font-bold border ${regimeColor}`}>
                            {regime}
                        </span>
                    </div>
                    <div className="text-4xl font-mono text-white tracking-tighter">
                        ${close ? close.toFixed(close < 1 ? 4 : 2) : '0.00'}
                    </div>
                </div>

                {/* 2. Sparklines (Trend) */}
                <div className="flex flex-col justify-center items-center px-4">
                    <div className="grid grid-cols-1 gap-6 text-center w-full max-w-[200px]">
                        {/* 15M / Scanner Timeframe */}
                        <div className="flex flex-col items-center">
                            <div className="h-[40px] flex items-center justify-center">
                                {renderSparkline(recent_closes) || <span className="text-gray-600 text-xs">No Data</span>}
                            </div>
                            <span className="text-xs text-gray-500 mt-2 uppercase tracking-widest">Active Scale (20c)</span>
                        </div>
                    </div>
                </div>

                {/* 3. Key Metrics */}
                <div className="flex flex-col justify-center pl-4 pt-4 md:pt-0">
                    <div className="grid grid-cols-2 gap-y-6 gap-x-8">
                        <div>
                            <div className="text-xs text-gray-500 uppercase mb-1">RSI (14)</div>
                            <div className={`text-xl font-bold ${rsi_14 > 70 ? 'text-red-400' : rsi_14 < 30 ? 'text-green-400' : 'text-gray-300'}`}>
                                {rsi_14 ? rsi_14.toFixed(0) : '-'}
                            </div>
                        </div>
                        <div>
                            <div className="text-xs text-gray-500 uppercase mb-1">ADX (14)</div>
                            <div className={`text-xl font-bold ${adx_14 > 25 ? 'text-purple-400' : 'text-gray-400'}`}>
                                {adx_14 ? adx_14.toFixed(0) : '-'}
                            </div>
                        </div>
                        <div>
                            <div className="text-xs text-gray-500 uppercase mb-1">Vol 24h</div>
                            <div className="text-xl font-bold text-gray-300">
                                ${current_volume ? formatNumber(current_volume) : '-'}
                            </div>
                        </div>
                        <div>
                            <div className="text-xs text-gray-500 uppercase mb-1">RVol</div>
                            <div className={`text-xl font-bold ${volume_ratio > 1.5 ? 'text-yellow-400' : 'text-gray-300'}`}>
                                {volume_ratio ? volume_ratio.toFixed(1) : '-'}x
                            </div>
                        </div>
                    </div>

                    <div className="mt-6 w-full">
                        <button className="w-full bg-blue-600 hover:bg-blue-500 text-white font-bold py-2 rounded-lg flex items-center justify-center gap-2 transition-colors">
                            <Zap className="w-4 h-4 fill-white" /> Ask AI
                        </button>
                    </div>
                </div>
            </div>
        </div>
    );
}
