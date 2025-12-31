'use client'

import { useState, useEffect } from 'react'
import useSWR from 'swr'
import axios from 'axios'
import dynamic from 'next/dynamic'
// import StatCard from '@/components/StatCard' // Unused
import StrategyMonitor from '@/components/StrategyMonitor'
import LiveLogs from '@/components/LiveLogs'
import ActiveTrade from '@/components/ActiveTrade'
import Settings from '@/components/Settings'
import TokenScanner from '@/components/TokenScanner'
import AICommentary from '@/components/AICommentary'

// NEW HEADER COMPONENT
import MarketCard from '@/components/MarketCard'

import GamificationWidget from '@/components/GamificationWidget'
import RecentSignals from '@/components/RecentSignals'
import { Activity, Zap, TrendingUp, BarChart2, Terminal } from 'lucide-react'

// OPTIMIZATION: Dynamic import for heavy Chart component
const Chart = dynamic(() => import('@/components/Chart'), {
    ssr: false,
    loading: () => (
        <div className="w-full h-[400px] bg-white/5 border border-white/10 rounded-2xl overflow-hidden p-4 animate-pulse">
            <div className="flex items-center justify-center h-full">
                <div className="text-center">
                    <div className="w-12 h-12 border-4 border-blue-500 border-t-transparent rounded-full animate-spin mx-auto mb-4"></div>
                    <p className="text-gray-400 text-sm">Loading chart...</p>
                </div>
            </div>
        </div>
    )
})


const API_URL = ''
const fetcher = (url: string) => axios.get(url).then(res => res.data)

const swrConfig = {
    refreshInterval: 2000,
    dedupingInterval: 1500,
    revalidateOnFocus: false,
    revalidateOnReconnect: false,
}

