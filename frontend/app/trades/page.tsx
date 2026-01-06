'use client'

import React from 'react'
import Link from 'next/link'
import { useTradeHistory } from '@/hooks/useTradeHistory'
import TradesTable from '@/components/trades/TradesTable'
import PnLChart from '@/components/trades/PnLChart'
import SourceSelector from '@/components/trades/SourceSelector'

export default function TradesPage() {
    const { trades, source, setSource, isLoading, stats } = useTradeHistory()

    return (
        <div className="min-h-screen bg-[#050505] text-white p-6">
            <div className="max-w-7xl mx-auto space-y-6">

                {/* Header */}
                <div className="flex items-center justify-between">
                    <div>
                        <h1 className="text-3xl font-bold bg-gradient-to-r from-blue-400 to-purple-400 bg-clip-text text-transparent">
                            Trade History
                        </h1>
                        <p className="text-gray-400 text-sm">Performance Analysis & Logs</p>
                    </div>
                    <div className="flex gap-4 items-center">
                        <SourceSelector value={source} onChange={setSource} />
                        <Link href="/" className="px-4 py-2 bg-white/5 hover:bg-white/10 rounded-lg text-sm transition-colors border border-white/10">
                            ← Back
                        </Link>
                    </div>
                </div>

                {/* KPI Cards (Derived from Hook Stats) */}
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                    <StatCard label="Total PnL" value={`$${stats.totalPnL.toFixed(2)}`} color={stats.totalPnL >= 0 ? 'text-green-400' : 'text-red-400'} />
                    <StatCard label="Win Rate" value={`${stats.winRate.toFixed(1)}%`} color={stats.winRate >= 50 ? 'text-blue-400' : 'text-yellow-500'} />
                    <StatCard label="Profit Factor" value={stats.profitFactor === Infinity ? '∞' : stats.profitFactor.toFixed(2)} />
                    <StatCard label="Total Trades" value={stats.totalTrades} />
                </div>

                {/* PnL Chart */}
                <div className="bg-white/5 border border-white/10 rounded-xl p-6 h-[400px]">
                    <h3 className="text-sm font-bold text-gray-400 mb-4 uppercase tracking-wider">Cumulative Performance</h3>
                    <PnLChart trades={trades} />
                </div>

                {/* Trades Table */}
                <div className="bg-white/5 border border-white/10 rounded-xl overflow-hidden">
                    <div className="p-4 border-b border-white/5">
                        <h3 className="text-sm font-bold text-gray-400 uppercase tracking-wider">Execution Log</h3>
                    </div>
                    <TradesTable trades={trades} loading={isLoading} />
                </div>

            </div>
        </div>
    )
}

function StatCard({ label, value, color = 'text-white' }: { label: string, value: string | number, color?: string }) {
    return (
        <div className="bg-white/5 backdrop-blur border border-white/10 p-4 rounded-xl">
            <div className="text-gray-400 text-xs uppercase tracking-wider mb-1">{label}</div>
            <div className={`text-2xl font-bold ${color}`}>
                {value}
            </div>
        </div>
    )
}
