'use client';

import React, { useEffect, useRef } from 'react';
import { Terminal, Clock, AlertTriangle, AlertCircle, CheckCircle } from 'lucide-react';

interface NotificationLogProps {
    logs: (string | any)[];
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
    const getLogIcon = (log: string | any) => {
        let message = '';
        let level = '';

        if (typeof log === 'string') {
            message = log;
        } else if (log && typeof log === 'object') {
            message = String(log.message || JSON.stringify(log));
            level = String(log.level || '');
        } else {
            message = String(log);
        }

        if (level === 'ERROR' || message.includes('🔴') || message.includes('error') || message.includes('fail')) return <AlertCircle className="w-3 h-3 text-red-500" />;
        if (level === 'WARNING' || message.includes('⚠️') || message.includes('warning')) return <AlertTriangle className="w-3 h-3 text-yellow-500" />;
        if (level === 'SUCCESS' || message.includes('✅') || message.includes('success')) return <CheckCircle className="w-3 h-3 text-green-500" />;
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
                    logs.map((log, index) => {
                        let message = '';
                        let timestamp = null;

                        if (typeof log === 'string') {
                            message = log;
                        } else if (log && typeof log === 'object') {
                            message = String(log.message || '');
                            if (!message && Object.keys(log).length > 0) message = JSON.stringify(log);

                            if (log.timestamp) {
                                timestamp = <span className="text-gray-600 mr-2">[{log.timestamp}]</span>;
                            }
                        } else {
                            message = String(log);
                        }

                        return (
                            <div
                                key={index}
                                className="group flex items-start gap-2 p-1.5 hover:bg-[#1a1a1a] rounded transition-colors"
                            >
                                <div className="mt-0.5 shrink-0 opacity-70">
                                    {getLogIcon(log)}
                                </div>
                                <span className="text-gray-400 break-words leading-tight">
                                    {timestamp}
                                    {message}
                                </span>
                            </div>
                        );
                    })
                )}
            </div>
        </div>
    );
}
