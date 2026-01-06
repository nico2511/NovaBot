import { Zap, Shield, Trophy, TrendingUp, Lock } from 'lucide-react'

export default function GamificationRules() {
    return (
        <div className="space-y-6">
            <h2 className="text-2xl font-bold">📊 Level System Overview</h2>

            <div className="grid md:grid-cols-3 gap-6">
                {/* Goblin */}
                <div className="bg-gradient-to-br from-red-900/20 to-orange-900/20 rounded-xl p-6 border border-red-500/30 relative overflow-hidden">
                    <div className="absolute top-0 right-0 p-4 opacity-10 text-9xl select-none">👺</div>
                    <div className="flex items-center gap-3 mb-4 relative z-10">
                        <span className="text-4xl">👺</span>
                        <div>
                            <h3 className="text-xl font-bold text-red-100">Goblin</h3>
                            <p className="text-sm text-red-400 font-mono">$0 - $100</p>
                        </div>
                    </div>

                    <div className="space-y-3 text-sm relative z-10">
                        <div className="flex items-center gap-2">
                            <Zap className="w-4 h-4 text-yellow-500" />
                            <span>Lev: <strong>3x</strong></span>
                        </div>
                        <div className="flex items-center gap-2">
                            <Shield className="w-4 h-4 text-blue-400" />
                            <span>Size: <strong>$50</strong></span>
                        </div>
                        <div className="mt-4 text-xs text-gray-400 italic">
                            "Perfect for learning with low risk."
                        </div>
                    </div>
                </div>

                {/* Mercenary */}
                <div className="bg-gradient-to-br from-blue-900/20 to-cyan-900/20 rounded-xl p-6 border border-blue-500/30 relative overflow-hidden">
                    <div className="absolute top-0 right-0 p-4 opacity-10 text-9xl select-none">⚔️</div>
                    <div className="flex items-center gap-3 mb-4 relative z-10">
                        <span className="text-4xl">⚔️</span>
                        <div>
                            <h3 className="text-xl font-bold text-blue-100">Mercenary</h3>
                            <p className="text-sm text-blue-400 font-mono">$100 - $500</p>
                        </div>
                    </div>

                    <div className="space-y-3 text-sm relative z-10">
                        <div className="flex items-center gap-2">
                            <Zap className="w-4 h-4 text-yellow-500" />
                            <span>Lev: <strong>5x</strong></span>
                        </div>
                        <div className="flex items-center gap-2">
                            <Shield className="w-4 h-4 text-blue-400" />
                            <span>Size: <strong>$250</strong></span>
                        </div>
                        <div className="mt-4 text-xs text-gray-400 italic">
                            "Unlock more assets and higher limits."
                        </div>
                    </div>
                </div>

                {/* Whale */}
                <div className="bg-gradient-to-br from-purple-900/20 to-pink-900/20 rounded-xl p-6 border border-purple-500/30 relative overflow-hidden">
                    <div className="absolute top-0 right-0 p-4 opacity-10 text-9xl select-none">🐋</div>
                    <div className="flex items-center gap-3 mb-4 relative z-10">
                        <span className="text-4xl">🐋</span>
                        <div>
                            <h3 className="text-xl font-bold text-purple-100">Whale</h3>
                            <p className="text-sm text-purple-400 font-mono">$500+</p>
                        </div>
                    </div>

                    <div className="space-y-3 text-sm relative z-10">
                        <div className="flex items-center gap-2">
                            <Zap className="w-4 h-4 text-yellow-500" />
                            <span>Lev: <strong>10x</strong></span>
                        </div>
                        <div className="flex items-center gap-2">
                            <Shield className="w-4 h-4 text-blue-400" />
                            <span>Size: <strong>Unlimited</strong></span>
                        </div>
                        <div className="mt-4 text-xs text-gray-400 italic">
                            "Full access to BTC/ETH and maximum power."
                        </div>
                    </div>
                </div>
            </div>
        </div>
    )
}
