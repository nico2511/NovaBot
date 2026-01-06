'use client'

import { useDiagnostics } from '@/hooks/useDiagnostics'
import MetricCard from '@/components/dev/MetricCard'
import ServiceStatusCard from '@/components/dev/ServiceStatusCard'
import { RefreshCw, TrendingUp, DollarSign, Activity, Zap, Cpu } from 'lucide-react'
import axios from 'axios'

export default function DevPage() {
    const { data, error, isLoading, refresh } = useDiagnostics()

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

    if (isLoading || !data) {
        return (
            <div className="min-h-screen bg-[#050505] text-white flex items-center justify-center">
                <div className="text-center">
                    <div className="w-12 h-12 border-4 border-blue-500 border-t-transparent rounded-full animate-spin mx-auto mb-4"></div>
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
                        <p className="text-gray-400">Real-time system & bot internals</p>
                    </div>
                    <button
                        onClick={() => refresh()}
                        className="px-4 py-2 bg-blue-500/20 hover:bg-blue-500/30 border border-blue-500/50 rounded-lg flex items-center gap-2 transition-colors"
                    >
                        <RefreshCw size={16} />
                        Refresh
                    </button>
                </div>

                {/* Rapid Actions */}
                <div className="mb-8 bg-gradient-to-br from-orange-500/10 to-red-500/5 border border-orange-500/30 rounded-xl p-6">
                    <div className="flex items-center gap-2 mb-4">
                        <Zap className="text-orange-400" size={20} />
                        <h3 className="text-lg font-bold text-orange-400">Rapid Actions</h3>
                    </div>
                    <div className="flex flex-wrap gap-3">
                        <button
                            onClick={async () => {
                                if (!confirm('Pull latest code from Git?')) return
                                try {
                                    await axios.post('/api/dev/git_pull')
                                    alert('✅ Git pull successful!')
                                    refresh()
                                } catch (e: any) {
                                    alert(`❌ Error: ${e.response?.data?.message || e.message}`)
                                }
                            }}
                            className="px-4 py-2 bg-blue-500/20 hover:bg-blue-500/30 border border-blue-500/50 rounded-lg flex items-center gap-2 transition-colors text-sm font-semibold"
                        >
                            📥 Git Pull
                        </button>
                        <button
                            onClick={async () => {
                                if (!confirm('Build frontend? This may take 1-2 minutes.')) return
                                try {
                                    await axios.post('/api/dev/build_frontend')
                                    alert('✅ Frontend build started!')
                                } catch (e: any) {
                                    alert(`❌ Error: ${e.response?.data?.message || e.message}`)
                                }
                            }}
                            className="px-4 py-2 bg-green-500/20 hover:bg-green-500/30 border border-green-500/50 rounded-lg flex items-center gap-2 transition-colors text-sm font-semibold"
                        >
                            🔨 Build Frontend
                        </button>
                        <button
                            onClick={async () => {
                                if (!confirm('Restart frontend server?')) return
                                try {
                                    await axios.post('/api/dev/restart_frontend')
                                    alert('✅ Frontend restarted!')
                                } catch (e: any) {
                                    alert(`❌ Error: ${e.response?.data?.message || e.message}`)
                                }
                            }}
                            className="px-4 py-2 bg-purple-500/20 hover:bg-purple-500/30 border border-purple-500/50 rounded-lg flex items-center gap-2 transition-colors text-sm font-semibold"
                        >
                            🔄 Restart Frontend
                        </button>
                        <button
                            onClick={async () => {
                                if (!confirm('Restart bot backend?')) return
                                try {
                                    await axios.post('/api/dev/restart_bot')
                                    alert('✅ Bot restarted!')
                                    setTimeout(() => refresh(), 2000)
                                } catch (e: any) {
                                    alert(`❌ Error: ${e.response?.data?.message || e.message}`)
                                }
                            }}
                            className="px-4 py-2 bg-red-500/20 hover:bg-red-500/30 border border-red-500/50 rounded-lg flex items-center gap-2 transition-colors text-sm font-semibold"
                        >
                            🔄 Restart Bot
                        </button>
                    </div>
                </div>

                {/* --- SECTIONS --- */}

                {/* 1. Bot State & Systems */}
                <h3 className="text-lg font-bold text-gray-400 mb-4 uppercase tracking-widest text-xs">Bot System State</h3>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
                    <MetricCard
                        label="Engine Status"
                        value={data.bot_state?.is_running ? 'RUNNING' : 'STOPPED'}
                        icon={<Cpu size={14} />}
                        statusColor={data.bot_state?.is_running ? 'green' : 'red'}
                    />
                    <MetricCard
                        label="Trading"
                        value={data.bot_state?.trading_enabled ? 'ENABLED' : 'DISABLED'}
                        icon={<Activity size={14} />}
                        statusColor={data.bot_state?.trading_enabled ? 'green' : 'yellow'}
                    />
                    <MetricCard
                        label="Active Symbol"
                        value={data.bot_state?.active_symbol || 'N/A'}
                        icon={<TrendingUp size={14} />}
                        statusColor="blue"
                    />
                    <MetricCard
                        label="Mode"
                        value={data.bot_state?.execution_mode?.includes('Auto') ? 'LIVE' : 'PAPER'}
                        icon={<Zap size={14} />}
                        statusColor={data.bot_state?.execution_mode?.includes('Auto') ? 'red' : 'green'}
                    />
                </div>

                {/* 2. Services Health */}
                <h3 className="text-lg font-bold text-gray-400 mb-4 uppercase tracking-widest text-xs">Service Health</h3>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-8">
                    <ServiceStatusCard
                        name="Hyperliquid API"
                        isHealthy={data.api_status?.hyperliquid_connected}
                        latency={data.api_status?.last_call}
                        details={`Rate Limit: ${data.api_status?.rate_limit_remaining || 'N/A'}`}
                    />
                    <ServiceStatusCard
                        name="Scanner Engine"
                        isHealthy={data.scanner_settings?.enabled}
                        details={`Interval: ${data.scanner_settings?.interval}m`}
                    />
                    <MetricCard
                        label="Gamification"
                        value={`Level ${data.gamification?.level || 0}`}
                        subValue={`${data.gamification?.progress_pct?.toFixed(1)}%`}
                        icon={<Activity size={14} />}
                        statusColor="blue"
                    />
                </div>

                {/* 3. Account & Portfolio Metrics */}
                <h3 className="text-lg font-bold text-gray-400 mb-4 uppercase tracking-widest text-xs">Account Metrics</h3>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
                    <MetricCard
                        label="Total Equity"
                        value={`$${data.account?.balance?.toFixed(2) || '0.00'}`}
                        icon={<DollarSign size={14} />}
                        statusColor="green"
                    />
                    <MetricCard
                        label="Unrealized PnL"
                        value={`$${data.portfolio?.unrealized_pnl?.toFixed(2) || '0.00'}`}
                        subValue={`${data.portfolio?.roi_unrealized_pct?.toFixed(2)}%`}
                        statusColor={(data.portfolio?.unrealized_pnl || 0) >= 0 ? 'green' : 'red'}
                    />
                    <MetricCard
                        label="Realized Today"
                        value={`$${data.portfolio?.realized_pnl_today?.toFixed(2) || '0.00'}`}
                        subValue={`${data.portfolio?.roi_today_pct?.toFixed(2)}%`}
                        statusColor={(data.portfolio?.realized_pnl_today || 0) >= 0 ? 'green' : 'red'}
                    />
                    <MetricCard
                        label="Leverage"
                        value={`${data.portfolio?.account_leverage?.toFixed(2) || '0.00'}x`}
                        statusColor="yellow"
                    />
                </div>

                {/* 4. Active Positions List */}
                {data.positions?.length > 0 && (
                    <div className="mb-8">
                        <h3 className="text-lg font-bold text-gray-400 mb-4 uppercase tracking-widest text-xs">Active Positions</h3>
                        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                            {Array.isArray(data.positions) && data.positions.map((pos: any, i: number) => (
                                <div key={i} className="bg-white/5 border border-white/10 rounded-xl p-4">
                                    <div className="flex justify-between items-center mb-2">
                                        <span className="font-bold text-lg">{pos.symbol}</span>
                                        <span className={`px-2 py-0.5 rounded text-xs font-bold ${pos.side === 'BUY' ? 'bg-green-500/20 text-green-400' : 'bg-red-500/20 text-red-400'}`}>
                                            {pos.side}
                                        </span>
                                    </div>
                                    <div className="flex justify-between text-sm">
                                        <span className="text-gray-400">Size: {pos.size}</span>
                                        <span className={`font-mono ${(pos.pnl || 0) >= 0 ? 'text-green-400' : 'text-red-400'}`}>
                                            ${pos.pnl?.toFixed(2)}
                                        </span>
                                    </div>
                                </div>
                            ))}
                        </div>
                    </div>
                )}

                {/* Dev Controls (Keeping strictly necessary) */}

            </div>
        </div>
    )
}
