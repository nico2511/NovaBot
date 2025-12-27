'use client'

import { useState, useEffect } from 'react'
import useSWR from 'swr'
import axios from 'axios'
import dynamic from 'next/dynamic'
import StatCard from '@/components/StatCard'
import StrategyMonitor from '@/components/StrategyMonitor'
import TradeHistory from '@/components/TradeHistory'
import LiveLogs from '@/components/LiveLogs'
import ActiveTrade from '@/components/ActiveTrade'
import Settings from '@/components/Settings'
import TokenScanner from '@/components/TokenScanner'
import AICommentary from '@/components/AICommentary'

import CryptoWeather from '@/components/CryptoWeather'

// Dynamic import for heavy Chart component
const Chart = dynamic(() => import('@/components/Chart'), {
    ssr: false,
    loading: () => <div className="w-full h-[400px] bg-surface/50 animate-pulse rounded-2xl" />
})

const API_URL = ''
const fetcher = (url: string) => axios.get(url).then(res => res.data)

export default function DashboardClient() {
    const [activeTab, setActiveTab] = useState('overview')
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
        <>
            {/* Header */}
            <header className="bg-gradient-to-r from-surface/95 to-surface/80 backdrop-blur-lg border-b border-border/30 sticky top-0 z-50">
                <div className="container mx-auto px-6 py-4">
                    <div className="flex items-center justify-between">
                        <div className="flex items-center gap-8">
                            <div>
                                <h1 className="text-2xl font-bold bg-gradient-to-r from-primary to-blue-400 bg-clip-text text-transparent">
                                    ⚡ HyperLiquid AI Trader
                                </h1>
                                <p className="text-sm text-gray-400 mt-1">Advanced algorithmic trading with AI-powered strategies</p>
                            </div>

                            {/* Weather Widget */}
                            <div className="hidden md:block">
                                <CryptoWeather
                                    regime={marketData?.regime || 'UNKNOWN'}
                                    adx={marketData?.adx || 0}
                                    rsi={marketData?.rsi}
                                    ema_20={marketData?.ema_20}
                                    ema_50={marketData?.ema_50}
                                    atr={marketData?.atr}
                                    symbol={status?.active_symbol || 'BTC'}
                                />
                            </div>
                        </div>

                        <div className="flex items-center gap-6">
                            {/* NEW: Price & Balance in Header */}
                            <div className="flex gap-6 items-center">
                                <div className="text-right hidden sm:block">
                                    <div className="text-xs text-gray-400">Price ({marketData?.symbol || 'BTC'})</div>
                                    <div className="text-lg font-bold text-white">
                                        {marketData?.price ? `$${marketData.price.toLocaleString()}` : '--'}
                                    </div>
                                </div>
                                <div className="text-right hidden sm:block border-l border-white/10 pl-6">
                                    <div className="text-xs text-gray-400">Balance (USDC)</div>
                                    <div className="text-lg font-bold text-cyan-400">
                                        {balance?.total_equity ? `$${balance.total_equity.toFixed(2)}` : '--'}
                                    </div>
                                </div>
                            </div>

                            {/* Navigation */}
                            <a href="/trades" className="p-2 hover:bg-white/10 rounded-lg transition-colors group" title="Trade Analysis">
                                <span className="text-xl group-hover:scale-110 transition-transform">📊</span>
                            </a>

                            {/* Status Pill */}
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
            < main className="container mx-auto px-6 py-8" >
                {/* Stats Grid Removed as requested */}

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
                    {/* Tab Navigation */}
                    <div className="flex gap-2 mb-6 border-b border-border/30 pb-4">
                        <button
                            onClick={() => setActiveTab('overview')}
                            className={`px-4 py-2 rounded-lg font-medium transition-all ${activeTab === 'overview'
                                ? 'bg-primary text-white'
                                : 'text-gray-400 hover:text-white hover:bg-surface/50'
                                }`}
                        >
                            📊 Overview
                        </button>
                        <button
                            onClick={() => setActiveTab('scanner')}
                            className={`px-4 py-2 rounded-lg font-medium transition-all ${activeTab === 'scanner'
                                ? 'bg-primary text-white'
                                : 'text-gray-400 hover:text-white hover:bg-surface/50'
                                }`}
                        >
                            🔍 Scanner
                        </button>
                        <button
                            onClick={() => setActiveTab('ai')}
                            className={`px-4 py-2 rounded-lg font-medium transition-all ${activeTab === 'ai'
                                ? 'bg-primary text-white'
                                : 'text-gray-400 hover:text-white hover:bg-surface/50'
                                }`}
                        >
                            🤖 AI Commentary
                        </button>
                    </div>

                    {/* Tab Content */}
                    {activeTab === 'overview' && (
                        <Chart
                            symbol={status?.active_symbol || 'BTC'}
                            strategy={marketData?.active_strategies?.[0]?.replace(/ /g, '') || 'ScalpEmaRsi'}
                        />
                    )}

                    {activeTab === 'scanner' && (
                        <TokenScanner />
                    )}

                    {activeTab === 'ai' && (
                        <AICommentary symbol={status?.active_symbol || 'BTC'} />
                    )}
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
                    strategy_progress={marketData?.strategy_progress || {}}
                />

                {/* Trade History */}
                <div className="mt-8">
                    <TradeHistory />
                </div>
            </main >

            {/* Settings Panel */}
            < Settings />
        </>
    )
}
