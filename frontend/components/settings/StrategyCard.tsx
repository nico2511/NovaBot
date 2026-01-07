import { Zap, Activity } from 'lucide-react'
import { Settings } from '@/hooks/useBotSettings'

interface StrategyCardProps {
    settings: Settings
    statusData: any
    tokenData: any
    onChange: (key: keyof Settings, value: any) => void
    onToggleEngine: () => void
}

export default function StrategyCard({ settings, statusData, tokenData, onChange, onToggleEngine }: StrategyCardProps) {
    return (
        <div className="space-y-6">
            <div className="flex items-center gap-2 mb-4">
                <Zap className="text-blue-500" size={24} />
                <h2 className="text-xl font-bold">Automation & Market</h2>
            </div>

            <div className="bg-white/5 border border-white/10 rounded-2xl p-6 space-y-6">

                {/* Available Assets */}
                <div>
                    <label className="block text-sm font-semibold mb-2 text-gray-300">Active Market</label>
                    <input
                        type="text"
                        value={settings.asset}
                        onChange={(e) => onChange('asset', e.target.value)}
                        list="available-tokens"
                        className="w-full bg-black/50 border border-white/10 rounded-xl px-4 py-3 focus:border-blue-500 transition-colors"
                        placeholder="Type or select: BTC, kPEPE, DOGE..."
                        autoComplete="off"
                    />
                    <datalist id="available-tokens">
                        {tokenData?.success && Array.isArray(tokenData.tokens) && tokenData.tokens.map((token: string) => (
                            <option key={token} value={token} />
                        ))}
                    </datalist>
                    <div className="text-xs text-gray-400 mt-1">
                        {tokenData?.success && tokenData.tokens?.length > 0
                            ? `💡 ${tokenData.tokens.length} tokens available - start typing to see suggestions`
                            : '💡 Type any symbol including k-prefix tokens (kPEPE, kBONK, etc.)'
                        }
                    </div>
                </div>

                {/* Execution Mode */}
                <div>
                    <label className="block text-sm font-semibold mb-2 text-gray-300">Trading Mode</label>
                    <select
                        value={settings.execution_mode}
                        onChange={(e) => onChange('execution_mode', e.target.value)}
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

                <div className="border-t border-white/10 pt-6"></div>

                {/* GLOBAL CONTROLS */}
                <h3 className="text-lg font-bold flex items-center gap-2 mb-4">
                    <Activity size={18} className="text-green-500" /> Bot Controls
                </h3>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    {/* ENGINE START/STOP */}
                    <div className="bg-white/5 border border-white/10 p-4 rounded-xl flex flex-col justify-between">
                        <div className="mb-2">
                            <span className="block font-bold">Engine</span>
                            <span className="text-xs text-gray-400">Main Process</span>
                        </div>
                        <button
                            onClick={onToggleEngine}
                            className={`px-4 py-2 rounded-lg font-bold text-sm transition-all ${statusData?.is_running
                                ? 'bg-red-500/20 text-red-500 border border-red-500/50 hover:bg-red-500/30'
                                : 'bg-green-500/20 text-green-500 border border-green-500/50 hover:bg-green-500/30'
                                }`}
                        >
                            {statusData?.is_running ? '⏸️ STOP' : '▶️ START'}
                        </button>
                    </div>

                    {/* TRADING ENABLE/DISABLE */}
                    <div className="bg-white/5 border border-white/10 p-4 rounded-xl flex flex-col justify-between">
                        <div className="mb-2">
                            <span className="block font-bold">Trading</span>
                            <span className="text-xs text-gray-400">Order Execution</span>
                        </div>
                        <button
                            onClick={() => onChange('trading_enabled', !settings.trading_enabled)}
                            className={`px-4 py-2 rounded-lg font-bold text-sm transition-all ${settings.trading_enabled
                                ? 'bg-green-500/20 text-green-500 border border-green-500/50 hover:bg-green-500/30'
                                : 'bg-yellow-500/20 text-yellow-500 border border-yellow-500/50 hover:bg-yellow-500/30'
                                }`}
                        >
                            {settings.trading_enabled ? '✅ ENABLED' : '🛑 PAUSED'}
                        </button>
                    </div>
                </div>

            </div>
        </div>
    )
}