export default function V2Dashboard() {
    const [activeTab, setActiveTab] = useState('overview')

    const { data: status } = useSWR(`${API_URL}/api/status`, fetcher, swrConfig)
    const { data: marketData } = useSWR(`${API_URL}/api/market/data`, fetcher, swrConfig)
    const { data: balance } = useSWR(`${API_URL}/api/balance`, fetcher, {
        ...swrConfig,
        refreshInterval: 5000
    })

    const { data: signalsData } = useSWR(`${API_URL}/api/signals`, fetcher, {
        ...swrConfig,
        refreshInterval: 3000
    })
    const manualSignals = signalsData?.signals?.filter((s: any) => s.manual_approval) || []


    return (
        <div className="min-h-screen bg-[#050505] text-white">
            {/* Header */}
            <header className="bg-black/40 backdrop-blur-lg border-b border-white/5 sticky top-0 z-50">
                {/* MANUAL ACTION BANNER */}
                {manualSignals.length > 0 && (
                    <div className="bg-orange-500/90 text-white px-4 py-2 text-center font-bold animate-pulse cursor-pointer hover:bg-orange-600 transition-colors backdrop-blur">
                        ⚠️ ACTION REQUIRED: {manualSignals.length} Trade Opportunity Waiting for Validation!
                        <span className="ml-2 text-sm font-normal opacity-90">(Check Signals below)</span>
                    </div>
                )}

                <div className="container mx-auto px-6 py-4">
                    <div className="flex items-center justify-between gap-4">
                        <div className="flex items-center gap-4">
                            <div>
                                <h1 className="text-2xl font-bold text-white flex items-center gap-2">
                                    <Zap className="text-blue-500 fill-blue-500/20" size={24} />
                                    HyperLiquid AI
                                </h1>
                                <p className="text-xs text-gray-500 font-mono mt-1">NOVA BOT • v2.0</p>
                            </div>
                        </div>

                        <div className="flex items-center gap-3">
                            {/* Gamification */}
                            <div className="hidden md:block">
                                <GamificationWidget />
                            </div>

                            {/* Status Pill */}
                            <div className={`px-3 py-1.5 rounded-full text-xs font-bold border ${status?.is_running
                                ? 'bg-green-500/10 text-green-400 border-green-500/20'
                                : 'bg-gray-800/50 text-gray-400 border-gray-700/50'
                                }`}>
                                <div className="flex items-center gap-2">
                                    <span className={`w-2 h-2 rounded-full ${status?.is_running ? 'bg-green-500 animate-pulse' : 'bg-gray-500'}`}></span>
                                    {status?.is_running ? 'ONLINE' : 'OFFLINE'}
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </header>

            <div className="container mx-auto px-6 py-8 space-y-6">

                {/* Main Grid */}
                <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">

                    {/* LEFT COLUMN: Chart, MarketCard, & Tabs (Span 2) */}
                    <div className="lg:col-span-2 space-y-6">

                        {/* CHART SECTION */}
                        <div className="bg-black/40 backdrop-blur border border-white/5 rounded-xl overflow-hidden shadow-2xl shadow-black/50">
                            {/* Tabs */}
                            <div className="flex border-b border-white/5 overflow-x-auto">
                                {[
                                    { id: 'overview', label: 'Price Chart', icon: Activity },
                                    { id: 'strategies', label: 'Strategies', icon: TrendingUp },
                                    { id: 'signals', label: 'Signals', icon: Zap },
                                    { id: 'scanner', label: 'Scanner', icon: BarChart2 },
                                    { id: 'ai', label: 'AI Analysis', icon: Zap },
                                    { id: 'logs', label: 'System Logs', icon: Terminal },
                                ].map((tab) => (
                                    <button
                                        key={tab.id}
                                        onClick={() => setActiveTab(tab.id)}
                                        className={`flex-1 min-w-[120px] py-4 text-sm font-bold flex items-center justify-center gap-2 transition-all ${activeTab === tab.id
                                            ? 'text-blue-400 border-b-2 border-blue-500 bg-white/[0.02]'
                                            : 'text-gray-500 hover:text-gray-300 hover:bg-white/[0.01]'
                                            }`}
                                    >
                                        <tab.icon size={16} className={activeTab === tab.id ? 'text-blue-400' : 'text-gray-500'} />
                                        {tab.label}
                                    </button>
                                ))}
                            </div>

                            <div className="p-0">
                                {activeTab === 'overview' && (
                                    <div className="p-6">
                                        <Chart
                                            symbol={status?.active_symbol || 'BTC'}
                                            strategy={marketData?.active_strategies?.[0]?.replace(/ /g, '') || 'ScalpEmaRsi'}
                                        />

                                        {/* MARKET DATA CARD - Directly below Chart in Overview Tab */}
                                        <div className="mt-6">
                                            <MarketCard
                                                symbol={status?.active_symbol || 'BTC'}
                                                price={marketData?.price}
                                                regime={marketData?.regime}
                                                rsi={marketData?.rsi}
                                                adx={marketData?.adx}
                                                atr={marketData?.atr}
                                                volume_24h={marketData?.volume_24h}
                                                open_interest={marketData?.open_interest}
                                                trends={marketData?.trends}
                                            />
                                        </div>
                                    </div>
                                )}

                                {activeTab === 'strategies' && (
                                    <div className="p-6">
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
                                            hideHeader={true}
                                            embedded={true}
                                        />
                                    </div>
                                )}

                                {activeTab === 'signals' && <div className="p-6"><RecentSignals hideHeader={true} embedded={true} /></div>}
                                {activeTab === 'scanner' && <div className="p-6"><TokenScanner hideHeader={true} /></div>}
                                {activeTab === 'ai' && <div className="p-6"><AICommentary symbol={status?.active_symbol || 'BTC'} /></div>}
                                {activeTab === 'logs' && (
                                    <div className="p-6 h-[600px]">
                                        <LiveLogs embedded={true} hideHeader={true} />
                                    </div>
                                )}
                            </div>
                        </div>
                    </div>

                    {/* RIGHT COLUMN: Active Trade Only */}
                    <div className="space-y-6">
                        <div className="bg-black/40 backdrop-blur border border-white/5 rounded-xl overflow-hidden p-6">
                            <ActiveTrade embedded={true} />
                        </div>
                    </div>

                </div>
            </div>

            {/* Settings */}
            <div className="container mx-auto px-6 mb-8">
                <Settings />
            </div>
        </div>
    )
}
