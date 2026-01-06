import { Zap, Activity } from 'lucide-react'
import { Settings } from '@/hooks/useBotSettings'

interface ScannerCardProps {
    settings: Settings
    gamStatus: any
    onUpdateScanner: (key: string, value: any) => void
    onToggleGamification: (enabled: boolean) => void
}

export default function ScannerCard({ settings, gamStatus, onUpdateScanner, onToggleGamification }: ScannerCardProps) {
    const scanner = settings.scanner || { enabled: false, interval: 15, min_score: 75, auto_switch: false, gamification_enabled: true }

    return (
        <div className="space-y-6">
            <div className="flex items-center gap-2 mb-4">
                <Activity className="text-purple-500" size={24} />
                <h2 className="text-xl font-bold">Token Scanner</h2>
            </div>
            <div className="bg-white/5 border border-white/10 rounded-2xl p-6 space-y-6">

                {/* Enable Auto-Scan */}
                <div className="flex items-center justify-between bg-black/30 p-4 rounded-xl">
                    <div>
                        <span className="font-semibold block">Enable Auto-Scan</span>
                        <span className="text-xs text-gray-500">Periodically scan for opportunities</span>
                    </div>
                    <input
                        type="checkbox"
                        checked={scanner.enabled}
                        onChange={(e) => onUpdateScanner('enabled', e.target.checked)}
                        className="w-6 h-6 accent-blue-500 rounded cursor-pointer"
                    />
                </div>

                <div className="grid grid-cols-2 gap-4">
                    <div>
                        <label className="text-xs font-semibold text-gray-400">Interval (min)</label>
                        <input
                            type="number"
                            value={scanner.interval}
                            onChange={(e) => onUpdateScanner('interval', parseInt(e.target.value))}
                            className="w-full bg-black/50 border border-white/10 rounded-lg px-3 py-2 mt-1"
                            min="5"
                        />
                    </div>
                    <div>
                        <label className="text-xs font-semibold text-gray-400">Min Score</label>
                        <input
                            type="number"
                            value={scanner.min_score}
                            onChange={(e) => onUpdateScanner('min_score', parseInt(e.target.value))}
                            className="w-full bg-black/50 border border-white/10 rounded-lg px-3 py-2 mt-1"
                            min="0"
                            max="100"
                        />
                    </div>
                </div>

                {/* Auto Switch */}
                <div className="flex items-center justify-between bg-black/30 p-4 rounded-xl">
                    <div>
                        <span className="font-semibold block">Auto-Switch Symbol</span>
                        <span className="text-xs text-gray-500">Switch chart to best opportunity found</span>
                    </div>
                    <input
                        type="checkbox"
                        checked={scanner.auto_switch}
                        onChange={(e) => onUpdateScanner('auto_switch', e.target.checked)}
                        className="w-6 h-6 accent-purple-500 rounded cursor-pointer"
                    />
                </div>

                {/* Gamification Section */}
                <div className="bg-black/30 p-4 rounded-xl border-2 border-yellow-500/30">
                    <div className="flex items-center justify-between mb-4">
                        <div>
                            <span className="font-semibold block flex items-center gap-2">
                                🎮 Gamification
                                <span className="text-xs px-2 py-0.5 bg-yellow-500/20 text-yellow-400 rounded-full">NEW</span>
                            </span>
                            <span className="text-xs text-gray-500">
                                Limit tokens and rules by account level
                            </span>
                        </div>
                        <input
                            type="checkbox"
                            checked={scanner.gamification_enabled !== false}
                            onChange={(e) => onToggleGamification(e.target.checked)}
                            className="w-6 h-6 accent-yellow-500 rounded cursor-pointer"
                        />
                    </div>

                    {scanner.gamification_enabled !== false ? (
                        <div className="space-y-3">
                            <div className="text-xs text-yellow-400 bg-yellow-500/10 border border-yellow-500/30 rounded-lg p-3">
                                🎮 <strong>Gamification ACTIVE</strong>
                            </div>

                            {gamStatus?.gamification && (
                                <div className="grid grid-cols-2 gap-2 text-xs">
                                    <div className="bg-white/5 p-2 rounded border border-white/10">
                                        <div className="text-gray-400">Your Level</div>
                                        <div className="font-bold text-yellow-400">{gamStatus.gamification.level}</div>
                                    </div>
                                    <div className="bg-white/5 p-2 rounded border border-white/10">
                                        <div className="text-gray-400">Max Leverage</div>
                                        <div className="font-bold text-white">{gamStatus.gamification.max_leverage}x</div>
                                    </div>
                                    <div className="bg-white/5 p-2 rounded border border-white/10 col-span-2">
                                        <div className="text-gray-400">Allowed Tiers</div>
                                        <div className="font-bold text-white flex flex-wrap gap-1 mt-1">
                                            {gamStatus.gamification.allowed_tiers.map((t: string) => (
                                                <span key={t} className="px-1.5 py-0.5 bg-white/10 rounded">{t}</span>
                                            ))}
                                        </div>
                                    </div>
                                    <div className="bg-white/5 p-2 rounded border border-white/10 col-span-2">
                                        <div className="text-gray-400">Position Limit</div>
                                        <div className="font-bold text-white">
                                            {gamStatus.gamification.max_position_size
                                                ? `$${gamStatus.gamification.max_position_size} USDC`
                                                : 'UNLIMITED'}
                                        </div>
                                    </div>
                                </div>
                            )}
                        </div>
                    ) : (
                        <div className="text-xs text-blue-400 bg-blue-500/10 border border-blue-500/30 rounded-lg p-3">
                            🌍 <strong>Gamification OFF:</strong> Full market access (All Tokens, Max Lev 50x)
                        </div>
                    )}
                </div>
            </div>
        </div>
    )
}
