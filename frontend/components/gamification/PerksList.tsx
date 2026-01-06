import { Zap, Shield, Trophy } from 'lucide-react'

interface PerksListProps {
    level: string
    maxLeverage: number
    allowedTiers: string[]
    maxPositionSize: number | null
}

export default function PerksList({ level, maxLeverage, allowedTiers, maxPositionSize }: PerksListProps) {
    return (
        <div className="bg-surface/50 border border-white/10 rounded-xl p-6">
            <div className="flex items-center gap-2 mb-6">
                <Trophy className="text-yellow-500" />
                <h3 className="text-lg font-bold">Unlocks & Perks</h3>
            </div>

            <div className="space-y-4">
                {/* Leverage */}
                <div className="flex items-center justify-between p-3 bg-white/5 rounded-lg border border-white/5">
                    <div className="flex items-center gap-3">
                        <div className="p-2 bg-yellow-500/20 rounded-lg text-yellow-500">
                            <Zap size={18} />
                        </div>
                        <div>
                            <div className="font-bold text-sm">Max Leverage</div>
                            <div className="text-xs text-gray-500">Multiplier Power</div>
                        </div>
                    </div>
                    <div className="text-xl font-bold text-yellow-500">{maxLeverage}x</div>
                </div>

                {/* Position Size */}
                <div className="flex items-center justify-between p-3 bg-white/5 rounded-lg border border-white/5">
                    <div className="flex items-center gap-3">
                        <div className="p-2 bg-blue-500/20 rounded-lg text-blue-500">
                            <Shield size={18} />
                        </div>
                        <div>
                            <div className="font-bold text-sm">Max Position Size</div>
                            <div className="text-xs text-gray-500">Risk Limit</div>
                        </div>
                    </div>
                    <div className="text-xl font-bold text-blue-400">
                        {maxPositionSize ? `$${maxPositionSize}` : '∞ Unlimited'}
                    </div>
                </div>

                {/* Tiers */}
                <div className="p-3 bg-white/5 rounded-lg border border-white/5">
                    <div className="flex items-center gap-3 mb-2">
                        <div className="p-2 bg-purple-500/20 rounded-lg text-purple-500">
                            <Trophy size={18} />
                        </div>
                        <div>
                            <div className="font-bold text-sm">Allowed Tiers</div>
                            <div className="text-xs text-gray-500">Tradable Assets</div>
                        </div>
                    </div>
                    <div className="flex flex-wrap gap-1 mt-2">
                        {allowedTiers.map(tier => (
                            <span key={tier} className="px-2 py-1 bg-purple-500/10 border border-purple-500/20 rounded text-xs font-bold text-purple-300">
                                {tier}
                            </span>
                        ))}
                    </div>
                </div>

            </div>
        </div>
    )
}
