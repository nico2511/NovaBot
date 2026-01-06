import { Shield } from 'lucide-react'
import { Settings } from '@/hooks/useBotSettings'

interface RiskCardProps {
    settings: Settings
    onChange: (key: keyof Settings, value: any) => void
}

export default function RiskCard({ settings, onChange }: RiskCardProps) {
    return (
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
                        onChange={(e) => onChange('size_value', parseFloat(e.target.value))}
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
                        onChange={(e) => onChange('leverage', parseInt(e.target.value))}
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
                        onChange={(e) => onChange('max_positions', parseInt(e.target.value))}
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
                        onChange={(e) => onChange('daily_stop_loss', parseFloat(e.target.value))}
                        className="w-full bg-black/50 border border-red-500/30 rounded-xl px-4 py-3 focus:border-red-500 transition-colors text-red-200"
                        min="1"
                    />
                </div>
            </div>
        </div>
    )
}
