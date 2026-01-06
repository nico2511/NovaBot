'use client'

import { Trophy, Zap, Wallet } from 'lucide-react'
import useSWR from 'swr'

interface GamificationStatus {
    level: string
    xp: number
    next_level_xp: number
    balance: number
    multiplier?: number
    rank?: string
}

const fetcher = (url: string) => fetch(url).then(res => res.json())

export default function GamificationHeader() {
    const { data } = useSWR('/api/gamification_status', fetcher, { refreshInterval: 5000, keepPreviousData: true })
    const status = data?.gamification as GamificationStatus

    // Defaults
    const level = status?.level || "Goblin"
    const xp = status?.xp || 0
    const nextXp = status?.next_level_xp || 1000
    const balance = status?.balance || 0
    const progress = Math.min((xp / nextXp) * 100, 100)

    const levelColor = level === 'Whale' ? 'text-purple-400' : level === 'Mercenary' ? 'text-blue-400' : 'text-green-400'

    return (
        <div className="w-full h-16 flex items-center justify-between px-8 border-b border-border/30 bg-black/20 backdrop-blur-sm">
            {/* Left: Branding */}
            <div className="flex items-center gap-3">
                <h1 className="font-bold text-2xl tracking-wider text-white">
                    HYPER<span className="text-primary">BOT</span>
                </h1>
                <span className="px-2 py-0.5 rounded text-[10px] bg-primary/20 text-primary border border-primary/30 uppercase font-bold tracking-widest">
                    V3.0 GAMIFIED
                </span>
            </div>

            {/* Center: Quick Stats */}
            <div className="flex items-center gap-8">
                {/* Balance */}
                <div className="flex items-center gap-3 bg-white/5 border border-white/10 px-4 py-1.5 rounded-full">
                    <Wallet size={16} className="text-gray-400" />
                    <span className="font-mono font-bold text-white">${balance.toFixed(2)} <span className="text-xs text-gray-500">USDC</span></span>
                </div>

                {/* Level Progress */}
                <div className="flex items-center gap-4 min-w-[300px]">
                    <div className="flex flex-col items-end">
                        <span className={`text-sm font-bold uppercase ${levelColor} drop-shadow-[0_0_8px_rgba(0,0,0,0.5)]`}>
                            {level} <span className="text-xs text-white/50 ml-1">LVL {Math.floor(xp / 1000) + 1}</span>
                        </span>
                    </div>

                    <div className="flex-1 h-2 bg-gray-800 rounded-full overflow-hidden relative shadow-inner">
                        <div
                            className="absolute top-0 left-0 h-full bg-gradient-to-r from-primary/50 to-primary transition-all duration-1000 ease-out shadow-[0_0_10px_#22c55e]"
                            style={{ width: `${progress}%` }}
                        />
                    </div>

                    <span className="text-xs font-mono text-gray-400 w-16 text-right">
                        {Math.floor(xp)}/{nextXp} XP
                    </span>
                </div>
            </div>

            {/* Right: User/Profile */}
            <div className="flex items-center gap-4">
                <div className="flex items-center gap-2">
                    <div className="w-8 h-8 rounded-full bg-gradient-to-tr from-gray-700 to-gray-600 border border-white/20" />
                    <div className="flex flex-col text-right leading-none">
                        <span className="text-sm font-bold text-white">Trader0x</span>
                        <span className="text-[10px] text-gray-500 uppercase">Pro Admin</span>
                    </div>
                </div>
            </div>
        </div>
    )
}
