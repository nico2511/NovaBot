
import { Target, Lock, CheckCircle } from 'lucide-react'

export default function QuestPanel() {
    // Mock Data for now - could be fetched from API
    const quests = [
        { id: 1, title: "Maître du Volume", desc: "Exécuter 10 trades automatiques", progress: 4, target: 10, xp: 500, active: true },
        { id: 2, title: "Sniper Profit", desc: "Gagner 100 USDC de profit", progress: 20, target: 100, xp: 1000, active: true },
        { id: 3, title: "Légende Hyperliquid", desc: "Atteindre 10k de volume", progress: 0, target: 10000, xp: 5000, locked: true },
    ]

    return (
        <div className="p-4 bg-background/40 backdrop-blur-md rounded-xl border border-border/40 flex flex-col gap-4">
            <div className="flex items-center justify-between">
                <div className="flex items-center gap-2 text-primary">
                    <Target size={18} />
                    <h3 className="font-bold uppercase tracking-wider text-sm">Quêtes du Jour</h3>
                </div>
                <div className="text-[10px] bg-white/5 border border-white/10 px-2 py-0.5 rounded text-gray-400">
                    Reset: 4h 12m
                </div>
            </div>

            <div className="flex flex-col gap-3 overflow-y-auto max-h-[200px] pr-2 custom-scrollbar">
                {quests.map(quest => (
                    <div
                        key={quest.id}
                        className={`relative p-3 rounded-lg border flex flex-col gap-2 transition-all group overflow-hidden
                        ${quest.locked
                                ? 'bg-black/20 border-white/5 opacity-50'
                                : 'bg-gradient-to-br from-white/5 to-transparent border-white/10 hover:border-primary/30 hover:bg-white/10'
                            }`}
                    >
                        {/* Header */}
                        <div className="flex items-center justify-between z-10">
                            <span className={`text-sm font-bold ${quest.locked ? 'text-gray-600' : 'text-white'}`}>
                                {quest.title}
                            </span>
                            <span className={`text-xs font-bold ${quest.locked ? 'text-gray-700' : 'text-primary'}`}>
                                +{quest.xp} XP
                            </span>
                        </div>

                        {/* Description */}
                        <span className="text-xs text-gray-500 z-10">{quest.desc}</span>

                        {/* Progress */}
                        {!quest.locked && (
                            <div className="w-full h-1.5 bg-black/50 rounded-full overflow-hidden mt-1 z-10">
                                <div
                                    className="h-full bg-gradient-to-r from-blue-500 to-primary"
                                    style={{ width: `${(quest.progress / quest.target) * 100}%` }}
                                />
                            </div>
                        )}

                        {/* Status Footer */}
                        <div className="flex justify-end z-10">
                            {!quest.locked ? (
                                <span className="text-[10px] font-mono text-gray-400">
                                    {quest.progress}/{quest.target} {quest.target > 100 ? 'USDC' : ''}
                                </span>
                            ) : (
                                <Lock size={12} className="text-gray-600" />
                            )}
                        </div>

                        {/* Background Effect */}
                        {!quest.locked && (
                            <div className="absolute inset-0 bg-primary/5 translate-y-full group-hover:translate-y-0 transition-transform duration-500 rounded-lg pointer-events-none" />
                        )}
                    </div>
                ))}
            </div>

            <style jsx global>{`
                .custom-scrollbar::-webkit-scrollbar {
                    width: 4px;
                }
                .custom-scrollbar::-webkit-scrollbar-track {
                    background: rgba(255, 255, 255, 0.05);
                }
                .custom-scrollbar::-webkit-scrollbar-thumb {
                    background: rgba(255, 255, 255, 0.1);
                    border-radius: 2px;
                }
                .custom-scrollbar::-webkit-scrollbar-thumb:hover {
                    background: rgba(34, 197, 94, 0.3);
                }
            `}</style>
        </div>
    )
}
