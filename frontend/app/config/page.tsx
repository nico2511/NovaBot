'use client'

import { useBotSettings } from '@/hooks/useBotSettings'
import StrategyCard from '@/components/settings/StrategyCard'
import RiskCard from '@/components/settings/RiskCard'
import ScannerCard from '@/components/settings/ScannerCard'

export default function ConfigPage() {
    const {
        settings,
        statusData,
        tokenData,
        gamStatus,
        isLoading,
        isSaving,
        updateSettings,
        updateScannerSettings,
        saveSettings,
        toggleEngine,
        toggleGamification
    } = useBotSettings()

    if (isLoading) {
        return (
            <div className="min-h-screen bg-[#050505] text-white flex items-center justify-center">
                <div className="text-center">
                    <div className="w-12 h-12 border-4 border-blue-500 border-t-transparent rounded-full animate-spin mx-auto mb-4"></div>
                    <p className="text-gray-400">Loading configuration...</p>
                </div>
            </div>
        )
    }

    return (
        <div className="min-h-screen bg-[#050505] text-white p-8 pb-32">
            <div className="max-w-4xl mx-auto">
                <div className="flex items-center justify-between mb-8">
                    <div>
                        <h1 className="text-4xl font-bold mb-2">⚙️ Bot Configuration</h1>
                        <p className="text-gray-400">Manage trading pairs, risk, and automation settings</p>
                    </div>
                </div>

                <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
                    {/* Left Column: Strategy & Automation */}
                    <div className="space-y-8">
                        <StrategyCard
                            settings={settings}
                            statusData={statusData}
                            tokenData={tokenData}
                            onChange={updateSettings}
                            onToggleEngine={toggleEngine}
                        />
                        <ScannerCard
                            settings={settings}
                            gamStatus={gamStatus}
                            onUpdateScanner={updateScannerSettings}
                            onToggleGamification={toggleGamification}
                        />
                    </div>

                    {/* Right Column: Risk Management */}
                    <div className="space-y-8">
                        <RiskCard
                            settings={settings}
                            onChange={updateSettings}
                        />

                        {/* Summary Widget */}
                        <div className="bg-gradient-to-br from-blue-900/20 to-purple-900/20 border border-white/10 p-6 rounded-2xl">
                            <h3 className="text-lg font-bold mb-4">📊 Configuration Summary</h3>
                            <div className="space-y-2 text-sm">
                                <div className="flex justify-between">
                                    <span className="text-gray-400">Target Asset</span>
                                    <span className="font-mono text-blue-400">{settings.asset}</span>
                                </div>
                                <div className="flex justify-between">
                                    <span className="text-gray-400">Mode</span>
                                    <span className={`font-bold ${settings.execution_mode.includes('Auto') ? 'text-green-400' : 'text-orange-400'}`}>
                                        {settings.execution_mode.includes('Auto') ? 'LIVE TRADING' : 'SIMULATION'}
                                    </span>
                                </div>
                                <div className="flex justify-between">
                                    <span className="text-gray-400">Max Risk</span>
                                    <span className="font-mono text-red-300">-${settings.daily_stop_loss} / day</span>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            {/* Floating Save Button */}
            <div className="fixed bottom-8 left-1/2 transform -translate-x-1/2 w-full max-w-md px-4 z-50">
                <button
                    onClick={saveSettings}
                    disabled={isSaving}
                    className={`w-full py-4 rounded-xl font-bold text-lg shadow-2xl transition-all ${isSaving
                            ? 'bg-gray-600 cursor-not-allowed opacity-80'
                            : 'bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-500 hover:to-purple-500 scale-100 hover:scale-105'
                        }`}
                >
                    {isSaving ? '💾 Saving Changes...' : '💾 Apply Configuration'}
                </button>
            </div>
        </div>
    )
}
