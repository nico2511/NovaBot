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
    hideHeader?: boolean
    embedded?: boolean
}

export default function StrategyMonitor({ strategies, regime, rsi, atr, adx, ema_20, ema_50, bb, strategy_progress = {}, hideHeader = false, embedded = false }: StrategyMonitorProps) {
    const getStrategyDetails = (strategy: string) => {
        const details: { [key: string]: { icon: string; description: string; conditions: string[]; params?: string[] } } = {
            'Scalp Ema Rsi': {
                icon: '⚡',
                description: 'Trend following momentum scalp. *DISABLED*',
                conditions: [
                    'EMA Cross (9/21) [Inactive]',
                    'RSI Momentum Filter',
                    'High Drawdown Risk'
                ],
                params: ['EMA: 9/21', 'RSI: 14', 'Threshold: 50-70']
            },
            'Institutional Scalp': {
                icon: '🏦',
                description: 'Liquidity Grab & Sweep Detection. (Optimized: Long Only)',
                conditions: [
                    'Sweep of 20-candle High/Low',
                    'Reclaim confirmation (Wick > 50%)',
                    'Direction: LONG ONLY active'
                ],
                params: ['Lookback: 20 candles', 'Reclaim: 50%', 'Longs Only']
            },
            'Golden Cross': {
                icon: '✨',
                description: 'Major Trend Filter (EMA 50/200)',
                conditions: [
                    'Weekly trend alignment',
                    'Low frequency / High conviction',
                    'Safety fuse for trending markets'
                ],
                params: ['EMA: 50/200', 'Timeframe: Weekly', 'Type: Trend Filter']
            },
            'Elastic Reversion': {
                icon: '🪀',
                description: 'Range mean reversion (Oversold bounce)',
                conditions: [
                    'RSI Extreme (< 20)',
                    'Price vs EMA Extension',
                    'Active in RANGE regime'
                ],
                params: ['RSI: < 20', 'Regime: RANGE', 'Target: EMA20']
            },
            'Smart Trend': {
                icon: '🧠',
                description: 'AI-assisted Micro-Structure Analysis',
                conditions: [
                    '1m Micro-BOS detection',
                    'Volume Profile analysis',
                    'Live execution only'
                ],
                params: ['Timeframe: 1m', 'AI: Gemini', 'Confidence: >75%']
            },
            'Smart Mean Reversion': {
                icon: '🎣',
                description: 'Bottom Fishing with Momentum Floor',
                conditions: [
                    'RSI < 30 (Oversold)',
                    'ROC > -15% (Momentum Floor)',
                    'Price < BB Lower + Stabilization'
                ],
                params: ['RSI: < 30', 'ROC: > -15%', 'BB: 20/2.0', 'SL: Low-3 - 0.5%']
            }
        }

        return details[strategy] || {
            icon: '🤖',
            description: 'Active strategy monitoring market conditions',
            conditions: ['Analyzing market data', 'Waiting for signals']
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

                                    {/* Parameters Section */}
                                    {details.params && (
                                        <div className="mt-3 pt-3 border-t border-border/20">
                                            <div className="text-xs text-gray-500 mb-2 font-semibold">Parameters:</div>
                                            <div className="flex flex-wrap gap-2">
                                                {details.params.map((param, i) => (
                                                    <span key={i} className="text-xs bg-primary/10 text-primary-light px-2 py-1 rounded border border-primary/20">
                                                        {param}
                                                    </span>
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
