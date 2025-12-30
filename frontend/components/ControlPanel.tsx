
import { Play, Square, Settings, RefreshCw } from 'lucide-react'
import { useState, useEffect } from 'react'

interface ControlPanelProps {
    symbol: string
    price: number
    isTrading: boolean
    toggleTrading: () => void
    config: any
    updateConfig: (key: string, value: any) => void
}

export default function ControlPanel({ symbol, price, isTrading, toggleTrading, config, updateConfig }: ControlPanelProps) {
    const [localInvestment, setLocalInvestment] = useState(config?.size_value || 100)

    useEffect(() => {
        setLocalInvestment(config?.size_value || 100)
    }, [config])

    const handleInvestmentChange = (val: string) => {
        setLocalInvestment(val)
        updateConfig('size_value', parseFloat(val))
    }

    return (
        <div className="p-5 bg-background/40 backdrop-blur-md rounded-xl border border-border/40 flex flex-col gap-5 h-full relative overflow-hidden group">
            {/* Header */}
            <div className="flex items-center justify-between pb-2 border-b border-white/5">
                <div className="flex items-center gap-2 text-primary">
                    <Settings size={18} />
                    <h3 className="font-bold uppercase tracking-wider text-sm">Configuration</h3>
                </div>
                <div className="text-xs font-mono text-gray-500">HYPE-USD {price?.toFixed(4)}</div>
            </div>

            {/* Inputs - Cyber Style */}
            <div className="grid grid-cols-2 gap-4">
                <div className="flex flex-col gap-1.5">
                    <label className="text-[10px] uppercase text-gray-500 font-bold tracking-wider ml-1">Risk Mode</label>
                    <div className="relative">
                        <select
                            className="w-full bg-black/40 border border-white/10 rounded px-3 py-2 text-sm text-white focus:border-primary/50 focus:outline-none focus:shadow-[0_0_10px_rgba(34,197,94,0.1)] appearance-none"
                            value={config?.risk_level || 'Normal'}
                            onChange={(e) => updateConfig('risk_level', e.target.value)}
                        >
                            <option>Conservative</option>
                            <option>Normal</option>
                            <option>Aggressive</option>
                            <option>Degenerate</option>
                        </select>
                        <div className="absolute right-3 top-1/2 -translate-y-1/2 pointer-events-none text-gray-500">▼</div>
                    </div>
                </div>

                <div className="flex flex-col gap-1.5">
                    <label className="text-[10px] uppercase text-gray-500 font-bold tracking-wider ml-1">Investment (USDC)</label>
                    <input
                        type="number"
                        value={localInvestment}
                        onChange={(e) => handleInvestmentChange(e.target.value)}
                        className="w-full bg-black/40 border border-white/10 rounded px-3 py-2 text-sm text-white font-mono focus:border-primary/50 focus:outline-none focus:shadow-[0_0_10px_rgba(34,197,94,0.1)]"
                    />
                </div>
            </div>

            {/* Price Range (Visual Only for now) */}
            <div className="grid grid-cols-2 gap-4">
                <div className="flex flex-col gap-1.5">
                    <label className="text-[10px] uppercase text-gray-500 font-bold tracking-wider ml-1">Min Price</label>
                    <input type="text" value={(price * 0.95).toFixed(2)} disabled className="w-full bg-black/20 border border-white/5 rounded px-3 py-2 text-sm text-gray-500 font-mono disabled:opacity-50" />
                </div>
                <div className="flex flex-col gap-1.5">
                    <label className="text-[10px] uppercase text-gray-500 font-bold tracking-wider ml-1">Max Price</label>
                    <input type="text" value={(price * 1.05).toFixed(2)} disabled className="w-full bg-black/20 border border-white/5 rounded px-3 py-2 text-sm text-gray-500 font-mono disabled:opacity-50" />
                </div>
            </div>

            <div className="flex-1" />

            {/* BIG ACTION BUTTON */}
            <button
                onClick={toggleTrading}
                className={`w-full py-4 rounded font-bold text-lg uppercase tracking-widest transition-all duration-300 flex items-center justify-center gap-3 relative overflow-hidden group
                ${isTrading
                        ? 'bg-red-500/10 text-red-500 border border-red-500/50 hover:bg-red-500/20 shadow-[0_0_20px_rgba(239,68,68,0.2)]'
                        : 'bg-primary/10 text-primary border border-primary/50 hover:bg-primary/20 shadow-[0_0_20px_rgba(34,197,94,0.2)]'
                    }`}
            >
                {/* Scanline effect */}
                <div className="absolute inset-0 bg-gradient-to-b from-transparent via-white/5 to-transparent h-[200%] w-full -translate-y-full group-hover:translate-y-full transition-transform duration-1000 pointer-events-none" />

                {isTrading ? (
                    <>
                        <Square size={20} fill="currentColor" />
                        STOP BOT
                    </>
                ) : (
                    <>
                        <Play size={20} fill="currentColor" />
                        LANCER LE BOT
                    </>
                )}
            </button>
        </div>
    )
}
