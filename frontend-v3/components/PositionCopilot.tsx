'use client';

import React, { useEffect, useState, useRef } from 'react';
import useSWR from 'swr';
import { TrendingUp, TrendingDown, Minus, Anchor, AlertTriangle, ShieldCheck, Activity, BarChart2, Bell } from 'lucide-react';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8001';

// Fetcher for SWR
const fetcher = (url: string) => fetch(url).then((res) => res.json());

interface TimeframeSentiment {
    sentiment: string;
    score: number;
    rsi: number;
    trend: string;
    macd: {
        value: number;
        crossover: string;
        hist: number;
    };
    volume: {
        status: string;
        value: number;
    };
    details: string;
}

interface PositionAnalysis {
    symbol: string;
    size: any;
    analysis: {
        advice: string;
        color: string;
        reason: string;
        score: number;
    };
}

interface SentimentHistory {
    timestamp: number;
    sentiment: string;
    score: number;
}

interface AnalysisResponse {
    symbol: string;
    market_sentiment: {
        "5m": TimeframeSentiment;
        "1h": TimeframeSentiment;
        "4h": TimeframeSentiment;
        "history": SentimentHistory[];
    };
    positions_analysis: PositionAnalysis[];
    global_advice: string;
}

export default function PositionCopilot() {
    const { data, error } = useSWR<AnalysisResponse>(
        `${API_BASE_URL}/api/analysis/`,
        fetcher,
        { refreshInterval: 3000 }
    );

    const [alertMsg, setAlertMsg] = useState<string | null>(null);
    const lastSentimentRef = useRef<string | null>(null);

    // Alert Logic
    useEffect(() => {
        if (data?.market_sentiment?.["1h"]) {
            const currentSentiment = data.market_sentiment["1h"].sentiment;

            // Initial Load
            if (lastSentimentRef.current === null) {
                lastSentimentRef.current = currentSentiment;
                return;
            }

            // Check change
            if (lastSentimentRef.current !== currentSentiment) {
                setAlertMsg(`Market Sentiment Changed: ${lastSentimentRef.current} ➔ ${currentSentiment}`);
                lastSentimentRef.current = currentSentiment;

                // Auto dismiss after 5s
                setTimeout(() => setAlertMsg(null), 5000);
            }
        }
    }, [data]);

    if (error) return null;
    if (!data) return (
        <div className="w-full bg-[#111] border border-gray-800 rounded-lg p-6 animate-pulse">
            <div className="h-4 bg-gray-800 rounded w-1/3 mb-4"></div>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div className="h-24 bg-gray-800 rounded"></div>
                <div className="h-24 bg-gray-800 rounded"></div>
                <div className="h-24 bg-gray-800 rounded"></div>
            </div>
        </div>
    );

    const getSentimentIcon = (sentiment: string) => {
        if (sentiment === "BULLISH") return <TrendingUp className="w-4 h-4" />;
        if (sentiment === "BEARISH") return <TrendingDown className="w-4 h-4" />;
        return <Minus className="w-4 h-4" />;
    };

    const getSentimentColor = (sentiment: string) => {
        if (sentiment === "BULLISH") return "text-profit bg-profit/10 border-profit/20";
        if (sentiment === "BEARISH") return "text-loss bg-loss/10 border-loss/20";
        return "text-gray-400 bg-gray-800/50 border-gray-700/50";
    };

    // Helper for Advice Pill
    const getAdviceStyle = (advice: string) => {
        switch (advice) {
            case "GOOD": return "bg-green-500/10 text-green-400 border-green-500/20";
            case "TAKE PROFIT": return "bg-emerald-500/20 text-emerald-400 border-emerald-500/30 animate-pulse";
            case "CAUTION": return "bg-orange-500/10 text-orange-400 border-orange-500/20";
            case "DANGER": return "bg-red-500/20 text-red-500 border-red-500/30 font-bold";
            default: return "bg-blue-500/10 text-blue-400 border-blue-500/20";
        }
    };

    const hasPosition = data.positions_analysis && data.positions_analysis.length > 0;
    const activePos = hasPosition ? data.positions_analysis[0] : null;

    // if (!hasPosition) return null; // Logic removed to show sentiment even when flat

    return (
        <div className="w-full bg-[#0E0E0E] border border-gray-800 rounded-xl p-5 shadow-2xl relative overflow-hidden transition-all">

            {/* Alert Banner */}
            {alertMsg && (
                <div className="absolute top-0 left-0 w-full bg-blue-600 text-white text-xs font-bold px-4 py-1 flex items-center justify-center animate-in slide-in-from-top-2">
                    <Bell className="w-3 h-3 mr-2" />
                    {alertMsg}
                </div>
            )}

            {/* Header */}
            <div className="flex justify-between items-start mb-6 mt-2">
                <div>
                    <h2 className="text-gray-200 font-bold text-lg flex items-center gap-2">
                        <Anchor className="w-5 h-5 text-blue-500" />
                        Position Copilot
                        <span className="text-xs font-normal text-gray-500 bg-gray-800 px-2 py-0.5 rounded-full">
                            {data.symbol}
                        </span>
                    </h2>
                    <p className="text-gray-500 text-xs mt-1">Multi-Timeframe Sentiment Analysis v2</p>
                </div>

                {activePos && (
                    <div className={`px-4 py-2 rounded-lg border flex items-center gap-2 ${getAdviceStyle(activePos.analysis.advice)}`}>
                        {activePos.analysis.advice === 'DANGER' ? <AlertTriangle className="w-4 h-4" /> : <ShieldCheck className="w-4 h-4" />}
                        <div className="flex flex-col items-end">
                            <span className="text-xs font-bold tracking-wider opacity-70">ADVICE</span>
                            <span className="font-bold">{activePos.analysis.advice}</span>
                        </div>
                    </div>
                )}
            </div>

            {/* Timeframe Grid - Mobile Optimized */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-3 mb-4">
                {["5m", "1h", "4h"].map((tf) => {
                    // @ts-ignore
                    const senti = data.market_sentiment[tf] as TimeframeSentiment;
                    if (!senti) return null;

                    return (
                        <div key={tf} className={`flex flex-col p-3 rounded-lg border ${getSentimentColor(senti.sentiment)} transition-all duration-300 hover:scale-[1.02] relative overflow-hidden`}>

                            {/* Header Line */}
                            <div className="flex justify-between items-center mb-2">
                                <div className="text-[10px] uppercase font-bold opacity-60">{tf} Term</div>
                                <div className="flex items-center gap-1.5 font-bold text-sm">
                                    {getSentimentIcon(senti.sentiment)}
                                    {senti.sentiment}
                                </div>
                            </div>

                            {/* Metrics Grid */}
                            <div className="grid grid-cols-2 gap-2 text-[10px] opacity-80 font-mono mt-1">
                                <div className="bg-black/20 p-1 rounded">
                                    RSI: <span className={senti.rsi > 70 || senti.rsi < 30 ? "text-yellow-400" : ""}>{senti.rsi}</span>
                                </div>
                                <div className="bg-black/20 p-1 rounded flex items-center gap-1">
                                    MACD:
                                    <span className={senti.macd?.crossover === "BULLISH" ? "text-green-400" : senti.macd?.crossover === "BEARISH" ? "text-red-400" : ""}>
                                        {senti.macd?.crossover === "BULLISH" ? "▲" : "▼"}
                                    </span>
                                </div>
                                <div className="col-span-2 bg-black/20 p-1 rounded flex justify-between">
                                    <span>VOL: {senti.volume?.status}</span>
                                    <BarChart2 className="w-3 h-3 opacity-50" />
                                </div>
                            </div>
                        </div>
                    );
                })}
            </div>

            {/* Historical Context & Analysis Footer */}
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                {/* Context/Reasoning Footer */}
                {activePos && (
                    <div className="md:col-span-3 bg-gray-900/50 rounded-lg p-3 border border-gray-800 text-sm flex items-start gap-3">
                        <div className="mt-1 w-1.5 h-1.5 rounded-full bg-blue-500"></div>
                        <div className="text-gray-300">
                            <span className="text-gray-500 font-bold mr-2">ANALYSIS:</span>
                            {activePos.analysis.reason}
                        </div>
                    </div>
                )}
                {/* History Sparklines (Simple List) */}
                <div className="md:col-span-1 bg-gray-900/30 rounded-lg p-3 border border-gray-800 flex flex-col justify-center">
                    <div className="text-[10px] uppercase text-gray-500 font-bold mb-2 flex items-center gap-1">
                        <Activity className="w-3 h-3" /> History (1H)
                    </div>
                    <div className="space-y-1">
                        {data.market_sentiment.history && data.market_sentiment.history.slice(-3).reverse().map((h, i) => (
                            <div key={i} className="flex justify-between text-[10px]">
                                <span className="text-gray-400">{new Date(h.timestamp * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
                                <span className={h.sentiment === "BULLISH" ? "text-green-500" : "text-red-500"}>{h.sentiment}</span>
                            </div>
                        ))}
                        {(!data.market_sentiment.history || data.market_sentiment.history.length === 0) && (
                            <span className="text-[10px] text-gray-600">No history yet</span>
                        )}
                    </div>
                </div>
            </div>
        </div>
    );
}
