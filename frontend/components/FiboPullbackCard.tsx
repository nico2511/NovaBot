'use client'

import { TrendingUp, Target, Shield, Percent } from 'lucide-react'

interface FiboPullbackCardProps {
    strategy?: {
        name: string
        progress: number
        conditions?: Array<{
            name: string
            status: boolean
            value: string
        }>
    }
    metadata?: {
        swing_high?: number
        swing_low?: number
        fibo_618?: number
        fibo_786?: number
        adx?: number
        rr_ratio?: number
    }
}

export default function FiboPullbackCard({ strategy, metadata }: FiboPullbackCardProps) {
    const progress = strategy?.progress || 0
    const conditions = strategy?.conditions || []

    // Extract key metrics
    const swingHigh = metadata?.swing_high
    const swingLow = metadata?.swing_low
    const fibo618 = metadata?.fibo_618
    const fibo786 = metadata?.fibo_786
    const adx = metadata?.adx
    const rrRatio = metadata?.rr_ratio

    return (
        <div className="bg-gradient-to-br from-purple-500/10 to-blue-500/10 border border-purple-500/20 rounded-xl p-6 space-y-4">
            {/* Header */}
            <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-lg bg-purple-500/20 flex items-center justify-center">
                        <TrendingUp className="text-purple-400" size={20} />
                    </div>
                    <div>
                        <h3 className="font-bold text-white">Fibonacci Pullback</h3>
                        <p className="text-xs text-gray-400">Sniper Entries on 61.8% Retracements</p>
                    </div>
                </div>
                <div className={`px-3 py-1 rounded-full text-xs font-bold ${progress >= 80 ? 'bg-green-500/20 text-green-400' :
                        progress >= 50 ? 'bg-yellow-500/20 text-yellow-400' :
                            'bg-gray-500/20 text-gray-400'
                    }`}>
                    {progress}%
                </div>
            </div>

            {/* Progress Bar */}
            <div className="space-y-2">
                <div className="flex justify-between text-xs text-gray-400">
                    <span>Setup Progress</span>
                    <span>{progress}/100</span>
                </div>
                <div className="h-2 bg-gray-800 rounded-full overflow-hidden">
                    <div
                        className="h-full bg-gradient-to-r from-purple-500 to-blue-500 transition-all duration-500"
                        style={{ width: `${progress}%` }}
                    />
                </div>
            </div>

            {/* Fibonacci Levels */}
            {(swingHigh && swingLow && fibo618) && (
                <div className="grid grid-cols-2 gap-3">
                    <div className="bg-black/30 rounded-lg p-3 space-y-1">
                        <div className="flex items-center gap-2 text-xs text-gray-400">
                            <Target size={14} />
                            <span>Swing High</span>
                        </div>
                        <div className="text-sm font-bold text-white">${swingHigh.toFixed(2)}</div>
                    </div>
                    <div className="bg-black/30 rounded-lg p-3 space-y-1">
                        <div className="flex items-center gap-2 text-xs text-gray-400">
                            <Shield size={14} />
                            <span>Swing Low</span>
                        </div>
                        <div className="text-sm font-bold text-white">${swingLow.toFixed(2)}</div>
                    </div>
                    <div className="bg-purple-500/10 border border-purple-500/30 rounded-lg p-3 space-y-1">
                        <div className="flex items-center gap-2 text-xs text-purple-400">
                            <Percent size={14} />
                            <span>Fibo 61.8%</span>
                        </div>
                        <div className="text-sm font-bold text-purple-300">${fibo618.toFixed(2)}</div>
                    </div>
                    <div className="bg-red-500/10 border border-red-500/30 rounded-lg p-3 space-y-1">
                        <div className="flex items-center gap-2 text-xs text-red-400">
                            <Shield size={14} />
                            <span>Fibo 78.6%</span>
                        </div>
                        <div className="text-sm font-bold text-red-300">${fibo786?.toFixed(2) || 'N/A'}</div>
                    </div>
                </div>
            )}

            {/* Key Metrics */}
            {(adx || rrRatio) && (
                <div className="flex gap-3">
                    {adx && (
                        <div className="flex-1 bg-black/30 rounded-lg p-3">
                            <div className="text-xs text-gray-400 mb-1">ADX Strength</div>
                            <div className={`text-lg font-bold ${adx >= 25 ? 'text-green-400' :
                                    adx >= 20 ? 'text-yellow-400' :
                                        'text-gray-400'
                                }`}>
                                {adx.toFixed(1)}
                            </div>
                        </div>
                    )}
                    {rrRatio && (
                        <div className="flex-1 bg-black/30 rounded-lg p-3">
                            <div className="text-xs text-gray-400 mb-1">Risk:Reward</div>
                            <div className={`text-lg font-bold ${rrRatio >= 2.0 ? 'text-green-400' :
                                    rrRatio >= 1.5 ? 'text-yellow-400' :
                                        'text-red-400'
                                }`}>
                                1:{rrRatio.toFixed(1)}
                            </div>
                        </div>
                    )}
                </div>
            )}

            {/* Conditions */}
            {conditions.length > 0 && (
                <div className="space-y-2">
                    <div className="text-xs font-semibold text-gray-400 uppercase">Conditions</div>
                    <div className="space-y-1.5">
                        {conditions.map((cond, idx) => (
                            <div key={idx} className="flex items-center justify-between text-xs">
                                <div className="flex items-center gap-2">
                                    <div className={`w-1.5 h-1.5 rounded-full ${cond.status ? 'bg-green-500' : 'bg-gray-600'
                                        }`} />
                                    <span className={cond.status ? 'text-gray-300' : 'text-gray-500'}>
                                        {cond.name}
                                    </span>
                                </div>
                                <span className={`font-mono ${cond.status ? 'text-green-400' : 'text-gray-500'
                                    }`}>
                                    {cond.value}
                                </span>
                            </div>
                        ))}
                    </div>
                </div>
            )}

            {/* Status Message */}
            <div className={`text-xs text-center py-2 rounded-lg ${progress >= 80 ? 'bg-green-500/10 text-green-400' :
                    progress >= 50 ? 'bg-yellow-500/10 text-yellow-400' :
                        'bg-gray-800/50 text-gray-500'
                }`}>
                {progress >= 80 ? '🎯 Entry Zone Reached - Ready for Signal' :
                    progress >= 50 ? '⏳ Waiting for Pullback to 61.8%' :
                        '🔍 Scanning for Valid Swing Structure'}
            </div>
        </div>
    )
}
