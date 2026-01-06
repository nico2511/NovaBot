'use client'

import Link from 'next/link'
import { ArrowLeft } from 'lucide-react'
import { useGamification } from '@/hooks/useGamification'

// Components
import LevelCard from '@/components/gamification/LevelCard'
import NextLevelProgress from '@/components/gamification/NextLevelProgress'
import PerksList from '@/components/gamification/PerksList'
import GamificationRules from '@/components/gamification/GamificationRules'
import GamificationFAQ from '@/components/gamification/GamificationFAQ'

export default function GamificationPage() {
    const { gamStatus, isLoading } = useGamification()

    if (isLoading || !gamStatus) {
        return (
            <div className="min-h-screen bg-[#050505] flex items-center justify-center">
                <div className="text-center">
                    <div className="w-12 h-12 border-4 border-purple-500 border-t-transparent rounded-full animate-spin mx-auto mb-4"></div>
                    <p className="text-gray-400">Loading your profile...</p>
                </div>
            </div>
        )
    }

    return (
        <div className="min-h-screen bg-[#050505] text-white p-6">
            <div className="max-w-6xl mx-auto space-y-8">
                {/* Header */}
                <div className="flex items-center justify-between">
                    <div>
                        <h1 className="text-4xl font-bold bg-gradient-to-r from-purple-400 to-pink-400 bg-clip-text text-transparent">
                            Trader Journey
                        </h1>
                        <p className="text-gray-400 mt-2">Level up your trading career</p>
                    </div>
                    <Link href="/" className="flex items-center gap-2 px-4 py-2 bg-white/5 hover:bg-white/10 rounded-lg transition-colors border border-white/10">
                        <ArrowLeft className="w-4 h-4" />
                        Back to Dashboard
                    </Link>
                </div>

                {/* Main Stats Grid */}
                <div className="grid md:grid-cols-2 gap-6 items-stretch">
                    {/* Left: Level Card (Hero) */}
                    <div className="h-full">
                        <LevelCard status={gamStatus} />
                    </div>

                    {/* Right: Progress & Current Perks */}
                    <div className="space-y-6 flex flex-col h-full">
                        {gamStatus.progress.next_level && (
                            <NextLevelProgress progress={gamStatus.progress} />
                        )}
                        <div className="flex-1">
                            <PerksList
                                level={gamStatus.level}
                                maxLeverage={gamStatus.max_leverage}
                                allowedTiers={gamStatus.allowed_tiers}
                                maxPositionSize={gamStatus.max_position_size}
                            />
                        </div>
                    </div>
                </div>

                {/* Levels Overview / Rules */}
                <GamificationRules />

                {/* FAQ */}
                <GamificationFAQ />
            </div>
        </div>
    )
}
