'use client'

import { useState, useEffect } from 'react'
import useSWR from 'swr'
import axios from 'axios'
import { Settings as SettingsIcon, Shield, Zap, Activity, Save, ArrowLeft } from 'lucide-react'
import Link from 'next/link'

const API_URL = ''

interface Settings {
    asset: string
    execution_mode: string
    trading_enabled: boolean
    size_type: string
    size_value: number
    leverage: number
    max_positions: number
    daily_stop_loss: number
    scanner?: {
        enabled: boolean
        interval: number
        min_score: number
        auto_switch: boolean
    }
}

export default function ConfigPage() {
    const [settings, setSettings] = useState<Settings>({
        asset: 'BTC',
        execution_mode: 'Manual (Phantom)',
        trading_enabled: false,
        size_type: 'Fixed (USDC)',
        size_value: 100,
        leverage: 5,
        max_positions: 3,
        daily_stop_loss: 100,
        scanner: {
            enabled: false,
            interval: 15,
            min_score: 75,
            auto_switch: false
        }
    })

    const [isSaving, setIsSaving] = useState(false)

    // Fetch active_symbol from status endpoint
    const { data: statusData } = useSWR(`${API_URL}/api/status`, async (url) => {
        const res = await axios.get(url)
        return res.data
    }, { refreshInterval: 2000 })

    // Use SWR for auto-syncing settings
    const { data: serverSettings } = useSWR(`${API_URL}/api/settings`, async (url) => {
        const res = await axios.get(url)
        return res.data
    }, { refreshInterval: 2000 })

    useEffect(() => {
        if (serverSettings || statusData) {
            setSettings(prev => ({
                ...prev,
                ...serverSettings,
                asset: statusData?.active_symbol || serverSettings?.asset || prev.asset,
                size_value: parseFloat(serverSettings?.size_value || prev.size_value),
                leverage: parseInt(serverSettings?.leverage || prev.leverage),
                max_positions: parseInt(serverSettings?.max_positions || prev.max_positions),
                daily_stop_loss: parseFloat(serverSettings?.daily_stop_loss || prev.daily_stop_loss),
            }))
        }
    }, [serverSettings, statusData])

    const saveSettings = async () => {
        setIsSaving(true)
        try {
            await axios.post(`${API_URL}/api/settings`, settings)
            await axios.post(`${API_URL}/api/symbol/switch`, { symbol: settings.asset })
            alert('✅ Settings saved successfully!')
        } catch (error) {
            console.error('Failed to save settings:', error)
            alert('❌ Failed to save settings')
        } finally {
            setIsSaving(false)
        }
    }

    return (
        <div className="min-h-screen bg-[#050505] text-white p-8">
            <div className="max-w-4xl mx-auto space-y-8">

                {/* Header */}
                <div className="flex items-center justify-between">
                    <div className="flex items-center gap-4">
                        <Link href="/" className="p-2 hover:bg-white/5 rounded-full transition-colors">
                            <ArrowLeft size={24} className="text-gray-400" />
                        </Link>
                        <div>
                            <h1 className="text-3xl font-bold flex items-center gap-3">
                                <SettingsIcon className="text-gray-400" />
                                Bot Configuration
                            </h1>
                            <p className="text-gray-400 mt-1">Manage trading parameters, risk, and automations</p>
                        </div>
                    </div>
                </div>

                {/* Main Config Area */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-8">

                    {/* RISK MANAGEMENT */}
                    <div className="space-y-6">
                        <div className="flex items-center gap-2 mb-4">
                            <Shield className="text-orange-500" size={24} />
                            <h2 className="text-xl font-bold">Risk Management</h2>
                        </div>
                        <div className="bg-white/5 border border-white/10 rounded-2xl p-6 space-y-6">

                            {/* Position Size */}
                            <div>
                                <label className="block text-sm font-semibold mb-2 text-gray-300">Position Size (USDC)</label>
                                <div className="text-xs text-gray-500 mb-2">Amount allocated per trade</div>
                                <input
                                    type="number"
                                    value={settings.size_value}
                                    onChange={(e) => setSettings({ ...settings, size_value: parseFloat(e.target.value) })}
                                    className="w-full bg-black/50 border border-white/10 rounded-xl px-4 py-3 focus:border-blue-500 transition-colors"
                                />
                            </div>

                            {/* Leverage */}
                            <div>
                                <label className="block text-sm font-semibold mb-2 text-gray-300">Leverage (x)</label>
                                <div className="text-xs text-gray-500 mb-2">Multiplier for position size</div>
                                <input
                                    type="number"
                                    value={settings.leverage}
                                    onChange={(e) => setSettings({ ...settings, leverage: parseInt(e.target.value) })}
                                    className="w-full bg-black/50 border border-white/10 rounded-xl px-4 py-3 focus:border-blue-500 transition-colors"
                                    min="1"
                                    max="50"
                                />
                            </div>

                            {/* Max Positions */}
                            <div>
                                <label className="block text-sm font-semibold mb-2 text-gray-300">Max Simultaneous Positions</label>
                                <div className="text-xs text-gray-500 mb-2">Limit exposure to multiple assets</div>
                                <input
                                    type="number"
                                    value={settings.max_positions}
                                    onChange={(e) => setSettings({ ...settings, max_positions: parseInt(e.target.value) })}
                                    className="w-full bg-black/50 border border-white/10 rounded-xl px-4 py-3 focus:border-blue-500 transition-colors"
                                    min="1"
                                    max="10"
                                />
                            </div>

                            {/* Daily Stop Loss */}
                            <div>
                                <label className="block text-sm font-semibold mb-2 text-red-400">Daily Stop Loss Limit (USDC)</label>
                                <div className="text-xs text-gray-500 mb-2">Bot stops automatically if daily loss exceeds this</div>
                                <input
                                    type="number"
                                    value={settings.daily_stop_loss}
                                    onChange={(e) => setSettings({ ...settings, daily_stop_loss: parseFloat(e.target.value) })}
                                    className="w-full bg-black/50 border border-red-500/30 rounded-xl px-4 py-3 focus:border-red-500 transition-colors text-red-200"
                                    min="1"
                                />
                            </div>
                        </div>
                    </div>

                    {/* AUTOMATION & MARKET */}
                    <div className="space-y-6">
                        <div className="flex items-center gap-2 mb-4">
                            <Zap className="text-blue-500" size={24} />
                            <h2 className="text-xl font-bold">Automation & Market</h2>
                        </div>
                        <div className="bg-white/5 border border-white/10 rounded-2xl p-6 space-y-6">

                            {/* Market Selector */}
                            <div>
                                <label className="block text-sm font-semibold mb-2 text-gray-300">Active Market</label>
                                <input
                                    type="text"
                                    value={settings.asset}
                                    onChange={(e) => setSettings({ ...settings, asset: e.target.value.toUpperCase() })}
                                    list="assets"
                                    className="w-full bg-black/50 border border-white/10 rounded-xl px-4 py-3 uppercase focus:border-blue-500 transition-colors"
                                    placeholder="Symbol (e.g. BTC)"
                                />
                                <datalist id="assets">
                                    <option value="BTC">Bitcoin</option>
                                    <option value="ETH">Ethereum</option>
                                    <option value="SOL">Solana</option>
                                    <option value="HYPE">HyperLiquid</option>
                                </datalist>
                            </div>

                            {/* Execution Mode */}
                            <div className="border-t border-white/10 pt-6">
                                <label className="block text-sm font-semibold mb-2 text-gray-300">Trading Mode</label>
                                <div className="text-xs text-gray-500 mb-3">
                                    Choose between simulation or real money trading
                                </div>
                                <select
                                    value={settings.execution_mode}
                                    onChange={(e) => setSettings({ ...settings, execution_mode: e.target.value })}
                                    className="w-full bg-black/50 border border-white/10 rounded-xl px-4 py-3 focus:border-blue-500 transition-colors"
                                >
                                    <option value="Manual (Phantom)">🧪 SIMULATION (Paper Trading - No Real Money)</option>
                                    <option value="Auto (Hyperliquid)">💸 LIVE (Real Money on Hyperliquid)</option>
                                </select>

                                {settings.execution_mode === "Manual (Phantom)" ? (
                                    <div className="text-xs text-blue-400 bg-blue-500/10 border border-blue-500/30 rounded-lg p-3 mt-3">
                                        🧪 <strong>SIMULATION MODE:</strong> Trades are simulated. No real money at risk.
                                    </div>
                                ) : (
                                    <div className="text-xs text-red-400 bg-red-500/10 border border-red-500/30 rounded-lg p-3 mt-3">
                                        💸 <strong>LIVE MODE:</strong> Real orders will be executed on Hyperliquid with real money!
                                    </div>
                                )}
                            </div>

                            <div className="border-t border-white/10 pt-6">
                                <h3 className="font-bold mb-4 flex items-center gap-2">
                                    <Activity size={18} className="text-purple-400" />
                                    Token Scanner
                                </h3>

                                <div className="space-y-4">
                                    <div className="flex items-center justify-between bg-black/30 p-4 rounded-xl">
                                        <div>
                                            <span className="font-semibold block">Enable Auto-Scan</span>
                                            <span className="text-xs text-gray-500">Periodically scan for opportunities</span>
                                        </div>
                                        <input
                                            type="checkbox"
                                            checked={settings.scanner?.enabled || false}
                                            onChange={(e) => setSettings({
                                                ...settings,
                                                scanner: { ...settings.scanner!, enabled: e.target.checked }
                                            })}
                                            className="w-6 h-6 accent-blue-500 rounded cursor-pointer"
                                        />
                                    </div>

                                    <div className="grid grid-cols-2 gap-4">
                                        <div>
                                            <label className="text-xs font-semibold text-gray-400">Interval (min)</label>
                                            <input
                                                type="number"
                                                value={settings.scanner?.interval || 15}
                                                onChange={(e) => setSettings({
                                                    ...settings,
                                                    scanner: { ...settings.scanner!, interval: parseInt(e.target.value) }
                                                })}
                                                className="w-full bg-black/50 border border-white/10 rounded-lg px-3 py-2 mt-1"
                                                min="5"
                                            />
                                        </div>
                                        <div>
                                            <label className="text-xs font-semibold text-gray-400">Min Score</label>
                                            <input
                                                type="number"
                                                value={settings.scanner?.min_score || 75}
                                                onChange={(e) => setSettings({
                                                    ...settings,
                                                    scanner: { ...settings.scanner!, min_score: parseInt(e.target.value) }
                                                })}
                                                className="w-full bg-black/50 border border-white/10 rounded-lg px-3 py-2 mt-1"
                                                min="0"
                                                max="100"
                                            />
                                        </div>
                                    </div>

                                    <div className="flex items-center justify-between bg-black/30 p-4 rounded-xl">
                                        <div>
                                            <span className="font-semibold block">Auto-Switch Symbol</span>
                                            <span className="text-xs text-gray-500">Switch chart to best opportunity found</span>
                                        </div>
                                        <input
                                            type="checkbox"
                                            checked={settings.scanner?.auto_switch || false}
                                            onChange={(e) => setSettings({
                                                ...settings,
                                                scanner: { ...settings.scanner!, auto_switch: e.target.checked }
                                            })}
                                            className="w-6 h-6 accent-purple-500 rounded cursor-pointer"
                                        />
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>

                {/* BOT CONTROL SECTION */}
                <div className="mt-8">
                    <div className="flex items-center gap-2 mb-4">
                        <Activity className="text-green-500" size={24} />
                        <h2 className="text-xl font-bold">Bot Control</h2>
                    </div>

                    <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                        {/* Bot Engine Control */}
                        <div className="bg-white/5 border border-white/10 rounded-2xl p-6">
                            <div className="flex items-center justify-between">
                                <div>
                                    <h3 className="text-lg font-bold text-white mb-1 flex items-center gap-2">
                                        🤖 Bot Engine
                                    </h3>
                                    <p className="text-sm text-gray-400">Start or stop the main trading loop</p>
                                </div>
                                <button
                                    onClick={async () => {
                                        try {
                                            const endpoint = statusData?.is_running ? '/api/engine/stop' : '/api/engine/start'
                                            await axios.post(`${API_URL}${endpoint}`)
                                        } catch (error) {
                                            console.error('Failed to toggle engine:', error)
                                            alert('❌ Failed to toggle engine')
                                        }
                                    }}
                                    className={`px-6 py-3 rounded-xl font-bold uppercase tracking-wider transition-all ${statusData?.is_running
                                        ? 'bg-red-500/20 text-red-500 border-2 border-red-500/50 hover:bg-red-500/30'
                                        : 'bg-green-500/20 text-green-500 border-2 border-green-500/50 hover:bg-green-500/30'
                                        }`}
                                >
                                    {statusData?.is_running ? '⏸️ STOP' : '▶️ START'}
                                </button>
                            </div>
                        </div>

                        {/* Trading Execution Control */}
                        <div className="bg-white/5 border border-white/10 rounded-2xl p-6">
                            <div className="flex items-center justify-between">
                                <div>
                                    <h3 className="text-lg font-bold text-white mb-1 flex items-center gap-2">
                                        💰 Auto-Trading
                                    </h3>
                                    <p className="text-sm text-gray-400">
                                        {settings.execution_mode === "Manual (Phantom)"
                                            ? "Enable paper trading (simulation only)"
                                            : "Enable live trading (REAL money)"}
                                    </p>
                                </div>
                                <button
                                    onClick={async () => {
                                        const newState = !settings.trading_enabled
                                        setSettings({ ...settings, trading_enabled: newState })

                                        try {
                                            const endpoint = settings.trading_enabled ? '/api/trading/disable' : '/api/trading/enable'
                                            await axios.post(`${API_URL}${endpoint}`)
                                        } catch (error) {
                                            console.error('Failed to toggle trading:', error)
                                            alert('❌ Failed to toggle trading')
                                            setSettings({ ...settings, trading_enabled: !newState })
                                        }
                                    }}
                                    className={`px-6 py-3 rounded-xl font-bold uppercase tracking-wider transition-all ${settings.trading_enabled
                                        ? 'bg-red-500/20 text-red-500 border-2 border-red-500/50 hover:bg-red-500/30'
                                        : 'bg-blue-500/20 text-blue-500 border-2 border-blue-500/50 hover:bg-blue-500/30'
                                        }`}
                                >
                                    {settings.trading_enabled ? '🛑 DISABLE' : '✅ ENABLE'}
                                </button>
                            </div>

                            {!settings.trading_enabled ? (
                                <div className="text-xs text-yellow-500 bg-yellow-500/10 border border-yellow-500/30 rounded-lg p-3 mt-4">
                                    ⚠️ Auto-trading is DISABLED. Bot will only analyze signals without executing trades.
                                </div>
                            ) : settings.execution_mode === "Manual (Phantom)" ? (
                                <div className="text-xs text-blue-400 bg-blue-500/10 border border-blue-500/30 rounded-lg p-3 mt-4">
                                    📊 Paper trading ENABLED. Bot will simulate trades (no real orders).
                                </div>
                            ) : (
                                <div className="text-xs text-green-400 bg-green-500/10 border border-green-500/30 rounded-lg p-3 mt-4">
                                    🚀 Live trading ENABLED. Bot will execute REAL orders on Hyperliquid!
                                </div>
                            )}
                        </div>
                    </div>
                </div>

                {/* Save Button */}
                <div className="fixed bottom-8 right-8 left-8 md:left-auto max-w-4xl mx-auto flex justify-end pointer-events-none">
                    <button
                        onClick={saveSettings}
                        disabled={isSaving}
                        className="pointer-events-auto flex items-center gap-3 px-8 py-4 bg-blue-600 hover:bg-blue-500 text-white font-bold rounded-2xl shadow-xl shadow-blue-900/20 transform hover:scale-105 transition-all text-lg disabled:opacity-50 disabled:cursor-not-allowed"
                    >
                        <Save size={24} />
                        {isSaving ? 'Saving...' : 'Save Configuration'}
                    </button>
                </div>
            </div>
        </div>
    )
}
