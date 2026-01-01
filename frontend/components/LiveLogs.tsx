'use client'

import { useEffect, useState, useRef } from 'react'

interface Log {
    time: string
    message: string
}

export default function LiveLogs({ embedded = false, hideHeader = false }: { embedded?: boolean, hideHeader?: boolean }) {
    const [logs, setLogs] = useState<Log[]>([])
    const [mounted, setMounted] = useState(false)
    const logsEndRef = useRef<HTMLDivElement>(null)

    useEffect(() => { setMounted(true) }, [])

    const scrollToBottom = () => {
        logsEndRef.current?.scrollIntoView({ behavior: "smooth" })
    }

    useEffect(() => {
        const fetchLogs = async () => {
            try {
                const response = await fetch('/api/logs')
                const data = await response.json()
                setLogs(data.logs || [])
            } catch (error) {
                console.error('Failed to fetch logs:', error)
            }
        }

        fetchLogs()
        const interval = setInterval(fetchLogs, 3000) // Update every 3s

        return () => clearInterval(interval)
    }, [])

    // }, [logs])

    if (!mounted) return null;

    const getLogColor = (msg: string) => {
        const message = msg.toLowerCase();
        if (message.includes('error') || message.includes('failed') || message.includes('❌') || message.includes('stop')) return 'text-red-400';
        if (message.includes('warning') || message.includes('⚠️')) return 'text-yellow-400';
        if (message.includes('success') || message.includes('✅') || message.includes('started')) return 'text-green-400';
        if (message.includes('switch') || message.includes('🔄')) return 'text-blue-400';
        if (message.includes('level up') || message.includes('🎉')) return 'text-yellow-300 font-bold'; // Gold for Level Up
        if (message.includes('ai') || message.includes('🤖')) return 'text-purple-400';
        return 'text-gray-300';
    }

    if (embedded) {
        return (
            <div className="h-full flex flex-col">
                {!hideHeader && (
                    <div className="flex items-center justify-between mb-2">
                        <h3 className="text-sm font-semibold">📝 Live Logs</h3>
                        <div className="w-2 h-2 bg-success rounded-full animate-pulse"></div>
                    </div>
                )}
                <div className="bg-background/80 flex-1 overflow-y-auto font-mono text-xs p-2 custom-scrollbar">
                    {logs.length === 0 ? (
                        <div className="text-center text-gray-500 py-8">
                            <div>No logs yet</div>
                        </div>
                    ) : (
                        <div className="space-y-0.5">
                            {logs.map((log, index) => (
                                <div key={index} className={`flex gap-2 hover:bg-white/5 px-2 py-0.5 rounded transition-colors ${getLogColor(log.message)}`}>
                                    <span className="text-gray-600 w-14 shrink-0">{log.time}</span>
                                    <span className="flex-1 break-words">{log.message}</span>
                                </div>
                            ))}
                            <div ref={logsEndRef} />
                        </div>
                    )}
                </div>
            </div>
        )
    }

    return (
        <div className="bg-surface/50 backdrop-blur border border-border/30 rounded-2xl p-6">
            <div className="flex items-center justify-between mb-4">
                <h3 className="text-lg font-semibold">📝 Live Logs</h3>
                <div className="flex items-center gap-2">
                    <div className="w-2 h-2 bg-success rounded-full animate-pulse"></div>
                    <span className="text-xs text-gray-400">Live</span>
                </div>
            </div>

            <div className="bg-background/80 rounded-lg p-4 h-64 overflow-y-auto font-mono text-xs custom-scrollbar">
                {logs.length === 0 ? (
                    <div className="text-center text-gray-500 py-8">
                        <div className="text-2xl mb-2">📋</div>
                        <div>No logs yet</div>
                    </div>
                ) : (
                    <div className="space-y-0.5">
                        {logs.map((log, index) => (
                            <div key={index} className={`flex gap-2 hover:bg-surface/30 px-2 py-0.5 rounded transition-colors ${getLogColor(log.message)}`}>
                                <span className="text-gray-600 w-14 shrink-0">{log.time}</span>
                                <span className="flex-1 break-words">{log.message}</span>
                            </div>
                        ))}
                        <div ref={logsEndRef} />
                    </div>
                )}
            </div>
        </div>
    )
}
