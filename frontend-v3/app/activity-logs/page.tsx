'use client';

import React from 'react';
import useSWR from 'swr';
import Link from 'next/link';
import { ArrowLeft, AlertTriangle, CheckCircle, XCircle, Activity, TrendingUp, Info } from 'lucide-react';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8001';

interface LogEntry {
    timestamp: string;
    level: string;
    message: string;
    metadata?: { reason?: string } | null;
}

interface LogsResponse {
    logs: LogEntry[];
    total: number;
}

const fetcher = (url: string) => fetch(url).then((res) => res.json());

export default function LogsPage() {
    const { data, error, isLoading } = useSWR<LogsResponse>(
        `${API_BASE_URL}/api/logs?limit=100`,
        fetcher,
        { refreshInterval: 3000 }
    );

    // Get icon based on log level
    const getIcon = (level: string) => {
        switch (level) {
            case 'VETO':
                return <XCircle className="w-4 h-4 text-amber-500 flex-shrink-0" />;
            case 'ERROR':
                return <AlertTriangle className="w-4 h-4 text-loss flex-shrink-0" />;
            case 'TRADE':
                return <TrendingUp className="w-4 h-4 text-profit flex-shrink-0" />;
            case 'SIGNAL':
                return <Activity className="w-4 h-4 text-blue-400 flex-shrink-0" />;
            case 'SUCCESS':
                return <CheckCircle className="w-4 h-4 text-profit flex-shrink-0" />;
            case 'WARNING':
                return <AlertTriangle className="w-4 h-4 text-amber-400 flex-shrink-0" />;
            default:
                return <Info className="w-4 h-4 text-gray-500 flex-shrink-0" />;
        }
    };

    // Get text color based on log level
    const getTextColor = (level: string): string => {
        switch (level) {
            case 'ERROR':
                return 'text-loss';
            case 'VETO':
                return 'text-amber-400';
            case 'TRADE':
            case 'SUCCESS':
                return 'text-profit';
            case 'SIGNAL':
                return 'text-blue-400';
            case 'WARNING':
                return 'text-amber-300';
            default:
                return 'text-gray-300';
        }
    };

    return (
        <main className="min-h-screen p-4 md:p-8">
            <div className="max-w-4xl mx-auto">
                {/* Header */}
                <div className="flex items-center gap-4 mb-6">
                    <Link
                        href="/"
                        className="p-2 rounded-lg bg-gray-800 hover:bg-gray-700 transition-colors"
                    >
                        <ArrowLeft className="w-5 h-5 text-gray-400" />
                    </Link>
                    <div>
                        <h1 className="text-2xl font-bold text-white">Bot Logs</h1>
                        <p className="text-gray-500 text-sm">Real-time activity feed</p>
                    </div>
                </div>

                {/* Loading State */}
                {isLoading && (
                    <div className="text-center text-gray-400 py-12">
                        <div className="animate-pulse">Loading logs...</div>
                    </div>
                )}

                {/* Error State */}
                {error && (
                    <div className="text-center text-loss py-12">
                        <AlertTriangle className="w-8 h-8 mx-auto mb-2" />
                        <div>Unable to load logs</div>
                    </div>
                )}

                {/* Logs List */}
                {data && (
                    <div className="bg-gray-900/50 border border-gray-800 rounded-lg overflow-hidden">
                        <div className="px-4 py-3 border-b border-gray-800 flex justify-between items-center">
                            <span className="text-sm text-gray-400">
                                {data.total} entries
                            </span>
                            <span className="text-xs text-gray-600">
                                Auto-refresh: 3s
                            </span>
                        </div>

                        <div className="max-h-[70vh] overflow-y-auto">
                            {data.logs.length === 0 ? (
                                <div className="text-center text-gray-500 py-12">
                                    No logs available
                                </div>
                            ) : (
                                <div className="divide-y divide-gray-800/50">
                                    {data.logs.map((log, index) => (
                                        <div
                                            key={index}
                                            className="px-4 py-3 hover:bg-gray-800/30 transition-colors"
                                        >
                                            <div className="flex items-start gap-3">
                                                {getIcon(log.level)}
                                                <div className="flex-1 min-w-0">
                                                    <div className={`text-sm ${getTextColor(log.level)} break-words`}>
                                                        {log.message}
                                                    </div>
                                                    {log.timestamp && (
                                                        <div className="text-xs text-gray-600 mt-1 font-mono">
                                                            {log.timestamp}
                                                        </div>
                                                    )}
                                                </div>
                                                <span className={`text-xs px-2 py-0.5 rounded-full ${log.level === 'ERROR' ? 'bg-loss/20 text-loss' :
                                                        log.level === 'VETO' ? 'bg-amber-500/20 text-amber-400' :
                                                            log.level === 'SUCCESS' || log.level === 'TRADE' ? 'bg-profit/20 text-profit' :
                                                                log.level === 'SIGNAL' ? 'bg-blue-500/20 text-blue-400' :
                                                                    'bg-gray-700/50 text-gray-500'
                                                    }`}>
                                                    {log.level}
                                                </span>
                                            </div>
                                        </div>
                                    ))}
                                </div>
                            )}
                        </div>
                    </div>
                )}
            </div>
        </main>
    );
}
