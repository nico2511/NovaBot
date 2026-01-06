
interface SafetyBannerProps {
    isEnabled: boolean
}

export default function SafetyBanner({ isEnabled }: SafetyBannerProps) {
    if (isEnabled) return null

    return (
        <div className="bg-yellow-500/10 border-l-4 border-yellow-500 text-yellow-500 p-4 mb-6 rounded-r bg-surface shadow-lg backdrop-blur">
            <div className="flex items-center">
                <div className="font-bold text-lg mr-2">⚠️ TRADING DISABLED</div>
                <div className="text-sm opacity-80">
                    The bot is currently in safe mode. No trades will be executed.
                    <a href="/config" className="underline ml-2 hover:text-white">Enable in Config</a>
                </div>
            </div>
        </div>
    )
}
