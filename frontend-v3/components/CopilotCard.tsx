'use client';

import React from 'react';
import useSWR from 'swr';
import { Brain, AlertTriangle, TrendingUp, CheckCircle, XCircle, Activity } from 'lucide-react';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8001';

interface LogEntry {
    timestamp: string;
    level: string;
    message: string;
    metadata?: Record<string, any> | null;
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
                return 'border-amber-500/50';
            case 'ERROR':
                return 'border-loss/50';
            case 'TRADE':
            case 'SUCCESS':
                return 'border-profit/50';
            case 'SIGNAL':
                return 'border-blue-400/50';
            default:
                return 'border-gray-600/50';
        }
    };

    const renderMetadata = (metadata: Record<string, any>) => {
        const entryIndicators = metadata.entry_indicators || metadata;

        const badges = [];

        if (entryIndicators.rsi) {
            badges.push({
                label: 'RSI',
                value: Number(entryIndicators.rsi).toFixed(1),
                color: entryIndicators.rsi > 70 ? 'text-loss' : entryIndicators.rsi < 30 ? 'text-profit' : 'text-blue-400'
            });
        }

        if (entryIndicators.adx) {
            badges.push({
                label: 'ADX',
                value: Number(entryIndicators.adx).toFixed(1),
                color: entryIndicators.adx > 25 ? 'text-profit' : 'text-gray-400'
            });
        }

        if (entryIndicators.regime) {
            badges.push({
                label: 'Regime',
                value: entryIndicators.regime,
                color: 'text-neutral-300'
            });
        }

        if (entryIndicators.volume_ratio) {
            badges.push({
                label: 'Vol',
                value: `${Number(entryIndicators.volume_ratio).toFixed(0)}%`,
                color: entryIndicators.volume_ratio > 120 ? 'text-profit' : 'text-neutral-400'
            });
        }

        if (metadata.reason && typeof metadata.reason === 'string') {
            // Add reason as a full-width alert or badge if needed
        }

        if (badges.length === 0) return null;

        return (
            <div className="flex flex-wrap gap-2 mt-3 pt-3 border-t border-white/5">
                {badges.map((b, i) => (
                    <div key={i} className="flex items-center gap-1.5 bg-white/5 px-2 py-0.5 rounded border border-white/5">
                        <span className="text-[9px] uppercase tracking-tighter text-neutral-500 font-bold">{b.label}</span>
                        <span className={`text-[10px] font-mono font-bold ${b.color}`}>{b.value}</span>
                    </div>
                ))}
            </div>
        );
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
        <div className={`bg-[#111] border ${getAccentColor(latestLog.level)} rounded-lg p-4 transition-all duration-500`}>
            <div className="flex items-start gap-3">
                <div className="mt-1">
                    {getIcon(latestLog.level)}
                </div>
                <div className="flex-1 min-w-0">
                    <div className="flex items-center justify-between mb-1">
                        <div className="text-xs text-gray-500 uppercase tracking-wider">Co-pilot AI</div>
                        {latestLog.timestamp && (
                            <div className="text-[10px] text-gray-600">
                                {latestLog.timestamp}
                            </div>
                        )}
                    </div>
                    <div className="text-gray-200 text-sm leading-relaxed font-medium">
                        {getSummary(latestLog)}
                    </div>
                    {latestLog.metadata && renderMetadata(latestLog.metadata)}
                </div>
            </div>
        </div>
    );
}
