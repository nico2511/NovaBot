'use client';

import React from 'react';
import useSWR from 'swr';
import Link from 'next/link';
import { ArrowLeft, RefreshCw, Layers, Activity } from 'lucide-react';
import StrategyMonitorCard from '@/components/StrategyMonitorCard';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8001';
const fetcher = (url: string) => fetch(url).then((res) => res.json());

export default function StrategiesPage() {
    const { data, error, isLoading, mutate } = useSWR(
        `${API_BASE_URL}/api/strategies/monitor`,
        fetcher,
        { refreshInterval: 1000 } // Live updates every second
    );

    return (
        <main className="min-h-screen bg-[#0a0a0a] text-white p-4 md:p-8">
            <div className="max-w-7xl mx-auto space-y-6">
                {/* Header */}
                <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4 border-b border-gray-800 pb-6">
                    <div>
                        <Link href="/" className="inline-flex items-center text-gray-400 hover:text-white mb-2 transition-colors">
                            <ArrowLeft className="w-4 h-4 mr-2" /> Back to Dashboard
                        </Link>
                        <h1 className="text-2xl md:text-3xl font-bold flex items-center gap-3">
                            <Layers className="w-8 h-8 text-blue-500" />
                            Strategy Monitor
                        </h1>
                        <p className="text-gray-500 mt-1">Real-time analysis of trigger conditions and checks</p>
                    </div>

                    <div className="flex items-center gap-4">
                        {data && (
                            <div className="text-right">
                                <div className="text-xs text-gray-500 uppercase tracking-widest font-bold">Active Symbol</div>
                                <div className="text-xl font-bold text-blue-400">{data.symbol || '---'}</div>
                            </div>
                        )}
                        <button
                            onClick={() => mutate()}
                            className="p-2 bg-gray-900 rounded-lg hover:bg-gray-800 border border-gray-800 transition-all hover:scale-105"
                        >
                            <RefreshCw className={`w-5 h-5 text-gray-400 ${isLoading ? 'animate-spin' : ''}`} />
                        </button>
                    </div>
                </div>

                {/* Content */}
                {isLoading && !data ? (
                    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 animate-pulse">
                        {[1, 2, 3].map(i => (
                            <div key={i} className="h-64 bg-gray-900/50 rounded-xl border border-gray-800"></div>
                        ))}
                    </div>
                ) : error ? (
                    <div className="text-center py-20 bg-gray-900/30 rounded-xl border border-gray-800 border-dashed">
                        <p className="text-red-400 mb-2">Failed to load strategy data</p>
                        <p className="text-sm text-gray-600">Ensure the backend is running and you have restarted it to enable the monitor endpoint.</p>
                    </div>
                ) : (
                    <div className="space-y-6">
                        {/* Regime Context Header */}
                        {data.status !== 'waiting' && data.regime && (
                            <div className="bg-blue-900/10 border border-blue-500/20 p-4 rounded-xl flex items-center justify-between">
                                <div className="flex items-center gap-3">
                                    <Activity className={`w-5 h-5 ${data.regime === 'TREND' ? 'text-green-400' : 'text-orange-400'}`} />
                                    <div>
                                        <div className="text-xs text-blue-400 font-bold uppercase tracking-wider">Current Regime</div>
                                        <div className="text-white font-bold text-lg">{data.regime} <span className="text-gray-500 text-sm font-normal">(Auto-Focus Enabled)</span></div>
                                    </div>
                                </div>
                            </div>
                        )}

                        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                            {data.status === 'waiting' ? (
                                <div className="col-span-full text-center py-20 bg-gray-900/30 rounded-xl border border-gray-800 border-dashed animate-pulse">
                                    <RefreshCw className="w-12 h-12 text-blue-500 mx-auto mb-4 animate-spin" />
                                    <h3 className="text-gray-400 font-bold">Waiting for Market Data...</h3>
                                    <p className="text-sm text-gray-600 mt-2">{data.message || "Initializing strategies..."}</p>
                                </div>
                            ) : data.strategies && Array.isArray(data.strategies) ? (
                                <>
                                    {data.strategies.filter((strat: any) => {
                                        // Filtering Logic
                                        const regime = data.regime || 'UNKNOWN';
                                        const type = strat.type || 'unknown';

                                        // Universal types always show
                                        if (['liquidity', 'scalp_choc', 'institutional_scalp', 'scalp'].includes(type)) return true;

                                        if (regime === 'TREND') {
                                            return ['trend', 'trend_dip', 'trend_continuation', 'fibo_pullback', 'scalp'].includes(type);
                                        } else if (regime === 'RANGE') {
                                            return ['range', 'reversion', 'reversion_extreme', 'scalp'].includes(type);
                                        }

                                        // If unknown regime, show all
                                        return true;
                                    }).map((strat: any, idx: number) => (
                                        <StrategyMonitorCard key={idx} data={strat} />
                                    ))}

                                    {data.strategies.length > 0 && data.strategies.every((s: any) => {
                                        // Check if ALL got filtered out
                                        const regime = data.regime || 'UNKNOWN';
                                        const type = s.type || 'unknown';
                                        const isUniversal = ['liquidity', 'scalp_choc', 'institutional_scalp', 'scalp'].includes(type);
                                        if (isUniversal) return false;
                                        if (regime === 'TREND' && ['trend', 'trend_dip', 'trend_continuation', 'fibo_pullback', 'scalp'].includes(type)) return false;
                                        if (regime === 'RANGE' && ['range', 'reversion', 'reversion_extreme', 'scalp'].includes(type)) return false;
                                        return true;
                                    }) && (
                                            <div className="col-span-full text-center py-20 bg-gray-900/30 rounded-xl border border-gray-800 border-dashed">
                                                <Layers className="w-12 h-12 text-gray-700 mx-auto mb-4" />
                                                <h3 className="text-gray-400 font-bold">No Strategies for {data.regime}</h3>
                                                <p className="text-sm text-gray-600 mt-2">All active strategies are waiting for a regime change.</p>
                                            </div>
                                        )}
                                </>
                            ) : (
                                <div className="col-span-full text-center py-10">
                                    <p className="text-red-400">Invalid Data Format</p>
                                </div>
                            )}
                        </div>
                    </div>
                )}
            </div>
        </main>
    );
}
