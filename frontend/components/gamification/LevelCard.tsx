import { Shield } from 'lucide-react'
import { GamificationStatus } from '@/hooks/useGamification'
import { useGamification } from '@/hooks/useGamification'

interface LevelCardProps {
    status: GamificationStatus
}

export default function LevelCard({ status }: LevelCardProps) {
    const { getLevelEmoji, getLevelColor } = useGamification() // Or pass helpers as props, but hook is fine if pure function

    return (
        <div className={`bg-gradient-to-br ${getLevelColor(status.level)} p-1 rounded-2xl h-full`}>
            <div className="bg-[#0b0e11] rounded-xl p-6 h-full flex flex-col justify-between">

                <div className="flex items-center justify-between mb-8">
                    <div className="flex items-center gap-4">
                        <span className="text-6xl animate-bounce-slow">{getLevelEmoji(status.level)}</span>
                        <div>
                            <h2 className="text-3xl font-bold text-white">{status.level}</h2>
                            <p className="text-gray-400 font-mono">Balance: <span className="text-white font-bold">${status.balance.toFixed(2)}</span></p>
                        </div>
                    </div>
                </div>

                <div className="p-4 bg-blue-500/10 border border-blue-500/30 rounded-lg">
                    <div className="flex items-start gap-3">
                        <Shield className="w-5 h-5 text-blue-400 mt-0.5" />
                        <div className="flex-1">
                            <h3 className="font-semibold text-blue-300 mb-1 text-sm">Gamification Rules</h3>
                            <p className="text-xs text-gray-400">
                                Apply to <strong>Auto-Trading</strong> only. Manual trading is unrestricted.
                            </p>
                        </div>
                    </div>
                </div>

            </div>
        </div>
    )
}
