'use client';

import React from 'react';
import useSWR from 'swr';
import { Brain, AlertTriangle, TrendingUp, CheckCircle, XCircle, Activity } from 'lucide-react';

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

export default function CopilotCard() {
    const { data, error } = useSWR<LogsResponse>(
        `${API_BASE_URL}/api/logs?limit=10`,
        fetcher,
        { refreshInterval: 5000 } // Refresh every 5 seconds
    );

    // Find the most recent significant log entry
    const getLatestSignificantLog = (): LogEntry | null => {
        if (!data?.logs) return null;

        // Priority: VETO > TRADE > SIGNAL > ERROR
        const priorities = ['VETO', 'TRADE', 'SIGNAL', 'ERROR', 'SUCCESS'];

        for (const priority of priorities) {
            const log = data.logs.find(l => l.level === priority);
            if (log) return log;
        }

        // Fallback to latest log
        return data.logs[0] || null;
    };

    const latestLog = getLatestSignificantLog();

    // Get icon based on log level
    const getIcon = (level: string) => {
        switch (level) {
            case 'VETO':
                return <XCircle className="w-5 h-5 text-amber-500" />;
            case 'ERROR':
                return <AlertTriangle className="w-5 h-5 text-loss" />;
            case 'TRADE':
                return <TrendingUp className="w-5 h-5 text-profit" />;
            case 'SIGNAL':
                return <Activity className="w-5 h-5 text-blue-400" />;
            case 'SUCCESS':
                return <CheckCircle className="w-5 h-5 text-profit" />;
            default:
                return <Brain className="w-5 h-5 text-gray-400" />;
        }
    };

    // Get human-readable summary
    const getSummary = (log: LogEntry): string => {
        const message = log.message;

        // Truncate long messages
        if (message.length > 80) {
            return message.substring(0, 77) + '...';
        }
        return message;
    };

    // Get accent color based on level
    const getAccentColor = (level: string): string => {
        switch (level) {
            case 'VETO':
                return 'border-amber-500/30';
            case 'ERROR':
                return 'border-loss/30';
            case 'TRADE':
            case 'SUCCESS':
                return 'border-profit/30';
            case 'SIGNAL':
                return 'border-blue-400/30';
            default:
                return 'border-gray-600/30';
        }
    };

    if (error || !data) {
        return null; // Don't show if no data
    }

    if (!latestLog) {
        return (
            <div className={`bg-gray-900/50 border border-gray-700/50 rounded-lg p-4`}>
                <div className="flex items-center gap-3">
                    <Brain className="w-5 h-5 text-gray-500" />
                    <div className="flex-1">
                        <div className="text-xs text-gray-500 uppercase tracking-wider mb-1">Co-pilot</div>
                        <div className="text-gray-400 text-sm">Waiting for activity...</div>
                    </div>
                </div>
            </div>
        );
    }

    return (
        <div className={`bg-gray-900/50 border ${getAccentColor(latestLog.level)} rounded-lg p-4`}>
            <div className="flex items-start gap-3">
                {getIcon(latestLog.level)}
                <div className="flex-1 min-w-0">
                    <div className="text-xs text-gray-500 uppercase tracking-wider mb-1">Co-pilot</div>
                    <div className="text-gray-200 text-sm leading-relaxed">
                        {getSummary(latestLog)}
                    </div>
                    {latestLog.timestamp && (
                        <div className="text-xs text-gray-600 mt-2">
                            {latestLog.timestamp}
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
}
