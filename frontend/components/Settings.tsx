'use client'

import { useState, useEffect } from 'react'
import useSWR from 'swr'
import axios from 'axios'

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

export default function Settings() {
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

    const [isOpen, setIsOpen] = useState(false)

    // CRITICAL: Fetch active_symbol from status endpoint
    const { data: statusData } = useSWR(`${API_URL}/api/status`, async (url) => {
        const res = await axios.get(url)
        return res.data
    }, { refreshInterval: 2000 })

    // Use SWR for auto-syncing settings (especially asset/symbol changes)
    const { data: serverSettings } = useSWR(`${API_URL}/api/settings`, async (url) => {
        const res = await axios.get(url)
        return res.data
    }, { refreshInterval: 2000 })

    // Sync local state when server data changes
    useEffect(() => {
        if (serverSettings || statusData) {
            setSettings(prev => ({
                ...prev,
                ...serverSettings,
                // CRITICAL FIX: Use active_symbol from status if available
                asset: statusData?.active_symbol || serverSettings?.asset || prev.asset,
                // Ensure numeric values are parsed correctly
                size_value: parseFloat(serverSettings?.size_value || prev.size_value),
                leverage: parseInt(serverSettings?.leverage || prev.leverage),
                max_positions: parseInt(serverSettings?.max_positions || prev.max_positions),
                daily_stop_loss: parseFloat(serverSettings?.daily_stop_loss || prev.daily_stop_loss),
            }))
        }
    }, [serverSettings, statusData])

    const saveSettings = async () => {
        try {
            // Save all settings
            await axios.post(`${API_URL}/api/settings`, settings)

            // Also explicitly switch symbol to ensure sync
            await axios.post(`${API_URL}/api/symbol/switch`, { symbol: settings.asset })

            alert('✅ Settings saved!')
        } catch (error) {
            console.error('Failed to save settings:', error)
            alert('❌ Failed to save settings')
        }
    }

    return (
        <>
            {/* Settings Button */}
            <button
                onClick={() => setIsOpen(!isOpen)}
                className="fixed bottom-6 right-6 w-14 h-14 bg-primary hover:bg-primary-dark rounded-full shadow-lg flex items-center justify-center text-2xl transition-all z-50"
            >
                ⚙️
            </button>

            {/* Settings Panel */}
            {isOpen && (
                <div className="fixed inset-0 bg-black/50 backdrop-blur-sm z-50 flex items-center justify-center p-4">
                    <div className="bg-surface border border-border/30 rounded-2xl p-6 max-w-2xl w-full max-h-[90vh] overflow-y-auto">
                        <div className="flex items-center justify-between mb-6">
                            <h2 className="text-2xl font-bold">🎛️ Settings</h2>
                            <button
                                onClick={() => setIsOpen(false)}
                                className="text-gray-400 hover:text-white text-2xl"
                            >
                                ✕
                            </button>
                        </div>

                        <div className="space-y-6">
                            {/* Asset Selection */}
                            <div>
                                <label className="block text-sm font-semibold mb-2">Market</label>
                                <input
                                    type="text"
                                    value={settings.asset}
                                    onChange={(e) => setSettings({ ...settings, asset: e.target.value.toUpperCase() })}
                                    list="assets"
                                    className="w-full bg-background border border-border/30 rounded-lg px-4 py-2 uppercase"
                                    placeholder="Enter symbol (e.g. BTC, ETH, SOL)"
                                />
                                <datalist id="assets">
                                    <option value="BTC">Bitcoin</option>
                                    <option value="ETH">Ethereum</option>
                                    <option value="SOL">Solana</option>
                                    <option value="BNB">Binance Coin</option>
                                    <option value="ARB">Arbitrum</option>
                                    <option value="AVAX">Avalanche</option>
                                    <option value="MATIC">Polygon</option>
                                    <option value="LINK">Chainlink</option>
                                    <option value="UNI">Uniswap</option>
                                    <option value="ATOM">Cosmos</option>
                                    <option value="DOT">Polkadot</option>
                                    <option value="DOGE">Dogecoin</option>
                                    <option value="XRP">Ripple</option>
                                    <option value="ADA">Cardano</option>
                                    <option value="INIT">Initia</option>
                                    <option value="STABLE">Stable Protocol</option>
                                </datalist>
                            </div>

                            {/* Market Selection */}


                            {/* Risk Management */}
                            <div className="border-t border-border/30 pt-6">
                                <h3 className="text-lg font-semibold mb-4">🛡️ Risk Management</h3>
                                <p className="text-sm text-gray-400 mb-4">
                                    ℹ️ Leverage and position size are managed by your Gamification level
                                </p>

                                <div className="space-y-4">
                                    <div>
                                        <label className="block text-sm font-semibold mb-2">Daily Stop Loss (USDC)</label>
                                        <input
                                            type="number"
                                            value={settings.daily_stop_loss}
                                            onChange={(e) => setSettings({ ...settings, daily_stop_loss: parseFloat(e.target.value) })}
                                            min="1"
                                            step="10"
                                            className="w-full bg-background border border-border/30 rounded-lg px-4 py-2"
                                        />
                                        <div className="text-xs text-gray-400 mt-1">Circuit breaker: Stops bot if daily loss exceeds this</div>
                                    </div>
                                </div>
                            </div>


                            {/* Trading Control */}
                            <div className="border-t border-border/30 pt-6">
                                <h3 className="text-lg font-semibold mb-4">🤖 Trading Control</h3>

                                <div className="space-y-4">
                                    <div className="flex items-center justify-between p-4 bg-background/50 rounded-lg border border-border/30">
                                        <div>
                                            <label className="text-sm font-semibold block mb-1">Enable Automatic Trading</label>
                                            <p className="text-xs text-gray-400">Allow bot to execute trades automatically</p>
                                        </div>
                                        <button
                                            onClick={async () => {
                                                try {
                                                    const endpoint = settings.trading_enabled ? '/api/trading/disable' : '/api/trading/enable'
                                                    await axios.post(`${API_URL}${endpoint}`)
                                                    setSettings({ ...settings, trading_enabled: !settings.trading_enabled })
                                                } catch (error) {
                                                    console.error('Failed to toggle trading:', error)
                                                    alert('❌ Failed to toggle trading')
                                                }
                                            }}
                                            className={`px-6 py-3 rounded-lg font-bold uppercase tracking-wider transition-all ${settings.trading_enabled
                                                    ? 'bg-red-500/20 text-red-500 border-2 border-red-500/50 hover:bg-red-500/30'
                                                    : 'bg-primary/20 text-primary border-2 border-primary/50 hover:bg-primary/30'
                                                }`}
                                        >
                                            {settings.trading_enabled ? '🛑 STOP BOT' : '▶️ START BOT'}
                                        </button>
                                    </div>

                                    {!settings.trading_enabled && (
                                        <div className="text-xs text-yellow-500 bg-yellow-500/10 border border-yellow-500/30 rounded-lg p-3">
                                            ⚠️ Trading is currently DISABLED. Bot will analyze signals but won't execute trades.
                                        </div>
                                    )}
                                </div>
                            </div>


                            {/* Scanner Automation */}
                            <div className="border-t border-border/30 pt-6">
                                <h3 className="text-lg font-semibold mb-4">🤖 Scanner Automation</h3>

                                <div className="space-y-4">
                                    <div className="flex items-center justify-between">
                                        <label className="text-sm font-semibold">Enable Auto-Scan</label>
                                        <input
                                            type="checkbox"
                                            checked={settings.scanner?.enabled || false}
                                            onChange={(e) => setSettings({
                                                ...settings,
                                                scanner: { ...settings.scanner!, enabled: e.target.checked }
                                            })}
                                            className="w-5 h-5 accent-primary"
                                        />
                                    </div>

                                    <div className="grid grid-cols-2 gap-4">
                                        <div>
                                            <label className="block text-sm font-semibold mb-2">Interval (min)</label>
                                            <input
                                                type="number"
                                                value={settings.scanner?.interval || 15}
                                                onChange={(e) => setSettings({
                                                    ...settings,
                                                    scanner: { ...settings.scanner!, interval: parseInt(e.target.value) }
                                                })}
                                                min="5"
                                                className="w-full bg-background border border-border/30 rounded-lg px-4 py-2"
                                            />
                                        </div>
                                        <div>
                                            <label className="block text-sm font-semibold mb-2">Min Score (0-100)</label>
                                            <input
                                                type="number"
                                                value={settings.scanner?.min_score || 75}
                                                onChange={(e) => setSettings({
                                                    ...settings,
                                                    scanner: { ...settings.scanner!, min_score: parseInt(e.target.value) }
                                                })}
                                                min="0"
                                                max="100"
                                                className="w-full bg-background border border-border/30 rounded-lg px-4 py-2"
                                            />
                                        </div>
                                    </div>

                                    <div className="flex items-center justify-between bg-surface/50 p-3 rounded-lg border border-border/30">
                                        <div>
                                            <div className="text-sm font-semibold">Auto-Switch Symbol</div>
                                            <div className="text-xs text-gray-400">Automatically switch chart to best opportunity</div>
                                        </div>
                                        <input
                                            type="checkbox"
                                            checked={settings.scanner?.auto_switch || false}
                                            onChange={(e) => setSettings({
                                                ...settings,
                                                scanner: { ...settings.scanner!, auto_switch: e.target.checked }
                                            })}
                                            className="w-5 h-5 accent-primary"
                                        />
                                    </div>
                                </div>
                            </div>

                            {/* Save Button */}
                            <button
                                onClick={saveSettings}
                                className="w-full bg-success hover:bg-success/80 text-white font-semibold py-3 rounded-lg transition-all"
                            >
                                💾 Save Settings
                            </button>
                        </div>
                    </div>
                </div >
            )
            }
        </>
    )
}
