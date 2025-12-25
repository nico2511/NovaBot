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
        daily_stop_loss: 100
    })

    const [isOpen, setIsOpen] = useState(false)

    useEffect(() => {
        // Load settings from API
        const loadSettings = async () => {
            try {
                const response = await axios.get(`${API_URL}/api/settings`)
                if (response.data) {
                    setSettings(response.data)
                }
            } catch (error) {
                console.error('Failed to load settings:', error)
            }
        }
        loadSettings()
    }, [])

    const saveSettings = async () => {
        try {
            await axios.post(`${API_URL}/api/settings`, settings)
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
                                <select
                                    value={settings.asset}
                                    onChange={(e) => setSettings({ ...settings, asset: e.target.value })}
                                    className="w-full bg-background border border-border/30 rounded-lg px-4 py-2"
                                >
                                    <option value="BTC">BTC</option>
                                    <option value="ETH">ETH</option>
                                    <option value="SOL">SOL</option>
                                    <option value="BNB">BNB</option>
                                </select>
                            </div>

                            {/* Execution Mode */}
                            <div>
                                <label className="block text-sm font-semibold mb-2">Execution Mode</label>
                                <div className="space-y-2">
                                    <label className="flex items-center gap-2 cursor-pointer">
                                        <input
                                            type="radio"
                                            checked={settings.execution_mode === 'Manual (Phantom)'}
                                            onChange={() => setSettings({ ...settings, execution_mode: 'Manual (Phantom)', trading_enabled: false })}
                                            className="w-4 h-4"
                                        />
                                        <span>Manual (Phantom) - Paper trading only</span>
                                    </label>
                                    <label className="flex items-center gap-2 cursor-pointer">
                                        <input
                                            type="radio"
                                            checked={settings.execution_mode === 'Auto (Hyperliquid)'}
                                            onChange={() => setSettings({ ...settings, execution_mode: 'Auto (Hyperliquid)' })}
                                            className="w-4 h-4"
                                        />
                                        <span>Auto (Hyperliquid) - Live trading</span>
                                    </label>
                                </div>
                            </div>

                            {/* Live Trading Toggle */}
                            {settings.execution_mode === 'Auto (Hyperliquid)' && (
                                <div className="bg-warning/10 border border-warning/30 rounded-lg p-4">
                                    <label className="flex items-center gap-3 cursor-pointer">
                                        <input
                                            type="checkbox"
                                            checked={settings.trading_enabled}
                                            onChange={(e) => setSettings({ ...settings, trading_enabled: e.target.checked })}
                                            className="w-5 h-5"
                                        />
                                        <div>
                                            <div className="font-semibold">✅ ALLOW LIVE TRADING</div>
                                            <div className="text-sm text-gray-400">If unchecked, signals are generated but NOT executed</div>
                                        </div>
                                    </label>
                                    {settings.trading_enabled && (
                                        <div className="mt-3 text-warning font-semibold">
                                            ⚠️ Live Trading ENABLED
                                        </div>
                                    )}
                                </div>
                            )}

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

                            {/* Save Button */}
                            <button
                                onClick={saveSettings}
                                className="w-full bg-success hover:bg-success/80 text-white font-semibold py-3 rounded-lg transition-all"
                            >
                                💾 Save Settings
                            </button>
                        </div>
                    </div>
                </div>
            )}
        </>
    )
}
