import { Activity, TrendingUp, Zap, BarChart2, Terminal, Settings, FileText } from 'lucide-react'

interface DashboardTabsProps {
    active: string
    onChange: (tab: string) => void
}

export default function DashboardTabs({ active, onChange }: DashboardTabsProps) {
    const tabs = [
        { id: 'overview', label: 'Price Chart', icon: Activity },
        { id: 'strategies', label: 'Strategies', icon: TrendingUp },
        { id: 'signals', label: 'Trades', icon: Zap },
        { id: 'scanner', label: 'Scanner', icon: BarChart2 },

        { id: 'logs', label: 'System Logs', icon: Terminal },
        { id: 'config', label: 'Config', icon: Settings, external: true },
        { id: 'dev', label: 'Dev Ops', icon: Terminal, external: true },
    ]

    return (
        <div className="flex border-b border-white/5 overflow-x-auto">
            {tabs.map((tab) => {
                if (tab.external) {
                    return (
                        <a
                            key={tab.id}
                            href={`/${tab.id}`}
                            target="_blank"
                            rel="noopener noreferrer"
                            className={`flex-1 min-w-[120px] py-4 text-sm font-bold flex items-center justify-center gap-2 transition-all 
                                ${tab.id === 'dev' ? 'text-purple-400 hover:text-purple-300 hover:bg-purple-500/10' : ''}
                                ${tab.id === 'config' ? 'text-orange-400 hover:text-orange-300 hover:bg-orange-500/10' : ''}
                            `}
                        >
                            <tab.icon size={16} />
                            {tab.label}
                        </a>
                    )
                }
                return (
                    <button
                        key={tab.id}
                        onClick={() => onChange(tab.id)}
                        className={`flex-1 min-w-[120px] py-4 text-sm font-bold flex items-center justify-center gap-2 transition-all ${active === tab.id
                            ? 'text-blue-400 border-b-2 border-blue-500 bg-white/[0.02]'
                            : 'text-gray-500 hover:text-gray-300 hover:bg-white/[0.01]'
                            }`}
                    >
                        <tab.icon size={16} className={active === tab.id ? 'text-blue-400' : 'text-gray-500'} />
                        {tab.label}
                    </button>
                )
            })}
        </div>
    )
}
