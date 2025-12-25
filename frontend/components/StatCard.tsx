interface StatCardProps {
    icon: string
    label: string
    value: string | number
    delta?: string
    color?: 'blue' | 'green' | 'orange' | 'purple' | 'red' | 'cyan'
}

const colorClasses = {
    blue: 'border-primary/30 hover:border-primary',
    green: 'border-success/30 hover:border-success',
    orange: 'border-warning/30 hover:border-warning',
    purple: 'border-purple-500/30 hover:border-purple-500',
    red: 'border-error/30 hover:border-error',
    cyan: 'border-cyan-500/30 hover:border-cyan-500',
}

export default function StatCard({ icon, label, value, delta, color = 'blue' }: StatCardProps) {
    return (
        <div className={`bg-surface/50 backdrop-blur border ${colorClasses[color]} rounded-xl p-4 transition-all hover:-translate-y-1 hover:shadow-lg hover:shadow-${color}-500/20`}>
            <div className="text-2xl mb-2">{icon}</div>
            <div className="text-xs text-gray-400 uppercase tracking-wide mb-1">{label}</div>
            <div className="text-xl font-bold mb-1">{value}</div>
            {delta && <div className="text-xs text-gray-500">{delta}</div>}
        </div>
    )
}
