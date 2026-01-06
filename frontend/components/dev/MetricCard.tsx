import { ReactNode } from 'react'

interface MetricCardProps {
    label: string
    value: string | number
    subValue?: string | number
    icon?: ReactNode
    statusColor?: 'green' | 'red' | 'gray' | 'blue' | 'yellow'
}

export default function MetricCard({ label, value, subValue, icon, statusColor }: MetricCardProps) {
    let valueColor = 'text-white'
    if (statusColor === 'green') valueColor = 'text-green-400'
    if (statusColor === 'red') valueColor = 'text-red-400'
    if (statusColor === 'blue') valueColor = 'text-blue-400'
    if (statusColor === 'yellow') valueColor = 'text-yellow-400'

    return (
        <div className="bg-white/5 border border-white/10 rounded-xl p-4 flex flex-col justify-between">
            <div className="flex items-center gap-2 mb-2 text-gray-400 text-xs uppercase tracking-wider font-semibold">
                {icon}
                <span>{label}</span>
            </div>

            <div>
                <div className={`text-xl font-mono font-bold ${valueColor}`}>
                    {value}
                </div>
                {subValue && (
                    <div className="text-xs text-gray-500 font-mono mt-1">
                        {subValue}
                    </div>
                )}
            </div>
        </div>
    )
}
