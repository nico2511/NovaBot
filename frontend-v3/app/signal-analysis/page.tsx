'use client';

import React, { useState } from 'react';
import useSWR from 'swr';
import Link from 'next/link';
import { ArrowLeft, TrendingUp, TrendingDown, CheckCircle, XCircle, AlertTriangle, Download } from 'lucide-react';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8001';

interface SignalEntry {
    timestamp: string;
    symbol: string;
    direction: string;
    strategy: string;
    approved: boolean;
    confidence: number;
    reasoning: string;
    risk_level: string;
    market_price: number;
    suggested_sl: number | null;
    suggested_tp: number | null;
    indicators?: {
        rsi: number;
        adx: number;
        ema_50: number;
        bb_upper: number;
        bb_lower: number;
        volume_ratio: number;
        [key: string]: any;
    };
}

const fetcher = (url: string) => fetch(url).then((res) => res.json());

export default function SignalAnalysisPage() {
    const { data, error, isLoading } = useSWR<SignalEntry[]>(
        `${API_BASE_URL}/api/signal-analysis`,
        fetcher,
        { refreshInterval: 5000 }
    );

    const [filterSymbol, setFilterSymbol] = useState<string>('');
    const [filterApproved, setFilterApproved] = useState<string>('approved');
    const [filterDirection, setFilterDirection] = useState<string>('');

    // Get unique symbols
    const symbols = React.useMemo(() => {
        if (!data) return [];
        return Array.from(new Set(data.map(entry => entry.symbol))).sort();
    }, [data]);

    // Filter and Sort data
    const filteredData = React.useMemo(() => {
        if (!data) return [];
        return data.filter(entry => {
            const matchSymbol = !filterSymbol || entry.symbol === filterSymbol;
            const matchApproved = !filterApproved ||
                (filterApproved === 'approved' && entry.approved) ||
                (filterApproved === 'rejected' && !entry.approved);
            const matchDirection = !filterDirection || entry.direction === filterDirection;
            return matchSymbol && matchApproved && matchDirection;
        })
            .sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime());
    }, [data, filterSymbol, filterApproved, filterDirection]);

    // Get risk level color
    const getRiskColor = (risk: string) => {
        switch (risk) {
            case 'LOW':
                return 'text-profit bg-profit/20 border-profit/30';
            case 'MEDIUM':
                return 'text-amber-400 bg-amber-500/20 border-amber-500/30';
            case 'HIGH':
                return 'text-loss bg-loss/20 border-loss/30';
            default:
                return 'text-gray-400 bg-gray-500/20 border-gray-500/30';
        }
    };

    // Format timestamp
    const formatTimestamp = (timestamp: string) => {
        const date = new Date(timestamp);
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
            <div className="max-w-7xl mx-auto">
                {/* Header */}
                <div className="flex items-center justify-between mb-6">
                    <div className="flex items-center gap-4">
                        <Link
                            href="/"
                            className="p-2 rounded-lg bg-gray-800 hover:bg-gray-700 transition-colors"
                        >
                            <ArrowLeft className="w-5 h-5 text-gray-400" />
                        </Link>
                        <div>
                            <h1 className="text-2xl font-bold text-white">Signal Analysis</h1>
                            <p className="text-gray-500 text-sm">Trading signals and AI decision history</p>
                        </div>
                    </div>

                    {/* Download Button */}
                    <a
                        href={`${API_BASE_URL}/api/signal-analysis/download`}
                        download="signal_analysis.json"
                        className="flex items-center gap-2 px-4 py-2 rounded-lg bg-blue-600 hover:bg-blue-700 transition-colors text-white font-medium"
                    >
                        <Download className="w-4 h-4" />
                        Export JSON
                    </a>
                </div>

                {/* Filters */}
                <div className="bg-gray-900/50 border border-gray-800 rounded-lg p-4 mb-4">
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
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
                            <label className="text-sm text-gray-400 mb-2 block">Filter by Status</label>
                            <select
                                value={filterApproved}
                                onChange={(e) => setFilterApproved(e.target.value)}
                                className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500"
                            >
                                <option value="">All Signals</option>
                                <option value="approved">Approved</option>
                                <option value="rejected">Rejected</option>
                            </select>
                        </div>
                        <div>
                            <label className="text-sm text-gray-400 mb-2 block">Filter by Direction</label>
                            <select
                                value={filterDirection}
                                onChange={(e) => setFilterDirection(e.target.value)}
                                className="w-full bg-gray-800 border border-gray-700 rounded-lg px-3 py-2 text-white text-sm focus:outline-none focus:border-blue-500"
                            >
                                <option value="">All Directions</option>
                                <option value="BUY">Buy</option>
                                <option value="SELL">Sell</option>
                            </select>
                        </div>
                    </div>
                </div>

                {/* Loading State */}
                {isLoading && (
                    <div className="text-center text-gray-400 py-12">
                        <div className="animate-pulse">Loading signal analysis...</div>
                    </div>
                )}

                {/* Error State */}
                {error && (
                    <div className="text-center text-loss py-12">
                        <div>Unable to load signal analysis</div>
                        <div className="text-sm text-gray-500 mt-2">Make sure the backend is running</div>
                    </div>
                )}

                {/* Data Display */}
                {data && (
                    <div className="bg-gray-900/50 border border-gray-800 rounded-lg overflow-hidden">
                        <div className="px-4 py-3 border-b border-gray-800 flex justify-between items-center">
                            <span className="text-sm text-gray-400">
                                {filteredData.length} signals {filterSymbol || filterApproved || filterDirection ? `(filtered from ${data.length})` : ''}
                            </span>
                            <span className="text-xs text-gray-600">
                                Auto-refresh: 5s
                            </span>
                        </div>

                        <div className="max-h-[70vh] overflow-y-auto">
                            {filteredData.length === 0 ? (
                                <div className="text-center text-gray-500 py-12">
                                    No signal data available
                                </div>
                            ) : (
                                <div className="divide-y divide-gray-800/50">
                                    {filteredData.map((entry, index) => (
                                        <div
                                            key={index}
                                            className="px-4 py-4 hover:bg-gray-800/30 transition-colors"
                                        >
                                            <div className="flex items-start gap-4">
                                                {/* Direction Icon */}
                                                <div className={`mt-1 ${entry.direction === 'BUY' ? 'text-profit' : 'text-loss'}`}>
                                                    {entry.direction === 'BUY' ?
                                                        <TrendingUp className="w-5 h-5" /> :
                                                        <TrendingDown className="w-5 h-5" />
                                                    }
                                                </div>

                                                {/* Content */}
                                                <div className="flex-1 min-w-0">
                                                    {/* Header Row */}
                                                    <div className="flex items-center gap-2 mb-2 flex-wrap">
                                                        <span className="font-bold text-white text-lg">{entry.symbol}</span>
                                                        <span className={`px-2 py-0.5 rounded text-xs font-bold ${entry.direction === 'BUY' ? 'bg-profit/20 text-profit border border-profit/30' : 'bg-loss/20 text-loss border border-loss/30'}`}>
                                                            {entry.direction}
                                                        </span>
                                                        <span className="text-xs text-gray-500 px-2 py-0.5 bg-gray-800 rounded">
                                                            {entry.strategy}
                                                        </span>
                                                        {entry.approved ? (
                                                            <span className="flex items-center gap-1 text-xs text-profit bg-profit/20 px-2 py-0.5 rounded border border-profit/30">
                                                                <CheckCircle className="w-3 h-3" />
                                                                Approved
                                                            </span>
                                                        ) : (
                                                            <span className="flex items-center gap-1 text-xs text-loss bg-loss/20 px-2 py-0.5 rounded border border-loss/30">
                                                                <XCircle className="w-3 h-3" />
                                                                Rejected
                                                            </span>
                                                        )}
                                                    </div>

                                                    {/* Metrics Row */}
                                                    <div className="flex items-center gap-4 mb-2 text-sm">
                                                        <div className="flex items-center gap-1">
                                                            <span className="text-gray-500">Confidence:</span>
                                                            <span className={`font-bold ${entry.confidence >= 70 ? 'text-profit' : entry.confidence >= 40 ? 'text-amber-400' : 'text-loss'}`}>
                                                                {entry.confidence}%
                                                            </span>
                                                        </div>
                                                        <div className="flex items-center gap-1">
                                                            <span className="text-gray-500">Risk:</span>
                                                            <span className={`text-xs px-2 py-0.5 rounded border ${getRiskColor(entry.risk_level)}`}>
                                                                {entry.risk_level}
                                                            </span>
                                                        </div>
                                                        <div className="flex items-center gap-1">
                                                            <span className="text-gray-500">Price:</span>
                                                            <span className="text-white font-mono">${entry.market_price.toLocaleString()}</span>
                                                        </div>
                                                    </div>

                                                    {/* Technical Indicators Row */}
                                                    {entry.indicators && (
                                                        <div className="grid grid-cols-2 md:grid-cols-4 gap-2 mb-2 text-xs bg-gray-800/20 p-2 rounded border border-gray-800/50">
                                                            <div className="flex items-center gap-1">
                                                                <span className="text-gray-500">RSI:</span>
                                                                <span className={`font-mono ${entry.indicators.rsi > 70 ? 'text-loss' : entry.indicators.rsi < 30 ? 'text-profit' : 'text-gray-300'}`}>
                                                                    {entry.indicators.rsi?.toFixed(1) || '-'}
                                                                </span>
                                                            </div>
                                                            <div className="flex items-center gap-1">
                                                                <span className="text-gray-500">MA50:</span>
                                                                <span className="font-mono text-gray-300">
                                                                    {entry.indicators.ema_50?.toLocaleString(undefined, { maximumFractionDigits: 2 }) || '-'}
                                                                </span>
                                                            </div>
                                                            <div className="flex items-center gap-1">
                                                                <span className="text-gray-500">BB Width:</span>
                                                                <span className="font-mono text-gray-300">
                                                                    {entry.indicators.bb_width?.toFixed(2) || '-'}
                                                                </span>
                                                            </div>
                                                            <div className="flex items-center gap-1">
                                                                <span className="text-gray-500">Adx:</span>
                                                                <span className="font-mono text-gray-300">
                                                                    {entry.indicators.adx?.toFixed(1) || '-'}
                                                                </span>
                                                            </div>
                                                        </div>
                                                    )}

                                                    {/* Reasoning */}
                                                    <div className="text-sm text-gray-400 mb-2 bg-gray-800/50 p-2 rounded">
                                                        {entry.reasoning}
                                                    </div>

                                                    {/* SL/TP if available */}
                                                    {(entry.suggested_sl || entry.suggested_tp) && (
                                                        <div className="flex items-center gap-4 text-xs text-gray-500 mb-2">
                                                            {entry.suggested_sl && (
                                                                <div>
                                                                    <span className="text-gray-600">SL:</span> <span className="font-mono text-loss">${entry.suggested_sl}</span>
                                                                </div>
                                                            )}
                                                            {entry.suggested_tp && (
                                                                <div>
                                                                    <span className="text-gray-600">TP:</span> <span className="font-mono text-profit">${entry.suggested_tp}</span>
                                                                </div>
                                                            )}
                                                        </div>
                                                    )}

                                                    {/* Timestamp */}
                                                    <div className="text-xs text-gray-600 font-mono">
                                                        {formatTimestamp(entry.timestamp)}
                                                    </div>
                                                </div>
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            )}
                        </div>
                    </div>
                )}
            </div>
        </main>
    );
}
