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

                {/* Dev Controls */}
                <div className="bg-gradient-to-br from-orange-500/10 to-red-500/5 border border-orange-500/30 rounded-xl p-6 mb-6">
                    <div className="flex items-center gap-2 mb-4">
                        <span className="text-2xl">🛠️</span>
                        <h2 className="text-xl font-bold text-orange-300">Dev Controls</h2>
                        <span className="text-xs text-gray-400 ml-auto">⚠️ Production Only</span>
                    </div>

                    <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                        <button
                            onClick={async () => {
                                if (!confirm('Pull latest code from master?')) return
                                const btn = document.getElementById('git-pull-btn') as HTMLButtonElement
                                if (btn) btn.disabled = true
                                if (btn) btn.innerText = 'Pulling...'
                                try {
                                    const res = await axios.post('/api/dev/git_pull')
                                    alert(res.data.status === 'success' ? `✅ ${res.data.output}` : `❌ ${res.data.message}`)
                                } catch (e: any) {
                                    alert(`❌ Error: ${e.message}`)
                                }
                                if (btn) btn.disabled = false
                                if (btn) btn.innerText = '📥 Git Pull'
                            }}
                            id="git-pull-btn"
                            className="px-4 py-3 bg-blue-500/20 hover:bg-blue-500/30 border border-blue-500/50 rounded-lg font-bold text-sm transition-all"
                        >
                            📥 Git Pull
                        </button>

                        <button
                            onClick={async () => {
                                if (!confirm('Restart ALL PM2 processes?')) return
                                const btn = document.getElementById('restart-all-btn') as HTMLButtonElement
                                if (btn) btn.disabled = true
                                if (btn) btn.innerText = 'Restarting...'
                                try {
                                    await axios.post('/api/dev/restart_all')
                                    alert('✅ All processes restarted!')
                                } catch (e: any) {
                                    alert(`❌ Error: ${e.message}`)
                                }
                                if (btn) btn.disabled = false
                                if (btn) btn.innerText = '🔄 Restart All'
                            }}
                            id="restart-all-btn"
                            className="px-4 py-3 bg-orange-500/20 hover:bg-orange-500/30 border border-orange-500/50 rounded-lg font-bold text-sm transition-all"
                        >
                            🔄 Restart All
                        </button>

                        <button
                            onClick={async () => {
                                if (!confirm('Restart Frontend (Next.js)?')) return
                                const btn = document.getElementById('restart-front-btn') as HTMLButtonElement
                                if (btn) btn.disabled = true
                                if (btn) btn.innerText = 'Restarting...'
                                try {
                                    await axios.post('/api/dev/restart_frontend')
                                    alert('✅ Frontend restarted!')
                                } catch (e: any) {
                                    alert(`❌ Error: ${e.message}`)
                                }
                                if (btn) btn.disabled = false
                                if (btn) btn.innerText = '🎨 Restart Front'
                            }}
                            id="restart-front-btn"
                            className="px-4 py-3 bg-purple-500/20 hover:bg-purple-500/30 border border-purple-500/50 rounded-lg font-bold text-sm transition-all"
                        >
                            🎨 Restart Front
                        </button>

                        <button
                            onClick={async () => {
                                if (!confirm('Restart Bot Engine?')) return
                                const btn = document.getElementById('restart-bot-btn') as HTMLButtonElement
                                if (btn) btn.disabled = true
                                if (btn) btn.innerText = 'Restarting...'
                                try {
                                    await axios.post('/api/dev/restart_bot')
                                    alert('✅ Bot engine restarted!')
                                } catch (e: any) {
                                    alert(`❌ Error: ${e.message}`)
                                }
                                if (btn) btn.disabled = false
                                if (btn) btn.innerText = '🤖 Restart Bot'
                            }}
                            id="restart-bot-btn"
                            className="px-4 py-3 bg-green-500/20 hover:bg-green-500/30 border border-green-500/50 rounded-lg font-bold text-sm transition-all"
                        >
                            🤖 Restart Bot
                        </button>
                    </div>
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

                    {/* Recent Trades */}
                    <div className="bg-black/40 backdrop-blur border border-border/30 rounded-xl p-6 md:col-span-2 lg:col-span-3">
                        <div className="flex items-center gap-2 mb-4">
                            <Activity className="text-gray-400" size={20} />
                            <h2 className="text-xl font-bold">Recent Trades</h2>
                        </div>
                        <div className="overflow-x-auto">
                            <table className="w-full text-sm">
                                <thead>
                                    <tr className="text-left text-gray-500 border-b border-white/5">
                                        <th className="pb-2">Date</th>
                                        <th className="pb-2">Time</th>
                                        <th className="pb-2">Symbol</th>
                                        <th className="pb-2">Side</th>
                                        <th className="pb-2">Size</th>
                                        <th className="pb-2">Price</th>
                                        <th className="pb-2">Fee</th>
                                        <th className="pb-2">PnL</th>
                                    </tr>
                                </thead>
                                <tbody className="text-gray-300">
                                    {data.recent_trades && data.recent_trades.length > 0 ? (
                                        data.recent_trades.map((trade: any, i: number) => (
                                            <tr key={i} className="border-b border-white/5 hover:bg-white/5">
                                                <td className="py-2 font-mono text-gray-500" suppressHydrationWarning>
                                                    {new Date(trade.time).toLocaleDateString()}
                                                </td>
                                                <td className="py-2 font-mono" suppressHydrationWarning>
                                                    {new Date(trade.time).toLocaleTimeString()}
                                                </td>
                                                <td className="py-2 font-bold">{trade.symbol}</td>
                                                <td className={`py-2 ${trade.side === 'BUY' ? 'text-green-400' : 'text-red-400'}`}>
                                                    {trade.side}
                                                </td>
                                                <td className="py-2 font-mono">{trade.size}</td>
                                                <td className="py-2 font-mono">${trade.price.toFixed(4)}</td>
                                                <td className="py-2 font-mono text-gray-400">${trade.fee?.toFixed(4)}</td>
                                                <td className={`py-2 font-mono ${(trade.pnl_real || 0) >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                                                    ${(trade.pnl_real || 0).toFixed(4)}
                                                </td>
                                            </tr>
                                        ))
                                    ) : (
                                        <tr>
                                            <td colSpan={8} className="py-4 text-center text-gray-500">
                                                No recent trades
                                            </td>
                                        </tr>
                                    )}
                                </tbody>
                            </table>
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

                    {/* Gamification Status */}
                    <div className="bg-black/40 backdrop-blur border border-border/30 rounded-xl p-6">
                        <div className="flex items-center gap-2 mb-4">
                            <Activity className="text-purple-500" size={20} />
                            <h2 className="text-xl font-bold">Gamification</h2>
                        </div>
                        <div className="space-y-3">
                            <div className="flex items-center justify-between">
                                <span className="text-sm text-gray-400">Level</span>
                                <span className="text-lg font-bold text-yellow-400">{data.gamification?.level || 'N/A'}</span>
                            </div>
                            <div className="flex items-center justify-between">
                                <span className="text-sm text-gray-400">Title</span>
                                <span className="text-sm font-mono text-gray-300">{data.gamification?.title || 'Noob'}</span>
                            </div>
                            <div className="w-full bg-gray-700 h-2 rounded-full mt-2">
                                <div
                                    className="bg-purple-500 h-2 rounded-full"
                                    style={{ width: `${Math.min(100, data.gamification?.progress_pct || 0)}%` }}
                                ></div>
                            </div>
                            <div className="text-xs text-center text-gray-500 mt-1">
                                {data.gamification?.progress_pct?.toFixed(1)}% to next level
                            </div>
                        </div>
                    </div>

                    {/* Trading Settings */}
                    <div className="bg-black/40 backdrop-blur border border-border/30 rounded-xl p-6">
                        <div className="flex items-center gap-2 mb-4">
                            <Activity className="text-orange-500" size={20} />
                            <h2 className="text-xl font-bold">Trading Config</h2>
                        </div>
                        <div className="space-y-3">
                            <div className="grid grid-cols-2 gap-4">
                                <div>
                                    <div className="text-xs text-gray-400">Leverage</div>
                                    <div className="text-lg font-mono">{data.trading_settings?.leverage || 1}x</div>
                                </div>
                                <div>
                                    <div className="text-xs text-gray-400">Max Pos</div>
                                    <div className="text-lg font-mono">{data.trading_settings?.max_positions || 1}</div>
                                </div>
                            </div>
                            <div>
                                <div className="text-xs text-gray-400">Size</div>
                                <div className="text-sm font-mono">
                                    {data.trading_settings?.size_value || 0} ({data.trading_settings?.size_type || 'Values'})
                                </div>
                            </div>
                            <div>
                                <div className="text-xs text-gray-400">Daily Stop Loss</div>
                                <div className="text-sm font-mono text-red-400">
                                    ${data.trading_settings?.daily_stop_loss || 0}
                                </div>
                            </div>
                        </div>
                    </div>

                    {/* Scanner Settings */}
                    <div className="bg-black/40 backdrop-blur border border-border/30 rounded-xl p-6">
                        <div className="flex items-center gap-2 mb-4 justify-between">
                            <div className="flex items-center gap-2">
                                <Activity className="text-blue-500" size={20} />
                                <h2 className="text-xl font-bold">Scanner</h2>
                            </div>
                            <button
                                onClick={async () => {
                                    const btn = document.getElementById('scan-btn');
                                    if (btn) btn.innerText = 'Scanning...';
                                    try {
                                        await fetch('/api/dev/scan', { method: 'POST' });
                                        // window.location.reload(); // Let SWR update it
                                    } catch (e) {
                                        alert('Scan failed');
                                    }
                                    if (btn) btn.innerText = 'Run Scan';
                                }}
                                id="scan-btn"
                                className="px-3 py-1 bg-blue-600 hover:bg-blue-500 text-xs rounded font-bold transition-colors"
                            >
                                Run Scan
                            </button>
                        </div>
                        <div className="space-y-3">
                            <div className="flex items-center justify-between">
                                <span className="text-sm text-gray-400">Status</span>
                                <span className={`px-2 py-1 rounded text-xs font-bold ${data.scanner_settings?.enabled ? 'bg-green-500/20 text-green-400' : 'bg-gray-500/20 text-gray-400'}`}>
                                    {data.scanner_settings?.enabled ? 'ACTIVE' : 'MANUAL'}
                                </span>
                            </div>
                            <div className="flex items-center justify-between">
                                <span className="text-sm text-gray-400">Auto-Switch</span>
                                <span className={`px-2 py-1 rounded text-xs font-bold ${data.scanner_settings?.auto_switch ? 'bg-green-500/20 text-green-400' : 'bg-gray-500/20 text-gray-400'}`}>
                                    {data.scanner_settings?.auto_switch ? 'ON' : 'OFF'}
                                </span>
                            </div>
                            <div className="grid grid-cols-2 gap-4">
                                <div>
                                    <div className="text-xs text-gray-400">Interval</div>
                                    <div className="text-lg font-mono">{data.scanner_settings?.interval || 15}m</div>
                                </div>
                                <div>
                                    <div className="text-xs text-gray-400">Min Score</div>
                                    <div className="text-lg font-mono">{data.scanner_settings?.min_score || 0}</div>
                                </div>
                            </div>

                            {/* Detailed Scan Results */}
                            <div className="mt-4 border-t border-gray-700/50 pt-3">
                                <div className="text-xs text-gray-400 mb-2">Last Scan Results</div>
                                {data.scanner_results && data.scanner_results.length > 0 ? (
                                    <div className="space-y-2 max-h-40 overflow-y-auto pr-1">
                                        {data.scanner_results.map((res: any, idx: number) => (
                                            <div key={idx} className="flex items-center justify-between text-xs bg-white/5 p-2 rounded">
                                                <div className="flex items-center gap-2">
                                                    <span className="font-bold text-blue-300">{res.symbol}</span>
                                                    <span className={res.trend === 'UP' ? 'text-green-400' : 'text-red-400'}>
                                                        {res.trend === 'UP' ? '↗' : '↘'}
                                                    </span>
                                                </div>
                                                <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-gray-400 font-mono text-[10px] sm:text-xs text-right">
                                                    <span>Sc: <b className="text-white">{Math.round(res.score)}</b></span>
                                                    <span>RSI: {Math.round(res.rsi)}</span>

                                                    <span>Vol: <b className="text-gray-300">${(res.volume_24h / 1e6).toFixed(1)}M</b></span>
                                                    <span>ADX: {Math.round(res.adx || 0)}</span>

                                                    <span>OI: <b className="text-gray-300">${(res.open_interest / 1e6).toFixed(1)}M</b></span>
                                                    <span>F: <b className={(res.funding || 0) > 0 ? "text-green-400" : "text-red-400"}>{((res.funding || 0) * 100).toFixed(4)}%</b></span>
                                                </div>
                                            </div>
                                        ))}
                                    </div>
                                ) : (
                                    <div className="text-xs text-gray-500 italic text-center py-2">
                                        Waiting for first scan...
                                    </div>
                                )}
                            </div>
                        </div>
                    </div>

                    {/* Active Strategy */}
                    <div className="bg-black/40 backdrop-blur border border-border/30 rounded-xl p-6 md:col-span-2">
                        <div className="flex items-center gap-2 mb-4">
                            <Activity className="text-pink-500" size={20} />
                            <h2 className="text-xl font-bold">Active Strategy</h2>
                        </div>
                        <div className="space-y-3">
                            <div className="text-lg font-bold text-primary">
                                {data.active_strategy?.name || 'None'}
                            </div>
                            <div className="bg-white/5 rounded-lg p-3 text-xs font-mono overflow-x-auto">
                                <div className="text-gray-400 mb-1">Parameters:</div>
                                <pre>
                                    {JSON.stringify(data.active_strategy?.params || {}, null, 2)}
                                </pre>
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
