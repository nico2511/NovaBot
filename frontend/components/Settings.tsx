'use client'

import { useState, useEffect } from 'react'
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

    useEffect(() => {
        // Load settings from API
        const loadSettings = async () => {
            try {
                const response = await axios.get(`${API_URL}/api/settings`)
                if (response.data) {
                    setSettings(prev => ({
                        ...prev,
                        ...response.data,
                        // Ensure numeric values are parsed correctly if string comes back
                        size_value: parseFloat(response.data.size_value || prev.size_value),
                        leverage: parseInt(response.data.leverage || prev.leverage),
                        max_positions: parseInt(response.data.max_positions || prev.max_positions),
                        daily_stop_loss: parseFloat(response.data.daily_stop_loss || prev.daily_stop_loss)
                    }))
                }
            } catch (error) {
                console.error('Failed to load settings:', error)
            }
        }

        loadSettings()
    }, []) // Load once on mount

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

                                {/* Position Sizing */}
                                <div className="space-y-4">
                                    <div>
                                        <label className="block text-sm font-semibold mb-2">Sizing Type</label>
                                        <select
                                            value={settings.size_type}
                                            onChange={(e) => setSettings({ ...settings, size_type: e.target.value })}
                                            className="w-full bg-background border border-border/30 rounded-lg px-4 py-2"
                                        >
                                            <option value="Fixed (USDC)">Fixed (USDC)</option>
                                            <option value="% Equity">% Equity</option>
                                        </select>
                                    </div>

                                    <div>
                                        <label className="block text-sm font-semibold mb-2">
                                            Size Value {settings.size_type === '% Equity' ? '(%)' : '(USDC)'}
                                        </label>
                                        <input
                                            type="number"
                                            value={settings.size_value}
                                            onChange={(e) => setSettings({ ...settings, size_value: parseFloat(e.target.value) })}
                                            min="1"
                                            step="10"
                                            className="w-full bg-background border border-border/30 rounded-lg px-4 py-2"
                                        />
                                    </div>

                                    <div>
                                        <label className="block text-sm font-semibold mb-2">Leverage (1-20x)</label>
                                        <input
                                            type="range"
                                            value={settings.leverage}
                                            onChange={(e) => setSettings({ ...settings, leverage: parseInt(e.target.value) })}
                                            min="1"
                                            max="20"
                                            className="w-full"
                                        />
                                        <div className="text-center text-lg font-bold mt-2">{settings.leverage}x</div>
                                    </div>

                                    <div>
                                        <label className="block text-sm font-semibold mb-2">Max Open Positions</label>
                                        <input
                                            type="number"
                                            value={settings.max_positions}
                                            onChange={(e) => setSettings({ ...settings, max_positions: parseInt(e.target.value) })}
                                            min="1"
                                            max="10"
                                            className="w-full bg-background border border-border/30 rounded-lg px-4 py-2"
                                        />
                                        <div className="text-xs text-gray-400 mt-1">Hard limit on concurrent trades</div>
                                    </div>

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
