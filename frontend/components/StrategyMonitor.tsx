import useSWR from 'swr'
import { useState } from 'react'

interface StrategyMonitorProps {
    strategies: string[]
    regime: string
    rsi: number
    atr: number
    adx: number
    ema_20?: number
    ema_50?: number
    bb?: { upper: number; middle: number; lower: number }
    strategy_progress?: { [key: string]: number }
    strategy_conditions?: { [key: string]: Array<{ name: string; status: boolean; value: string }> }
    hideHeader?: boolean
    embedded?: boolean
}

const fetcher = (url: string) => fetch(url).then(res => res.json())

export default function StrategyMonitor({ strategies, regime, rsi, atr, adx, ema_20, ema_50, bb, strategy_progress = {}, strategy_conditions = {}, hideHeader = false, embedded = false }: StrategyMonitorProps) {

    // Fetch detailed strategy config from backend
    const { data: strategiesConfig } = useSWR('/api/strategies', fetcher, {
        refreshInterval: 60000, // Refresh every minute
        revalidateOnFocus: false
    })

    const getStrategyDetails = (strategyName: string) => {
        if (strategiesConfig && strategiesConfig.strategies && strategiesConfig.strategies[strategyName]) {
            const cfg = strategiesConfig.strategies[strategyName]

            // Map icon based on name/type
            let icon = '🤖'
            if (strategyName.includes('Scalp')) icon = '⚡'
            if (strategyName.includes('Trend') || strategyName.includes('Bull')) icon = '📈'
            if (strategyName.includes('Reversion') || strategyName.includes('Bounce')) icon = '🎣'
            if (strategyName.includes('Pattern') || strategyName.includes('Double') || strategyName.includes('Head')) icon = '📐'
            if (strategyName.includes('Institutional')) icon = '🏦'
            if (strategyName.includes('Smart Trend')) icon = '🧠'

            return {
                icon: icon,
                description: cfg.description || 'Active strategy',
                conditions: cfg.display_conditions || ['Monitoring market'],
                params: cfg.params || {}
            }
        }

        // Fallback if not loaded yet
        return {
            icon: '⏳',
            description: 'Loading details...',
            conditions: [],
            params: {}
        }
    }

    // Dynamic container class
    const containerClass = embedded
        ? "space-y-6" // No background/border when embedded
        : "bg-surface/50 backdrop-blur border border-border/30 rounded-2xl p-6"

    return (
        <div className={containerClass}>
            {!hideHeader && (
                <div className="flex items-center justify-between mb-6">
                    <h3 className="text-lg font-semibold">🔬 Strategy Monitor</h3>
                    <div className="flex items-center gap-2">
                        <div className="w-2 h-2 bg-success rounded-full animate-pulse"></div>
                        <span className="text-sm text-gray-400">Live Monitoring</span>
                    </div>
                </div>
            )}

            {/* Active Strategies */}
            {strategies.length === 0 ? (
                <div className="text-center py-8 text-gray-500">
                    <div className="text-4xl mb-2">⚠️</div>
                    <div>No active strategies for current market regime</div>
                </div>
            ) : (
                <div className="space-y-4">
                    <div className="text-sm font-semibold text-gray-400 uppercase tracking-wide">
                        Active Strategies ({strategies.length})
                    </div>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        {Array.isArray(strategies) && strategies.map((strategy, index) => {
                            const details = getStrategyDetails(strategy)
                            const dynamicConditions = strategy_conditions[strategy]

                            return (
                                <div
                                    key={index}
                                    className="relative bg-gradient-to-br from-primary/10 to-background/40 rounded-lg p-4 border-2 border-primary/50 hover:border-primary/80 transition-all"
                                >
                                    <div className="flex items-start gap-3 mb-3">
                                        <div className="text-2xl">{details.icon}</div>
                                        <div className="flex-1">
                                            <div className="font-semibold mb-1 text-primary-light capitalize">{strategy.replace(/_/g, ' ')}</div>
                                            <div className="text-xs text-gray-400">{details.description}</div>
                                        </div>
                                        <div className="w-2 h-2 bg-success rounded-full animate-pulse"></div>
                                    </div>

                                    <div className="space-y-2">
                                        {dynamicConditions && dynamicConditions.length > 0 ? (
                                            // Dynamic Conditions from Backend
                                            Array.isArray(dynamicConditions) && dynamicConditions.map((cond, i) => (
                                                <div key={i} className="flex items-center gap-2 text-sm justify-between bg-black/20 p-1 rounded px-2">
                                                    <div className="flex items-center gap-2">
                                                        <div className={`w-1.5 h-1.5 rounded-full ${cond.status ? 'bg-success shadow-[0_0_5px_rgba(34,197,94,0.5)]' : 'bg-red-500/50'}`}></div>
                                                        <span className={cond.status ? 'text-gray-200' : 'text-gray-500'}>{cond.name}</span>
                                                    </div>
                                                    <div className="flex items-center gap-2">
                                                        <span className={`text-xs font-mono font-medium ${cond.status ? 'text-primary-light' : 'text-orange-400'}`}>
                                                            {cond.value}
                                                        </span>
                                                        <span className="text-xs">{cond.status ? '✅' : '❌'}</span>
                                                    </div>
                                                </div>
                                            ))
                                        ) : (
                                            // Static Display Conditions
                                            Array.isArray(details.conditions) && details.conditions.map((condition: string, i: number) => (
                                                <div key={i} className="flex items-center gap-2 text-sm">
                                                    <div className="w-1 h-1 bg-primary rounded-full"></div>
                                                    <span className="text-gray-300">{condition}</span>
                                                </div>
                                            ))
                                        )}
                                    </div>

                                    {/* Parameters Section (Dynamic/Seuils) */}
                                    {details.params && Object.keys(details.params).length > 0 && (
                                        <div className="mt-3 pt-3 border-t border-border/20">
                                            <div className="text-xs text-gray-500 mb-2 font-semibold">Parameters (Seuils):</div>
                                            <div className="flex flex-wrap gap-2">
                                                {Object.entries(details.params).map(([key, value], i) => (
                                                    <div key={i} className="flex flex-col bg-black/30 px-2 py-1 rounded border border-white/5">
                                                        <span className="text-[10px] text-gray-500 uppercase">{key.replace(/_/g, ' ')}</span>
                                                        <span className="text-xs text-primary-light font-mono">{String(value)}</span>
                                                    </div>
                                                ))}
                                            </div>
                                        </div>
                                    )}

                                    {/* Progress Bar */}
                                    {strategy_progress[strategy] !== undefined && (
                                        <div className="mt-4 pt-3 border-t border-border/20">
                                            <div className="flex items-center justify-between mb-2">
                                                <span className="text-xs text-gray-400">Signal Proximity</span>
                                                <span className="text-xs font-semibold text-primary">{strategy_progress[strategy]}%</span>
                                            </div>
                                            <div className="relative h-2 bg-background/50 rounded-full overflow-hidden">
                                                <div
                                                    className={`absolute inset-y-0 left-0 rounded-full transition-all duration-500 ${strategy_progress[strategy] >= 70
                                                        ? 'bg-gradient-to-r from-green-500 to-green-400'
                                                        : strategy_progress[strategy] >= 30
                                                            ? 'bg-gradient-to-r from-yellow-500 to-yellow-400'
                                                            : 'bg-gradient-to-r from-gray-500 to-gray-400'
                                                        }`}
                                                    style={{ width: `${strategy_progress[strategy]}%` }}
                                                ></div>
                                            </div>
                                        </div>
                                    )}
                                </div>
                            )
                        })}
                    </div>
                </div>
            )}
        </div>
    )
}
