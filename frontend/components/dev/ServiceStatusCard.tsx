
interface ServiceStatusCardProps {
    name: string
    isHealthy: boolean
    latency?: string | number
    details?: string
}

export default function ServiceStatusCard({ name, isHealthy, latency, details }: ServiceStatusCardProps) {
    return (
        <div className="bg-white/5 border border-white/10 rounded-xl p-4">
            <div className="flex items-center justify-between mb-2">
                <span className="font-bold text-sm text-gray-200">{name}</span>
                <span className={`px-2 py-1 rounded text-[10px] font-bold uppercase ${isHealthy
                        ? 'bg-green-500/20 text-green-400 border border-green-500/30'
                        : 'bg-red-500/20 text-red-400 border border-red-500/30'
                    }`}>
                    {isHealthy ? 'Connected' : 'Disconnected'}
                </span>
            </div>

            <div className="space-y-1">
                {latency && (
                    <div className="flex justify-between text-xs">
                        <span className="text-gray-500">Latency</span>
                        <span className="font-mono text-gray-300">{latency}</span>
                    </div>
                )}
                {details && (
                    <div className="flex justify-between text-xs">
                        <span className="text-gray-500">Details</span>
                        <span className="font-mono text-gray-300">{details}</span>
                    </div>
                )}
            </div>
        </div>
    )
}
