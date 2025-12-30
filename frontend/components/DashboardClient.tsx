'use client'

import { useState, useEffect } from 'react'
import useSWR from 'swr'
import axios from 'axios'
import dynamic from 'next/dynamic'
import StatCard from '@/components/StatCard'
import StrategyMonitor from '@/components/StrategyMonitor'
import LiveLogs from '@/components/LiveLogs'
import ActiveTrade from '@/components/ActiveTrade'
import Settings from '@/components/Settings'
import TokenScanner from '@/components/TokenScanner'
import AICommentary from '@/components/AICommentary'

import CryptoWeather from '@/components/CryptoWeather'
import GamificationWidget from '@/components/GamificationWidget'
import RecentSignals from '@/components/RecentSignals'

// OPTIMIZATION: Dynamic import for heavy Chart component (lightweight-charts = 300KB)
// This prevents blocking the main bundle and improves FCP/LCP
const Chart = dynamic(() => import('@/components/Chart'), {
    ssr: false,
    loading: () => (
        <div className="w-full h-[400px] bg-surface/50 border border-border/30 rounded-2xl overflow-hidden p-4 animate-pulse">
            <div className="flex items-center justify-center h-full">
                <div className="text-center">
                    <div className="w-12 h-12 border-4 border-primary border-t-transparent rounded-full animate-spin mx-auto mb-4"></div>
                    <p className="text-gray-400 text-sm">Loading chart...</p>
                </div>
            </div>
        </div>
    )
})


const API_URL = ''
const fetcher = (url: string) => axios.get(url).then(res => res.data)

// OPTIMIZATION: SWR configuration to reduce API waterfalls
const swrConfig = {
    refreshInterval: 2000,
    dedupingInterval: 1500,  // Dedupe requests within 1.5s
    revalidateOnFocus: false,  // Don't refetch on window focus
    revalidateOnReconnect: false,  // Don't refetch on reconnect
}

export default function DashboardClient() {
    const [activeTab, setActiveTab] = useState('overview')

    // OPTIMIZATION: Parallel API calls with optimized config
    const { data: status } = useSWR(`${API_URL}/api/status`, fetcher, swrConfig)
    const { data: marketData } = useSWR(`${API_URL}/api/market/data`, fetcher, swrConfig)
    const { data: balance } = useSWR(`${API_URL}/api/balance`, fetcher, {
        ...swrConfig,
        refreshInterval: 5000  // Less frequent for balance
    })

    // Check for manual signals
    const { data: signalsData } = useSWR(`${API_URL}/api/signals`, fetcher, {
        ...swrConfig,
        refreshInterval: 3000
    })
    const manualSignals = signalsData?.signals?.filter((s: any) => s.manual_approval) || []

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
                {/* MANUAL ACTION BANNER */}
                {manualSignals.length > 0 && (
                    <div className="bg-orange-500 text-white px-4 py-2 text-center font-bold animate-pulse cursor-pointer hover:bg-orange-600 transition-colors">
                        ⚠️ ACTION REQUIRED: {manualSignals.length} Trade Opportunity Waiting for Validation!
                        <span className="ml-2 text-sm font-normal opacity-90">(Check Signals below)</span>
                    </div>
                )}

                <div className="container mx-auto px-4 py-3">
                    {/* Top Row: Title + Weather + Gamification */}
                    <div className="flex items-center justify-between gap-4 mb-3">
                        <div className="flex items-center gap-4 flex-1 min-w-0">
                            <div className="min-w-0">
                                <h1 className="text-xl lg:text-2xl font-bold bg-gradient-to-r from-primary to-blue-400 bg-clip-text text-transparent truncate">
                                    ⚡ HyperLiquid AI Trader
                                </h1>
                                <p className="text-xs text-gray-400 mt-0.5 hidden sm:block">Advanced algorithmic trading</p>
                            </div>

                            {/* Weather Widget - Hidden on small screens */}
                            <div className="hidden xl:block">
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

                        {/* Right Side: Gamification (Compact) + Status */}
                        <div className="flex items-center gap-3">
                            {/* Gamification Compact - Visible on medium+ screens */}
                            <div className="hidden md:flex items-center gap-2 bg-surface/60 rounded-lg px-3 py-2 border border-border/20">
                                <GamificationWidget />
                            </div>

                            {/* Navigation */}
                            <a href="/gamification" className="p-2 hover:bg-white/10 rounded-lg transition-colors group" title="Gamification">
                                <span className="text-xl group-hover:scale-110 transition-transform">🎮</span>
                            </a>
                            <a href="/trades" className="p-2 hover:bg-white/10 rounded-lg transition-colors group" title="Trade Analysis">
                                <span className="text-xl group-hover:scale-110 transition-transform">📊</span>
                            </a>

                            {/* Status Pill */}
                            <div className={`px-3 py-1.5 rounded-full text-xs font-semibold whitespace-nowrap ${status?.is_running
                                ? 'bg-success/20 text-success border border-success/30'
                                : 'bg-gray-700/50 text-gray-400 border border-gray-600/30'
                                }`}>
                                {status?.is_running ? '🟢 LIVE' : '⚪ OFF'}
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
                    <div className="flex gap-2 mb-6 border-b border-border/30 pb-4 overflow-x-auto">
                        <button
                            onClick={() => setActiveTab('overview')}
                            className={`px-4 py-2 rounded-lg font-medium transition-all whitespace-nowrap ${activeTab === 'overview'
                                ? 'bg-primary text-white'
                                : 'text-gray-400 hover:text-white hover:bg-surface/50'
                                }`}
                        >
                            📊 Overview
                        </button>
                        <button
                            onClick={() => setActiveTab('strategies')}
                            className={`px-4 py-2 rounded-lg font-medium transition-all whitespace-nowrap ${activeTab === 'strategies'
                                ? 'bg-primary text-white'
                                : 'text-gray-400 hover:text-white hover:bg-surface/50'
                                }`}
                        >
                            📈 Strategies
                        </button>
                        <button
                            onClick={() => setActiveTab('signals')}
                            className={`px-4 py-2 rounded-lg font-medium transition-all whitespace-nowrap ${activeTab === 'signals'
                                ? 'bg-primary text-white'
                                : 'text-gray-400 hover:text-white hover:bg-surface/50'
                                }`}
                        >
                            📡 Signals
                        </button>
                        <button
                            onClick={() => setActiveTab('scanner')}
                            className={`px-4 py-2 rounded-lg font-medium transition-all whitespace-nowrap ${activeTab === 'scanner'
                                ? 'bg-primary text-white'
                                : 'text-gray-400 hover:text-white hover:bg-surface/50'
                                }`}
                        >
                            🔍 Scanner
                        </button>
                        <button
                            onClick={() => setActiveTab('ai')}
                            className={`px-4 py-2 rounded-lg font-medium transition-all whitespace-nowrap ${activeTab === 'ai'
                                ? 'bg-primary text-white'
                                : 'text-gray-400 hover:text-white hover:bg-surface/50'
                                }`}
                        >
                            🤖 AI Analysis
                        </button>
                    </div>


                    {/* Tab Content */}
                    {activeTab === 'overview' && (
                        <Chart
                            symbol={status?.active_symbol || 'BTC'}
                            strategy={marketData?.active_strategies?.[0]?.replace(/ /g, '') || 'ScalpEmaRsi'}
                        />
                    )}

                    {activeTab === 'strategies' && (
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
                    )}

                    {activeTab === 'signals' && (
                        <RecentSignals />
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
            </main >

            {/* Settings Panel */}
            < Settings />
        </>
    )
}
