'use client';

import React, { useEffect, useRef } from 'react';
import { Terminal, Clock, AlertTriangle, AlertCircle, CheckCircle } from 'lucide-react';

interface NotificationLogProps {
    logs: string[];
}

export default function NotificationLog({ logs = [] }: NotificationLogProps) {
    const scrollRef = useRef<HTMLDivElement>(null);

    // Auto-scroll to bottom directly with DOM for simplicity as ScrollArea might need special handling
    useEffect(() => {
        if (scrollRef.current) {
            // Use setTimeout to ensure DOM is updated
            setTimeout(() => {
                scrollRef.current?.scrollTo({
                    top: scrollRef.current.scrollHeight,
                    behavior: 'smooth'
                });
            }, 100);
        }
    }, [logs]);

    // Helper to parse log level
    const getLogIcon = (log: string) => {
        if (log.includes('🔴') || log.includes('error') || log.includes('fail')) return <AlertCircle className="w-3 h-3 text-red-500" />;
        if (log.includes('⚠️') || log.includes('warning')) return <AlertTriangle className="w-3 h-3 text-yellow-500" />;
        if (log.includes('✅') || log.includes('success')) return <CheckCircle className="w-3 h-3 text-green-500" />;
        return <Clock className="w-3 h-3 text-gray-600" />;
    };

    return (
        <div className="w-full bg-[#111] border border-[#222] rounded-xl overflow-hidden shadow-lg mt-4">
            {/* Header */}
            <div className="flex items-center px-4 py-3 border-b border-[#222] bg-[#161616]">
                <Terminal className="w-4 h-4 text-purple-400 mr-2" />
                <h3 className="text-sm font-semibold text-gray-300">Live Logs</h3>
                <span className="ml-auto text-xs text-gray-600">{logs.length} events</span>
            </div>

            {/* Logs Area */}
            <div
                ref={scrollRef}
                className="h-48 overflow-y-auto p-2 font-mono text-xs space-y-1 scrollbar-thin scrollbar-thumb-gray-800 scrollbar-track-transparent"
            >
                {logs.length === 0 ? (
                    <div className="text-gray-600 text-center py-8 italic">
                        Waiting for events...
                    </div>
                ) : (
                    logs.map((log, index) => (
                        <div
                            key={index}
                            className="group flex items-start gap-2 p-1.5 hover:bg-[#1a1a1a] rounded transition-colors"
                        >
                            <div className="mt-0.5 shrink-0 opacity-70">
                                {getLogIcon(log)}
                            </div>
                            <span className="text-gray-400 break-words leading-tight">
                                {log}
                            </span>
                        </div>
                    ))
                )}
            </div>
        </div>
    );
}
