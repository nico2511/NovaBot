'use client'

import { useEffect, useState, useRef } from 'react'

interface Log {
    time: string
    message: string
}

export default function LiveLogs() {
    const [logs, setLogs] = useState<Log[]>([])
    const logsEndRef = useRef<HTMLDivElement>(null)

    const scrollToBottom = () => {
        logsEndRef.current?.scrollIntoView({ behavior: "smooth" })
    }

    useEffect(() => {
        const fetchLogs = async () => {
            try {
                const response = await fetch('http://localhost:8000/api/logs')
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

    // Disabled auto-scroll to prevent page jumping
    // useEffect(() => {
    //     scrollToBottom()
    // }, [logs])

    return (
        <div className="bg-surface/50 backdrop-blur border border-border/30 rounded-2xl p-6">
            <div className="flex items-center justify-between mb-4">
                <h3 className="text-lg font-semibold">📝 Live Logs</h3>
                <div className="flex items-center gap-2">
                    <div className="w-2 h-2 bg-success rounded-full animate-pulse"></div>
                    <span className="text-xs text-gray-400">Live</span>
                </div>
            </div>

            <div className="bg-background/80 rounded-lg p-4 h-64 overflow-y-auto font-mono text-sm">
                {logs.length === 0 ? (
                    <div className="text-center text-gray-500 py-8">
                        <div className="text-2xl mb-2">📋</div>
                        <div>No logs yet</div>
                    </div>
                ) : (
                    <div className="space-y-1">
                        {logs.map((log, index) => (
                            <div key={index} className="flex gap-3 text-gray-300 hover:bg-surface/30 px-2 py-1 rounded">
                                <span className="text-gray-500 text-xs">{log.time}</span>
                                <span className="flex-1">{log.message}</span>
                            </div>
                        ))}
                        <div ref={logsEndRef} />
                    </div>
                )}
            </div>
        </div>
    )
}
