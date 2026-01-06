
interface NextLevelProgressProps {
    progress: {
        current_level: string
        next_level: string | null
        progress_percent: number
        remaining: number
    }
}

export default function NextLevelProgress({ progress }: NextLevelProgressProps) {
    if (!progress.next_level) return null

    return (
        <div className="bg-surface/50 border border-white/10 rounded-xl p-6">
            <h3 className="text-lg font-bold mb-4">Route to {progress.next_level}</h3>

            <div className="flex items-center justify-between text-sm mb-2 text-gray-400">
                <span>Progress</span>
                <span className="text-white font-bold">{progress.progress_percent.toFixed(1)}%</span>
            </div>

            <div className="w-full bg-gray-700/50 rounded-full h-4 mb-4 overflow-hidden border border-white/5">
                <div
                    className="bg-gradient-to-r from-blue-500 to-purple-500 h-full rounded-full transition-all duration-1000 ease-out"
                    style={{ width: `${progress.progress_percent}%` }}
                />
            </div>

            <div className="flex justify-between items-center text-sm">
                <span className="text-gray-400">Current Rank</span>
                <span className="text-gray-400">Target Rank</span>
            </div>
            <div className="flex justify-between items-center font-bold text-lg">
                <span>{progress.current_level}</span>
                <span className="text-purple-400">{progress.next_level}</span>
            </div>

            <div className="mt-4 p-3 bg-blue-500/10 border border-blue-500/20 rounded-lg text-center">
                <p className="text-blue-300 text-sm">
                    🌱 You need <strong className="text-white">${progress.remaining.toFixed(2)}</strong> more to level up!
                </p>
            </div>
        </div>
    )
}
