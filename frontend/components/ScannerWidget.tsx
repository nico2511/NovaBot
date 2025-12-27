'use client'

import { useState, useEffect } from 'react'
import axios from 'axios'

interface Opportunity {
    symbol: string
    score: number
    volatility_24h: number
    relative_volume: number
    trend: string
}

interface ScannerWidgetProps {
    onSwitchSymbol: (symbol: string) => void
}

export default function ScannerWidget({ onSwitchSymbol }: ScannerWidgetProps) {
    const [opportunities, setOpportunities] = useState<Opportunity[]>([])
    const [loading, setLoading] = useState(true)

    const fetchOpportunities = async () => {
        try {
            setLoading(true)
            const res = await axios.get('/api/scanner/opportunities?top_n=5')
            if (res.data.success) {
                setOpportunities(res.data.opportunities)
            }
        } catch (e) {
            console.error(e)
        } finally {
            setLoading(false)
        }
    }

    useEffect(() => {
        fetchOpportunities()
        const interval = setInterval(fetchOpportunities, 60000) // Refresh every minute
        return () => clearInterval(interval)
    }, [])

    return (
        <div className="bg-surface border border-border/30 rounded-xl p-4 h-full flex flex-col">
            <div className="flex justify-between items-center mb-4">
                <h3 className="text-lg font-bold flex items-center gap-2">
                    🛰️ Scanner <span className="text-xs bg-primary/20 text-primary px-2 py-0.5 rounded-full">Live</span>
                </h3>
                <button onClick={fetchOpportunities} className="text-sm text-gray-400 hover:text-white">
                    ↻
                </button>
            </div>

            <div className="flex-1 overflow-y-auto min-h-[200px] space-y-2">
                {loading && opportunities.length === 0 ? (
                    <div className="text-center text-gray-500 py-4">Scanning markets...</div>
                ) : (
                    opportunities.map((opp) => (
                        <div key={opp.symbol} className="flex items-center justify-between bg-background/50 p-3 rounded-lg hover:bg-background/80 transition-colors">
                            <div className="flex flex-col">
                                <span className="font-bold text-white">{opp.symbol}</span>
                                <div className="flex items-center gap-2 text-xs">
                                    <span className={opp.score > 70 ? "text-green-400" : "text-yellow-400"}>
                                        Score: {opp.score}
                                    </span>
                                    <span className="text-gray-500">
                                        Vol: {(opp.volatility_24h * 100).toFixed(1)}%
                                    </span>
                                </div>
                            </div>

                            <button
                                onClick={() => onSwitchSymbol(opp.symbol)}
                                className="bg-primary/20 hover:bg-primary text-primary hover:text-white px-3 py-1.5 rounded-md text-xs font-semibold transition-all"
                            >
                                Watch
                            </button>
                        </div>
                    ))
                )}

                {opportunities.length === 0 && !loading && (
                    <div className="text-center text-gray-500 text-sm">No strong signals found</div>
                )}
            </div>
        </div>
    )
}
