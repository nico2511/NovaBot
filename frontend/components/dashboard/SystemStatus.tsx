'use client'

import { useEffect, useState } from 'react'
import useSWR from 'swr'
import axios from 'axios'
import { Activity, DollarSign, TrendingUp, Zap } from 'lucide-react'

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8001'
const fetcher = (url: string) => axios.get(url).then(res => res.data)

interface BalanceData {
    total_equity: number
    available: number
    margin: number
}

interface StatusData {
    is_running: boolean
    trading_enabled: boolean
    active_symbol: string
    execution_mode: string
}

interface GamificationData {
    level: string
    max_leverage: number
}

export default function SystemStatus() {
    const { data: status } = useSWR<StatusData>(`${API_URL}/api/status`, fetcher, { refreshInterval: 2000, keepPreviousData: true })
    const { data: balance } = useSWR<BalanceData>(`${API_URL}/api/balance`, fetcher, { refreshInterval: 5000, keepPreviousData: true })
    const { data: gamStatus } = useSWR<{ gamification: GamificationData }>(`${API_URL}/api/gamification_status`, fetcher, { refreshInterval: 10000, keepPreviousData: true })

    const [pnl, setPnl] = useState(0)
    const [pnlPercent, setPnlPercent] = useState(0)

    // Calculate PnL (simple calculation based on margin)
    useEffect(() => {
        if (balance) {
            const unrealizedPnl = balance.total_equity - balance.available - balance.margin
            setPnl(unrealizedPnl)
            if (balance.total_equity > 0) {
                setPnlPercent((unrealizedPnl / balance.total_equity) * 100)
            }
        }
    }, [balance])

    const formatCurrency = (value: number) => {
        return new Intl.NumberFormat('en-US', {
            style: 'currency',
            currency: 'USD',
            minimumFractionDigits: 2,
            maximumFractionDigits: 2
        }).format(value)
    }

    return (
        <div className="bg-black/40 backdrop-blur border border-white/5 rounded-xl p-4">
            <h3 className="text-xs font-bold text-gray-400 uppercase tracking-wider mb-4 flex items-center gap-2">
                <Activity size={14} className="text-blue-500" />
                BOT SYSTEM STATE
            </h3>

            {/* Status Grid */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4">
                {/* Engine Status */}
                <div className="bg-white/5 rounded-lg p-3 border border-white/5">
                    <div className="flex items-center gap-2 mb-1">
                        <Zap size={12} className="text-gray-400" />
                        <span className="text-[10px] text-gray-500 uppercase">Engine Status</span>
                    </div>
                    <div className={`text-sm font-bold ${status?.is_running ? 'text-green-400' : 'text-gray-400'}`}>
                        {status?.is_running ? 'RUNNING' : 'STOPPED'}
                    </div>
                </div>

                {/* Trading Status */}
                <div className="bg-white/5 rounded-lg p-3 border border-white/5">
                    <div className="flex items-center gap-2 mb-1">
                        <Activity size={12} className="text-gray-400" />
                        <span className="text-[10px] text-gray-500 uppercase">Trading</span>
                    </div>
                    <div className={`text-sm font-bold ${status?.trading_enabled ? 'text-yellow-400' : 'text-red-400'}`}>
                        {status?.trading_enabled ? 'DISABLED' : 'ENABLED'}
                    </div>
                </div>

                {/* Active Symbol */}
                <div className="bg-white/5 rounded-lg p-3 border border-white/5">
                    <div className="flex items-center gap-2 mb-1">
                        <TrendingUp size={12} className="text-gray-400" />
                        <span className="text-[10px] text-gray-500 uppercase">Active Symbol</span>
                    </div>
                    <div className="text-sm font-bold text-blue-400">
                        {status?.active_symbol || 'BTC'}
                    </div>
                </div>

                {/* Mode */}
                <div className="bg-white/5 rounded-lg p-3 border border-white/5">
                    <div className="flex items-center gap-2 mb-1">
                        <Zap size={12} className="text-gray-400" />
                        <span className="text-[10px] text-gray-500 uppercase">Mode</span>
                    </div>
                    <div className="text-sm font-bold text-purple-400">
                        {status?.execution_mode || 'LIVE'}
                    </div>
                </div>
            </div>

            {/* Service Health */}
            <div className="mb-4">
                <h4 className="text-[10px] text-gray-500 uppercase mb-2">SERVICE HEALTH</h4>
                <div className="grid grid-cols-2 gap-2">
                    <div className="flex items-center justify-between bg-white/5 rounded px-3 py-2 border border-white/5">
                        <span className="text-xs text-gray-400">Hyperliquid API</span>
                        <span className="px-2 py-0.5 bg-green-500/20 text-green-400 text-[10px] font-bold rounded border border-green-500/30">
                            CONNECTED
                        </span>
                    </div>
                    <div className="flex items-center justify-between bg-white/5 rounded px-3 py-2 border border-white/5">
                        <span className="text-xs text-gray-400">Scanner Engine</span>
                        <span className="px-2 py-0.5 bg-green-500/20 text-green-400 text-[10px] font-bold rounded border border-green-500/30">
                            CONNECTED
                        </span>
                    </div>
                </div>
            </div>

            {/* Account Metrics */}
            <div className="mb-4">
                <h4 className="text-[10px] text-gray-500 uppercase mb-2 flex items-center gap-2">
                    <DollarSign size={12} />
                    ACCOUNT METRICS
                </h4>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                    {/* Total Equity */}
                    <div className="bg-white/5 rounded-lg p-3 border border-white/5">
                        <div className="text-[10px] text-gray-500 mb-1">$ TOTAL EQUITY</div>
                        <div className="text-sm font-bold text-green-400">
                            {formatCurrency(balance?.total_equity || 0)}
                        </div>
                        <div className="text-[9px] text-gray-600 mt-0.5">
                            {((balance?.total_equity || 0) * 100).toFixed(2)}%
                        </div>
                    </div>

                    {/* Unrealized PnL */}
                    <div className="bg-white/5 rounded-lg p-3 border border-white/5">
                        <div className="text-[10px] text-gray-500 mb-1">UNREALIZED PNL</div>
                        <div className={`text-sm font-bold ${pnl >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                            {formatCurrency(pnl)}
                        </div>
                        <div className={`text-[9px] mt-0.5 ${pnlPercent >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                            {pnlPercent >= 0 ? '+' : ''}{pnlPercent.toFixed(2)}%
                        </div>
                    </div>

                    {/* Realized Today */}
                    <div className="bg-white/5 rounded-lg p-3 border border-white/5">
                        <div className="text-[10px] text-gray-500 mb-1">REALIZED TODAY</div>
                        <div className="text-sm font-bold text-white">
                            {formatCurrency(0)}
                        </div>
                        <div className="text-[9px] text-gray-600 mt-0.5">
                            0.00%
                        </div>
                    </div>

                    {/* Leverage */}
                    <div className="bg-white/5 rounded-lg p-3 border border-white/5">
                        <div className="text-[10px] text-gray-500 mb-1">LEVERAGE</div>
                        <div className="text-sm font-bold text-yellow-400">
                            {gamStatus?.gamification?.max_leverage?.toFixed(2) || '0.00'}x
                        </div>
                    </div>
                </div>
            </div>

            {/* Gamification */}
            <div className="flex items-center justify-between bg-gradient-to-r from-purple-500/10 to-blue-500/10 rounded-lg p-3 border border-purple-500/20">
                <div className="flex items-center gap-3">
                    <div className="w-10 h-10 bg-purple-500/20 rounded-lg flex items-center justify-center border border-purple-500/30">
                        <Zap size={20} className="text-purple-400" />
                    </div>
                    <div>
                        <div className="text-[10px] text-gray-500 uppercase">GAMIFICATION</div>
                        <div className="text-sm font-bold text-white">
                            Level {gamStatus?.gamification?.level || 'Goblin'}
                        </div>
                    </div>
                </div>
                <div className="text-right">
                    <div className="text-[10px] text-gray-500">{gamStatus?.gamification?.max_leverage?.toFixed(2) || '0.00'}x Max</div>
                </div>
            </div>
        </div>
    )
}
