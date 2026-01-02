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
        const details: { [key: string]: { icon: string; description: string; conditions: string[] } } = {
            'Scalp Ema Rsi': {
                icon: '⚡',
                description: 'Trend following momentum scalp. *DISABLED*',
                conditions: [
                    'EMA Cross (9/21) [Inactive]',
                    'RSI Momentum Filter',
                    'High Drawdown Risk'
                ]
            },
            'Institutional Scalp': {
                icon: '🏦',
                description: 'Liquidity Grab & Sweep Detection. (Optimized: Long Only)',
                conditions: [
                    'Sweep of 20-candle High/Low',
                    'Reclaim confirmation (Wick > 50%)',
                    'Direction: LONG ONLY active'
                ]
            },
            'Golden Cross': {
                icon: '✨',
                description: 'Major Trend Filter (EMA 50/200)',
                conditions: [
                    'Weekly trend alignment',
                    'Low frequency / High conviction',
                    'Safety fuse for trending markets'
                ]
            },
            'Elastic Reversion': {
                icon: '🪀',
                description: 'Range mean reversion (Oversold bounce)',
                conditions: [
                    'RSI Extreme (< 20)',
                    'Price vs EMA Extension',
                    'Active in RANGE regime'
                ]
            },
            'Smart Trend': {
                icon: '🧠',
                description: 'AI-assisted Micro-Structure Analysis',
                conditions: [
                    '1m Micro-BOS detection',
                    'Volume Profile analysis',
                    'Live execution only'
                ]
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
