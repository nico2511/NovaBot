'use client'

import { useState, useEffect } from 'react'
import useSWR from 'swr'
import axios from 'axios'
import StatCard from '@/components/StatCard'
import StrategyMonitor from '@/components/StrategyMonitor'
import Chart from '@/components/Chart'
import TradeHistory from '@/components/TradeHistory'
import LiveLogs from '@/components/LiveLogs'
import ActiveTrade from '@/components/ActiveTrade'
import Settings from '@/components/Settings'

const API_URL = ''

const fetcher = (url: string) => axios.get(url).then(res => res.data)

export default function Home() {
    const { data: status } = useSWR(`${API_URL}/api/status`, fetcher, { refreshInterval: 2000 })
    const { data: marketData } = useSWR(`${API_URL}/api/market/data`, fetcher, { refreshInterval: 2000 })
    const { data: balance } = useSWR(`${API_URL}/api/balance`, fetcher, { refreshInterval: 5000 })

    const toggleEngine = async () => {
        const endpoint = status?.is_running ? '/api/engine/stop' : '/api/engine/start'
        await axios.post(`${API_URL}${endpoint}`)
    }

    const toggleTrading = async () => {
        const endpoint = status?.trading_enabled ? '/api/trading/disable' : '/api/trading/enable'
        await axios.post(`${API_URL}${endpoint}`)
    }

    return (
        <div className="min-h-screen bg-background text-white">
            {/* Header */}
            <header className="bg-gradient-to-r from-surface/95 to-surface/80 backdrop-blur-lg border-b border-border/30 sticky top-0 z-50">
                <div className="container mx-auto px-6 py-4">
                    <div className="flex items-center justify-between">
                        <div>
                            <h1 className="text-2xl font-bold bg-gradient-to-r from-primary to-blue-400 bg-clip-text text-transparent">
                                ⚡ HyperLiquid AI Trader
                            </h1>
                            <p className="text-sm text-gray-400 mt-1">Advanced algorithmic trading with AI-powered strategies</p>
                        </div>
                        <div className="flex items-center gap-4">
                            <div className={`px-4 py-2 rounded-full text-sm font-semibold ${status?.is_running
                                ? 'bg-success/20 text-success border border-success/30'
                                : 'bg-gray-700/50 text-gray-400 border border-gray-600/30'
                                }`}>
                                {status?.is_running ? '🟢 LIVE' : '⚪ OFFLINE'}
                            </div>
                        </div>
                    </div>
                </div>
            </header>

            {/* Main Content */}
            <main className="container mx-auto px-6 py-8">
                {/* Stats Grid */}
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-4 mb-8">
                    <StatCard
                        icon="💰"
                        label="Price"
                        value={marketData?.price ? `$${marketData.price.toLocaleString()}` : '--'}
                        delta={marketData?.symbol || 'BTC'}
                        color="blue"
                    />
                    <StatCard
                        icon="🎯"
                        label="Strategies"
                        value={marketData?.active_strategies?.length || 0}
                        delta="Active"
                        color="purple"
                    />
                    <StatCard
                        icon="📊"
                        label="Regime"
                        value={marketData?.regime || 'UNKNOWN'}
                        delta={`ADX ${marketData?.adx?.toFixed(1) || '0'}`}
                        color={marketData?.regime === 'TREND' ? 'green' : 'orange'}
                    />
                    <StatCard
                        icon="⚙️"
                        label="Mode"
                        value={status?.execution_mode?.includes('Auto') ? 'Auto' : 'Manual'}
                        delta={status?.trading_enabled ? 'Live' : 'Paper'}
                        color={status?.trading_enabled ? 'green' : 'orange'}
                    />
                    <StatCard
                        icon="💵"
                        label="Balance"
                        value={balance?.total_equity ? `$${balance.total_equity.toFixed(2)}` : '--'}
                        delta="USDC"
                        color="cyan"
                    />
                </div>

                {/* Controls */}
                <div className="bg-surface/50 backdrop-blur border border-border/30 rounded-2xl p-6 mb-8">
                    <h3 className="text-lg font-semibold mb-4">Controls</h3>
                    <div className="flex gap-4">
                        <button
                            onClick={toggleEngine}
                            className={`px-6 py-3 rounded-lg font-semibold transition-all ${status?.is_running
                                ? 'bg-error/20 hover:bg-error/30 text-error border border-error/30'
                                : 'bg-success/20 hover:bg-success/30 text-success border border-success/30'
                                }`}
                        >
                            {status?.is_running ? '⏸ Stop Engine' : '▶️ Start Engine'}
                        </button>
                        <button
                            onClick={toggleTrading}
                            className={`px-6 py-3 rounded-lg font-semibold transition-all ${status?.trading_enabled
                                ? 'bg-warning/20 hover:bg-warning/30 text-warning border border-warning/30'
                                : 'bg-primary/20 hover:bg-primary/30 text-primary border border-primary/30'
                                }`}
                        >
                            {status?.trading_enabled ? '🔴 Disable Trading' : '🟢 Enable Trading'}
                        </button>
                    </div>
                </div>

                {/* Chart */}
                <div className="bg-surface/50 backdrop-blur border border-border/30 rounded-2xl p-6 mb-8">
                    <h3 className="text-lg font-semibold mb-4">📊 Market Data</h3>
                    <h3 className="text-lg font-semibold mb-4">📊 Market Data</h3>
                    <Chart
                        symbol={status?.active_symbol || 'BTC'}
                        strategy={marketData?.active_strategies?.[0]?.replace(/ /g, '') || 'ScalpEmaRsi'}
                    />
                </div>

                {/* Active Trade & Logs Grid */}
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 mb-8">
                    <ActiveTrade />
                    <LiveLogs />
                </div>

                {/* Strategy Monitor */}
                <StrategyMonitor
                    strategies={marketData?.active_strategies || []}
                    regime={marketData?.regime || 'UNKNOWN'}
                    rsi={marketData?.rsi || 0}
                    atr={marketData?.atr || 0}
                    adx={marketData?.adx || 0}
                    ema_20={marketData?.ema_20}
                    ema_50={marketData?.ema_50}
                    bb={marketData?.bb}
                />

                {/* Trade History */}
                <div className="mt-8">
                    <TradeHistory />
                </div>
            </main>

            {/* Settings Panel */}
            <Settings />
        </div>
    )
}
