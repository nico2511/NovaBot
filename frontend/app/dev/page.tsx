'use client'

import { useState } from 'react'
import useSWR from 'swr'
import axios from 'axios'
import { RefreshCw, Activity, TrendingUp, DollarSign, Zap } from 'lucide-react'

const API_URL = ''
const fetcher = (url: string) => axios.get(url).then(res => res.data)

export default function DevPage() {
    const { data, error, mutate } = useSWR(`${API_URL}/api/dev/diagnostics`, fetcher, {
        refreshInterval: 5000
    })

    if (error) {
        return (
            <div className="min-h-screen bg-[#050505] text-white p-8">
                <div className="max-w-7xl mx-auto">
                    <h1 className="text-3xl font-bold mb-4">⚠️ Error Loading Diagnostics</h1>
                    <pre className="bg-red-500/10 border border-red-500/30 rounded-lg p-4 text-red-400">
                        {error.message}
                    </pre>
                </div>
            </div>
        )
    }

    if (!data) {
        return (
            <div className="min-h-screen bg-[#050505] text-white flex items-center justify-center">
                <div className="text-center">
                    <div className="w-12 h-12 border-4 border-primary border-t-transparent rounded-full animate-spin mx-auto mb-4"></div>
                    <p className="text-gray-400">Loading diagnostics...</p>
                </div>
            </div>
        )
    }

    return (
        <div className="min-h-screen bg-[#050505] text-white p-8">
            <div className="max-w-7xl mx-auto">
                {/* Header */}
                <div className="flex items-center justify-between mb-8">
                    <div>
                        <h1 className="text-4xl font-bold mb-2">🔧 Dev Diagnostics</h1>
                        <p className="text-gray-400">Real-time Hyperliquid data & bot status</p>
                    </div>
                    <button
                        onClick={() => mutate()}
                        className="px-4 py-2 bg-primary/20 hover:bg-primary/30 border border-primary/50 rounded-lg flex items-center gap-2 transition-colors"
                    >
                        <RefreshCw size={16} />
                        Refresh
                    </button>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                    {/* Account Info */}
                    <div className="bg-black/40 backdrop-blur border border-border/30 rounded-xl p-6">
                        <div className="flex items-center gap-2 mb-4">
                            <DollarSign className="text-primary" size={20} />
                            <h2 className="text-xl font-bold">Account</h2>
                        </div>
                        <div className="space-y-3">
                            <div>
                                <div className="text-sm text-gray-400">Balance (USDC)</div>
                                <div className="text-2xl font-bold text-primary">
                                    ${data.account?.balance?.toFixed(2) || '0.00'}
                                </div>
                            </div>
                            <div className="grid grid-cols-2 gap-4">
                                <div>
                                    <div className="text-xs text-gray-400">Margin Used</div>
                                    <div className="text-lg font-mono">
                                        ${data.account?.margin_used?.toFixed(2) || '0.00'}
                                    </div>
                                </div>
                                <div>
                                    <div className="text-xs text-gray-400">Available</div>
                                    <div className="text-lg font-mono text-green-400">
                                        ${data.account?.available_margin?.toFixed(2) || '0.00'}
                                    </div>
                                </div>
                            </div>
                            <div className="grid grid-cols-2 gap-4 pt-2 border-t border-white/5">
                                <div>
                                    <div className="text-xs text-gray-400">Withdrawable</div>
                                    <div className="text-md font-mono text-blue-400">
                                        ${data.account?.withdrawable?.toFixed(2) || '0.00'}
                                    </div>
                                </div>
                                <div>
                                    <div className="text-xs text-gray-400">Leverage</div>
                                    <div className="text-md font-mono text-orange-400">
                                        {data.account?.account_leverage?.toFixed(2) || '0.00'}x
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>

                    {/* Active Positions */}
                    <div className="bg-black/40 backdrop-blur border border-border/30 rounded-xl p-6">
                        <div className="flex items-center gap-2 mb-4">
                            <Activity className="text-blue-400" size={20} />
                            <h2 className="text-xl font-bold">Active Positions</h2>
                        </div>
                        {data.positions && data.positions.length > 0 ? (
                            <div className="space-y-3">
                                {data.positions.map((pos: any, i: number) => (
                                    <div key={i} className="border border-border/30 rounded-lg p-3 scrollbar-none overflow-y-auto max-h-[200px]">
                                        <div className="flex items-center justify-between mb-2">
                                            <span className="font-bold">{pos.symbol}</span>
                                            <span className={`text-sm px-2 py-0.5 rounded ${pos.side === 'BUY' ? 'bg-green-500/20 text-green-400' : 'bg-red-500/20 text-red-400'}`}>
                                                {pos.side}
                                            </span>
                                        </div>
                                        <div className="grid grid-cols-2 gap-2 text-sm">
                                            <div>
                                                <div className="text-xs text-gray-400">Size</div>
                                                <div className="font-mono">{pos.size}</div>
                                            </div>
                                            <div>
                                                <div className="text-xs text-gray-400">Entry</div>
                                                <div className="font-mono">${pos.entry_price?.toFixed(2)}</div>
                                            </div>
                                            <div>
                                                <div className="text-xs text-gray-400">Lev.</div>
                                                <div className="font-mono">{pos.leverage}x</div>
                                            </div>
                                            <div>
                                                <div className="text-xs text-gray-400">P&L</div>
                                                <div className={`font-mono ${(pos.pnl || 0) >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                                                    ${pos.pnl?.toFixed(2)}
                                                </div>
                                            </div>
                                        </div>
                                    </div>
                                ))}
                            </div>
                        ) : (
                            <div className="text-center text-gray-500 py-8">
                                No active positions
                            </div>
                        )}
                    </div>

                    {/* Symbol Data */}
                    <div className="bg-black/40 backdrop-blur border border-border/30 rounded-xl p-6">
                        <div className="flex items-center gap-2 mb-4">
                            <TrendingUp className="text-yellow-400" size={20} />
                            <h2 className="text-xl font-bold">Symbol Data</h2>
                        </div>
                        <div className="space-y-3">
                            <div>
                                <div className="text-sm text-gray-400">Symbol</div>
                                <div className="text-2xl font-bold">{data.symbol?.name || 'N/A'}</div>
                            </div>
                            <div className="grid grid-cols-2 gap-4">
                                <div>
                                    <div className="text-xs text-gray-400">Price</div>
                                    <div className="text-lg font-mono">
                                        ${data.symbol?.price?.toFixed(2) || '0.00'}
                                    </div>
                                </div>
                                <div>
                                    <div className="text-xs text-gray-400">24h Volume</div>
                                    <div className="text-lg font-mono">
                                        ${(data.symbol?.volume_24h / 1e6)?.toFixed(1) || '0'}M
                                    </div>
                                </div>
                                <div>
                                    <div className="text-xs text-gray-400">Funding Rate</div>
                                    <div className="text-lg font-mono">
                                        {(data.symbol?.funding_rate * 100)?.toFixed(4) || '0'}%
                                    </div>
                                </div>
                                <div>
                                    <div className="text-xs text-gray-400">Open Interest</div>
                                    <div className="text-lg font-mono">
                                        ${(data.symbol?.open_interest / 1e6)?.toFixed(1) || '0'}M
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>

                    {/* Portfolio Stats */}
                    <div className="bg-black/40 backdrop-blur border border-border/30 rounded-xl p-6">
                        <div className="flex items-center gap-2 mb-4">
                            <Zap className="text-purple-400" size={20} />
                            <h2 className="text-xl font-bold">Portfolio</h2>
                        </div>
                        <div className="space-y-3">
                            <div>
                                <div className="text-sm text-gray-400">Total Value</div>
                                <div className="text-2xl font-bold">
                                    ${data.portfolio?.total_value?.toFixed(2) || '0.00'}
                                </div>
                            </div>
                            <div className="grid grid-cols-2 gap-4">
                                <div>
                                    <div className="text-xs text-gray-400">Unrealized P&L</div>
                                    <div className={`text-lg font-mono ${(data.portfolio?.unrealized_pnl || 0) >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                                        ${data.portfolio?.unrealized_pnl?.toFixed(2) || '0.00'}
                                        <span className="text-xs ml-1">({data.portfolio?.roi_unrealized_pct?.toFixed(2)}%)</span>
                                    </div>
                                </div>
                                <div>
                                    <div className="text-xs text-gray-400">Realized (Today)</div>
                                    <div className={`text-lg font-mono ${(data.portfolio?.realized_pnl_today || 0) >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                                        ${data.portfolio?.realized_pnl_today?.toFixed(2) || '0.00'}
                                        <span className="text-xs ml-1">({data.portfolio?.roi_today_pct?.toFixed(2)}%)</span>
                                    </div>
                                </div>
                            </div>
                            <div className="grid grid-cols-2 gap-4 pt-2 border-t border-white/5">
                                <div>
                                    <div className="text-xs text-gray-400">Notional Pos.</div>
                                    <div className="text-sm font-mono text-gray-300">
                                        ${data.portfolio?.total_notional_position?.toFixed(2) || '0.00'}
                                    </div>
                                </div>
                                <div>
                                    <div className="text-xs text-gray-400">Fees (10 trades)</div>
                                    <div className="text-sm font-mono text-gray-300">
                                        ${data.portfolio?.total_fees_paid_recent?.toFixed(4) || '0.0000'}
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>

                    {/* API Status */}
                    <div className="bg-black/40 backdrop-blur border border-border/30 rounded-xl p-6">
                        <div className="flex items-center gap-2 mb-4">
                            <Activity className="text-green-400" size={20} />
                            <h2 className="text-xl font-bold">API Status</h2>
                        </div>
                        <div className="space-y-3">
                            <div className="flex items-center justify-between">
                                <span className="text-sm text-gray-400">Hyperliquid</span>
                                <span className={`px-2 py-1 rounded text-xs font-bold ${data.api_status?.hyperliquid_connected ? 'bg-green-500/20 text-green-400' : 'bg-red-500/20 text-red-400'}`}>
                                    {data.api_status?.hyperliquid_connected ? '🟢 Connected' : '🔴 Disconnected'}
                                </span>
                            </div>
                            <div>
                                <div className="text-xs text-gray-400">Last API Call</div>
                                <div className="text-sm font-mono">
                                    {data.api_status?.last_call || 'N/A'}
                                </div>
                            </div>
                            <div>
                                <div className="text-xs text-gray-400">Rate Limit</div>
                                <div className="text-sm font-mono">
                                    {data.api_status?.rate_limit_remaining || 'N/A'} / {data.api_status?.rate_limit_total || 'N/A'}
                                </div>
                            </div>
                        </div>
                    </div>

                    {/* Bot State */}
                    <div className="bg-black/40 backdrop-blur border border-border/30 rounded-xl p-6">
                        <div className="flex items-center gap-2 mb-4">
                            <Activity className="text-orange-400" size={20} />
                            <h2 className="text-xl font-bold">Bot State</h2>
                        </div>
                        <div className="space-y-3">
                            <div className="flex items-center justify-between">
                                <span className="text-sm text-gray-400">Trading Enabled</span>
                                <span className={`px-2 py-1 rounded text-xs font-bold ${data.bot_state?.trading_enabled ? 'bg-green-500/20 text-green-400' : 'bg-red-500/20 text-red-400'}`}>
                                    {data.bot_state?.trading_enabled ? '✅ YES' : '❌ NO'}
                                </span>
                            </div>
                            <div className="flex items-center justify-between">
                                <span className="text-sm text-gray-400">Engine Running</span>
                                <span className={`px-2 py-1 rounded text-xs font-bold ${data.bot_state?.is_running ? 'bg-green-500/20 text-green-400' : 'bg-red-500/20 text-red-400'}`}>
                                    {data.bot_state?.is_running ? '✅ YES' : '❌ NO'}
                                </span>
                            </div>
                            <div>
                                <div className="text-xs text-gray-400">Active Symbol</div>
                                <div className="text-lg font-bold">{data.bot_state?.active_symbol || 'N/A'}</div>
                            </div>
                            <div>
                                <div className="text-xs text-gray-400">Execution Mode</div>
                                <div className="text-sm">{data.bot_state?.execution_mode || 'N/A'}</div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    )
}
