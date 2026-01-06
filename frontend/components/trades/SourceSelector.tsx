
interface SourceSelectorProps {
    value: 'local' | 'hyperliquid' | 'all'
    onChange: (val: 'local' | 'hyperliquid' | 'all') => void
}

export default function SourceSelector({ value, onChange }: SourceSelectorProps) {
    return (
        <div className="flex items-center gap-1 bg-white/5 rounded-lg p-1 border border-white/10">
            <button
                onClick={() => onChange('all')}
                className={`px-3 py-1.5 rounded text-xs font-bold transition-all ${value === 'all'
                    ? 'bg-blue-600 text-white shadow-lg'
                    : 'text-gray-400 hover:text-white hover:bg-white/5'
                    }`}
            >
                ALL
            </button>
            <button
                onClick={() => onChange('local')}
                className={`px-3 py-1.5 rounded text-xs font-bold transition-all ${value === 'local'
                    ? 'bg-blue-600 text-white shadow-lg'
                    : 'text-gray-400 hover:text-white hover:bg-white/5'
                    }`}
            >
                🤖 BOT
            </button>
            <button
                onClick={() => onChange('hyperliquid')}
                className={`px-3 py-1.5 rounded text-xs font-bold transition-all ${value === 'hyperliquid'
                    ? 'bg-blue-600 text-white shadow-lg'
                    : 'text-gray-400 hover:text-white hover:bg-white/5'
                    }`}
            >
                📊 HYPER
            </button>
        </div>
    )
}
