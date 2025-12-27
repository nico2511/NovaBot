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
}

export default function StrategyMonitor({ strategies, regime, rsi, atr, adx, ema_20, ema_50, bb, strategy_progress = {} }: StrategyMonitorProps) {
    const getStrategyDetails = (strategy: string) => {
        const details: { [key: string]: { icon: string; description: string; conditions: string[] } } = {
            'Scalp Ema Rsi': {
                icon: '⚡',
                description: 'Fast scalping with EMA crossovers and RSI confirmation',
                conditions: [
                    `EMA 9/21 crossover`,
                    `RSI ${rsi > 50 ? 'bullish' : 'bearish'} (${rsi.toFixed(1)})`,
                    `Trend filter active`
                ]
            },
            'Smcfvg': {
                icon: '🎯',
                description: 'Smart Money Concepts - Fair Value Gap detection',
                conditions: [
                    'Scanning for FVG zones',
                    'Institutional order flow analysis',
                    'Price imbalance detection'
                ]
            },
            'Mean Reversion': {
                icon: '📊',
                description: 'Bollinger Bands mean reversion strategy',
                conditions: [
                    `RSI ${rsi < 30 ? 'oversold' : rsi > 70 ? 'overbought' : 'neutral'}`,
                    'BB bands monitoring',
                    'Reversal signals active'
                ]
            },
            // ... existing strategies ...
            'Institutional Scalp': {
                icon: '🏦',
                description: 'Liquidity grab and stop hunt detection',
                conditions: [
                    'Monitoring recent highs/lows',
                    'Wick analysis active',
                    'Rejection patterns scanning'
                ]
            },
            'Swing Trend Pullback': {
                icon: '📈',
                description: 'Trend following with pullback entries',
                conditions: [
                    `Trend: ${regime}`,
                    'EMA 200 filter active',
                    'Pullback zones identified'
                ]
            }
        }

        return details[strategy] || {
            icon: '🤖',
            description: 'Active strategy monitoring market conditions',
            conditions: ['Analyzing market data', 'Waiting for signals']
        }
    }

    return (
        <div className="bg-surface/50 backdrop-blur border border-border/30 rounded-2xl p-6">
            <div className="flex items-center justify-between mb-6">
                <h3 className="text-lg font-semibold">🔬 Strategy Monitor</h3>
                <div className="flex items-center gap-2">
                    <div className="w-2 h-2 bg-success rounded-full animate-pulse"></div>
                    <span className="text-sm text-gray-400">Live Monitoring</span>
                </div>
            </div>

            {/* Market Overview Moved to Header */}

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
                        {strategies.map((strategy, index) => {
                            const details = getStrategyDetails(strategy)
                            return (
                                <div
                                    key={index}
                                    className="relative bg-gradient-to-br from-primary/10 to-background/40 rounded-lg p-4 border-2 border-primary/50 hover:border-primary/80 transition-all"
                                >
                                    <div className="flex items-start gap-3 mb-3">
                                        <div className="text-2xl">{details.icon}</div>
                                        <div className="flex-1">
                                            <div className="font-semibold mb-1 text-primary-light">{strategy}</div>
                                            <div className="text-xs text-gray-400">{details.description}</div>
                                        </div>
                                        <div className="w-2 h-2 bg-success rounded-full animate-pulse"></div>
                                    </div>
                                    <div className="space-y-2">
                                        {details.conditions.map((condition, i) => (
                                            <div key={i} className="flex items-center gap-2 text-sm">
                                                <div className="w-1 h-1 bg-primary rounded-full"></div>
                                                <span className="text-gray-300">{condition}</span>
                                            </div>
                                        ))}
                                    </div>

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
