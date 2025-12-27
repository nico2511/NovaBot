'use client'

interface CryptoWeatherProps {
    regime: string
    adx: number
    trend?: string
    rsi?: number
    ema_20?: number
    ema_50?: number
    atr?: number
}

export default function CryptoWeather({ regime, adx, trend, rsi, ema_20, ema_50, atr }: CryptoWeatherProps) {
    let weatherIcon = '☁️' // Cloudy (Range)
    let weatherText = 'Overcast (Range)'
    let color = 'text-gray-400'

    if (regime === 'TREND') {
        if (adx > 40) {
            weatherIcon = '🌪️' // Stormy/Strong Trend
            weatherText = 'Turbulent (Strong Trend)'
            color = 'text-yellow-400'
        } else {
            weatherIcon = '☀️' // Sunny
            weatherText = 'Clear Skies (Trending)'
            color = 'text-yellow-500'
        }
    } else if (regime === 'RANGE') {
        if (adx < 15) {
            weatherIcon = '🌫️' // Foggy
            weatherText = 'Foggy (Low Volatility)'
            color = 'text-blue-300'
        }
    }

    return (
        <div className="bg-gradient-to-br from-blue-900/30 to-surface border border-white/10 rounded-xl p-3 flex items-center gap-6 shadow-xl backdrop-blur-md">
            {/* Weather Icon & Main Status */}
            <div className="flex items-center gap-3 border-r border-white/10 pr-6">
                <div className="text-4xl filter drop-shadow-lg animate-pulse-slow">
                    {weatherIcon}
                </div>
                <div>
                    <h3 className="text-[10px] font-bold text-gray-400 uppercase tracking-wider">Market Weather</h3>
                    <div className={`text-sm font-bold ${color} leading-tight`}>
                        {weatherText}
                    </div>
                </div>
            </div>

            {/* Metrics Grid (Compact) */}
            <div className="flex items-center gap-6 text-xs">
                {/* Momentum */}
                <div className="text-center">
                    <div className="text-gray-500 mb-0.5">RSI</div>
                    <div className={`font-mono font-bold ${rsi && rsi < 30 ? 'text-success' : rsi && rsi > 70 ? 'text-error' : 'text-gray-300'}`}>
                        {rsi?.toFixed(0) || '--'}
                    </div>
                </div>

                {/* ADX */}
                <div className="text-center">
                    <div className="text-gray-500 mb-0.5">ADX</div>
                    <div className="font-mono font-bold text-gray-300">
                        {adx?.toFixed(0) || '--'}
                    </div>
                </div>

                {/* Trend EMAs */}
                <div className="text-center border-l border-white/10 pl-6">
                    <div className="text-gray-500 mb-0.5">EMA 20/50</div>
                    <div className="font-mono font-bold">
                        <span className="text-blue-400">{ema_20?.toFixed(0) || '-'}</span>
                        <span className="text-gray-600 mx-1">/</span>
                        <span className="text-purple-400">{ema_50?.toFixed(0) || '-'}</span>
                    </div>
                </div>

                {/* Volatility */}
                <div className="text-center">
                    <div className="text-gray-500 mb-0.5">ATR</div>
                    <div className="font-mono font-bold text-gray-300">{atr?.toFixed(1) || '--'}</div>
                </div>
            </div>
        </div>
    )
}
