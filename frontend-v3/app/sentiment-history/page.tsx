'use client';

import React, { useState } from 'react';
import useSWR from 'swr';
import Link from 'next/link';
import { ArrowLeft, TrendingUp, TrendingDown, Minus, Activity } from 'lucide-react';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8001';

interface SentimentEntry {
    timestamp: number;
    symbol: string;
    sentiment: string;
    score: number;
    details: string;
}

const fetcher = (url: string) => fetch(url).then((res) => res.json());

export default function SentimentHistoryPage() {
    const { data, error, isLoading } = useSWR<SentimentEntry[]>(
        `${API_BASE_URL}/api/sentiment-history`,
        fetcher,
        { refreshInterval: 5000 }
    );

    const [filterSymbol, setFilterSymbol] = useState<string>('');
    const [filterSentiment, setFilterSentiment] = useState<string>('');

    // Get unique symbols
    const symbols = React.useMemo(() => {
        if (!data) return [];
        return Array.from(new Set(data.map(entry => entry.symbol))).sort();
    }, [data]);

    // Filter data
    const filteredData = React.useMemo(() => {
        if (!data) return [];
        return data.filter(entry => {
            const matchSymbol = !filterSymbol || entry.symbol === filterSymbol;
            const matchSentiment = !filterSentiment || entry.sentiment === filterSentiment;
            return matchSymbol && matchSentiment;
        });
    }, [data, filterSymbol, filterSentiment]);

    // Get sentiment icon and color
    const getSentimentDisplay = (sentiment: string, score: number) => {
        switch (sentiment) {
            case 'BULLISH':
                return {
                    icon: <TrendingUp className="w-4 h-4" />,
                    color: 'text-profit',
                    bgColor: 'bg-profit/20',
                    borderColor: 'border-profit/30'
                };
            case 'BEARISH':
                return {
                    icon: <TrendingDown className="w-4 h-4" />,
                    color: 'text-loss',
                    bgColor: 'bg-loss/20',
                    borderColor: 'border-loss/30'
                };
            case 'NEUTRAL':
                return {
                    icon: <Minus className="w-4 h-4" />,
                    color: 'text-gray-400',
                    bgColor: 'bg-gray-500/20',
                    borderColor: 'border-gray-500/30'
                };
            default:
                return {
                    icon: <Activity className="w-4 h-4" />,
                    color: 'text-blue-400',
                    bgColor: 'bg-blue-500/20',
                    borderColor: 'border-blue-500/30'
                };
        }
    };

    // Format timestamp
    const formatTimestamp = (timestamp: number) => {
        const date = new Date(timestamp * 1000);
        return date.toLocaleString('fr-FR', {
            year: 'numeric',
            month: '2-digit',
            day: '2-digit',
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit'
        });
    };

    return (
        <main className="min-h-screen p-4 md:p-8">
            <div className="max-w-6xl mx-auto">
                {/* Header */}
                <div className="flex items-center gap-4 mb-6">
                    <Link
                        href="/"
                        className="p-2 rounded-lg bg-gray-800 hover:bg-gray-700 transition-colors"
                    >
                        <ArrowLeft className="w-5 h-5 text-gray-400" />
                    </Link>
                    <div>
                        <h1 className="text-2xl font-bold text-white">Sentiment History</h1>
                        <p className="text-gray-500 text-sm">Market sentiment analysis over time</p>
                    </div>
                </div>

                {/* Filters */}
                <div className="bg-gray-900/50 border border-gray-800 rounded-lg p-4 mb-4">
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        <div>
                            <label className="text-sm text-gray-400 mb-2 block">Filter by Symbol</label>
                            <select
                                value={filterSymbol}
                                onChange={(e) => setFilterSymbol(e.target.value)}
                                className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500"
                            >
                                <option value="">All Symbols</option>
                                {symbols.map(symbol => (
                                    <option key={symbol} value={symbol}>{symbol}</option>
                                ))}
                            </select>
                        </div>
                        <div>
                            <label className="text-sm text-gray-400 mb-2 block">Filter by Sentiment</label>
                            <select
                                value={filterSentiment}
                                onChange={(e) => setFilterSentiment(e.target.value)}
                                className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500"
                            >
                                <option value="">All Sentiments</option>
                                <option value="BULLISH">Bullish</option>
                                <option value="BEARISH">Bearish</option>
                                <option value="NEUTRAL">Neutral</option>
                            </select>
                        </div>
                    </div>
                </div>

                {/* Loading State */}
                {isLoading && (
                    <div className="text-center text-gray-400 py-12">
                        <div className="animate-pulse">Loading sentiment history...</div>
                    </div>
                )}

                {/* Error State */}
                {error && (
                    <div className="text-center text-loss py-12">
                        <div>Unable to load sentiment history</div>
                        <div className="text-sm text-gray-500 mt-2">Make sure the backend is running</div>
                    </div>
                )}

                {/* Data Display */}
                {data && (
                    <div className="bg-gray-900/50 border border-gray-800 rounded-lg overflow-hidden">
                        <div className="px-4 py-3 border-b border-gray-800 flex justify-between items-center">
                            <span className="text-sm text-gray-400">
                                {filteredData.length} entries {filterSymbol || filterSentiment ? `(filtered from ${data.length})` : ''}
                            </span>
                            <span className="text-xs text-gray-600">
                                Auto-refresh: 5s
                            </span>
                        </div>

                        <div className="max-h-[70vh] overflow-y-auto">
                            {filteredData.length === 0 ? (
                                <div className="text-center text-gray-500 py-12">
                                    No sentiment data available
                                </div>
                            ) : (
                                <div className="divide-y divide-gray-800/50">
                                    {filteredData.map((entry, index) => {
                                        const display = getSentimentDisplay(entry.sentiment, entry.score);
                                        return (
                                            <div
                                                key={index}
                                                className="px-4 py-3 hover:bg-gray-800/30 transition-colors"
                                            >
                                                <div className="flex items-start gap-4">
                                                    {/* Icon */}
                                                    <div className={`${display.color} mt-1`}>
                                                        {display.icon}
                                                    </div>

                                                    {/* Content */}
                                                    <div className="flex-1 min-w-0">
                                                        <div className="flex items-center gap-2 mb-1">
                                                            <span className="font-bold text-white">{entry.symbol}</span>
                                                            <span className={`px-2 py-0.5 rounded text-xs font-medium ${display.bgColor} ${display.color} border ${display.borderColor}`}>
                                                                {entry.sentiment}
                                                            </span>
                                                            <span className={`text-sm font-mono ${entry.score > 0 ? 'text-profit' : entry.score < 0 ? 'text-loss' : 'text-gray-400'}`}>
                                                                {entry.score > 0 ? '+' : ''}{entry.score}
                                                            </span>
                                                        </div>
                                                        <div className="text-sm text-gray-400 mb-1">
                                                            {entry.details}
                                                        </div>
                                                        <div className="text-xs text-gray-600 font-mono">
                                                            {formatTimestamp(entry.timestamp)}
                                                        </div>
                                                    </div>
                                                </div>
                                            </div>
                                        );
                                    })}
                                </div>
                            )}
                        </div>
                    </div>
                )}
            </div>
        </main>
    );
}
