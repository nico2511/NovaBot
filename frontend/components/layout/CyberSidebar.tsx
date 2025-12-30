'use client'

import { Home, Settings, Bot, Trophy, Terminal, Activity } from 'lucide-react'

interface SidebarProps {
    activeTab: string
    setActiveTab: (tab: string) => void
}

const NavItem = ({ icon: Icon, label, id, active, onClick }: { icon: any, label: string, id: string, active: boolean, onClick: () => void }) => {
    return (
        <button
            onClick={onClick}
            className={`w-12 h-12 flex items-center justify-center rounded-xl transition-all duration-300 relative group
            ${active
                    ? 'bg-primary/20 text-primary shadow-[0_0_15px_rgba(34,197,94,0.3)] border border-primary/50'
                    : 'text-gray-500 hover:text-white hover:bg-white/5'
                }`}
        >
            <Icon size={24} strokeWidth={active ? 2.5 : 2} />

            {/* Tooltip */}
            <span className="absolute left-16 bg-black/90 text-white text-xs px-2 py-1 rounded opacity-0 group-hover:opacity-100 transition-opacity border border-border/30 whitespace-nowrap z-50 pointer-events-none">
                {label}
            </span>

            {/* Active Indicator */}
            {active && (
                <div className="absolute left-0 top-1/2 -translate-y-1/2 w-1 h-6 bg-primary rounded-r-full shadow-[0_0_10px_#22c55e]" />
            )}
        </button>
    )
}

export default function CyberSidebar({ activeTab, setActiveTab }: SidebarProps) {
    return (
        <div className="h-screen w-20 flex flex-col items-center py-6 border-r border-border/30 bg-black/40 backdrop-blur-xl z-50">
            {/* Logo */}
            <div className="mb-10 w-10 h-10 bg-gradient-to-br from-primary to-blue-500 rounded-lg flex items-center justify-center shadow-[0_0_20px_rgba(34,197,94,0.4)]">
                <Bot className="text-black" size={24} />
            </div>

            {/* Navigation */}
            <div className="flex flex-col gap-6 flex-1">
                <NavItem
                    icon={Home}
                    label="Dashboard"
                    id="dashboard"
                    active={activeTab === 'dashboard'}
                    onClick={() => setActiveTab('dashboard')}
                />
                <NavItem
                    icon={Activity}
                    label="Strategies"
                    id="strategies"
                    active={activeTab === 'strategies'}
                    onClick={() => setActiveTab('strategies')}
                />
                <NavItem
                    icon={Trophy}
                    label="Quests"
                    id="gamification"
                    active={activeTab === 'gamification'}
                    onClick={() => setActiveTab('gamification')}
                />
            </div>

            {/* Bottom Actions */}
            <div className="flex flex-col gap-6 mt-auto">
                <NavItem
                    icon={Terminal}
                    label="Logs"
                    id="logs"
                    active={activeTab === 'logs'}
                    onClick={() => setActiveTab('logs')}
                />
                <NavItem
                    icon={Settings}
                    label="Settings"
                    id="settings"
                    active={activeTab === 'settings'}
                    onClick={() => setActiveTab('settings')}
                />
            </div>
        </div>
    )
}
