'use client';

import React from 'react';
import { CheckCircle, XCircle, AlertCircle, Clock, Activity, BarChart2 } from 'lucide-react';

interface StageMetric {
    value: number;
    threshold: number | string;
    op: string; // operator like '>', '<'
}

interface Stage {
    name: string;
    status: 'PASS' | 'FAIL' | 'WAIT' | 'READY (LONG)' | 'READY (SHORT)' | 'NEUTRAL' | 'TRIGGER!' | 'PARTIAL';
    details: string;
    metrics?: Record<string, StageMetric>;
}

interface StrategyProgress {
    strategy: string;
    score: number;
    stages: Stage[];
    error?: string;
}

interface StrategyMonitorCardProps {
    data: StrategyProgress;
}

export default function StrategyMonitorCard({ data }: StrategyMonitorCardProps) {
    const isError = !!data.error;

    const getStatusColor = (status: string) => {
        switch (status) {
            case 'PASS': return 'text-green-500';
            case 'TRIGGER!': return 'text-green-400 animate-pulse';
            case 'READY (LONG)': return 'text-blue-400';
            case 'READY (SHORT)': return 'text-orange-400';
            case 'FAIL': return 'text-red-500';
            case 'PARTIAL': return 'text-yellow-400';
            default: return 'text-gray-500';
        }
    };

    const getStatusIcon = (status: string) => {
        switch (status) {
            case 'PASS':
            case 'TRIGGER!':
                return <CheckCircle className="w-5 h-5" />;
            case 'FAIL': return <XCircle className="w-5 h-5" />;
            case 'READY (LONG)':
            case 'READY (SHORT)':
            case 'PARTIAL':
                return <Activity className="w-5 h-5" />;
            default: return <Clock className="w-5 h-5" />;
        }
    };

    return (
        <div className="bg-[#111] border border-gray-800 rounded-xl p-5 shadow-lg relative overflow-hidden">
            {/* Header */}
            <div className="flex justify-between items-start mb-4">
                <div className="flex items-center gap-3">
                    <div className="p-2 bg-blue-500/10 rounded-lg">
                        <BarChart2 className="w-6 h-6 text-blue-400" />
                    </div>
                    <div>
                        <h3 className="font-bold text-lg text-gray-100">{data.strategy}</h3>
                        <div className="text-xs text-gray-500 flex items-center gap-2">
                            <span>Readiness Score:</span>
                            <span className={`font-mono font-bold ${data.score >= 80 ? 'text-green-400' : data.score >= 50 ? 'text-yellow-400' : 'text-gray-500'}`}>
                                {data.score}%
                            </span>
                        </div>
                    </div>
                </div>
                {!isError && (
                    <div className={`w-3 h-3 rounded-full ${data.score >= 80 ? 'bg-green-500 shadow-[0_0_10px_rgba(34,197,94,0.5)]' : 'bg-gray-700'}`}></div>
                )}
            </div>

            {/* Error State */}
            {isError ? (
                <div className="bg-red-900/20 border border-red-900/50 rounded-lg p-4 text-center">
                    <AlertCircle className="w-8 h-8 text-red-500 mx-auto mb-2" />
                    <p className="text-sm text-red-400">{data.error}</p>
                </div>
            ) : (
                /* Stages List */
                <div className="space-y-3">
                    {data.stages.map((stage, idx) => (
                        <div key={idx} className="bg-gray-900/30 border border-gray-800 rounded-lg p-3">
                            <div className="flex justify-between items-center mb-2">
                                <span className="text-sm font-semibold text-gray-300">{stage.name}</span>
                                <div className={`flex items-center gap-2 text-sm font-bold ${getStatusColor(stage.status)}`}>
                                    <span className="uppercase text-[10px] tracking-wider">{stage.status}</span>
                                    {getStatusIcon(stage.status)}
                                </div>
                            </div>

                            <div className="text-xs text-gray-500 mb-2 font-mono">
                                {stage.details}
                            </div>

                            {/* Metrics Breakdown (if available) */}
                            {stage.metrics && (
                                <div className="grid grid-cols-2 gap-2 mt-2 pt-2 border-t border-gray-800/50">
                                    {Object.entries(stage.metrics).map(([key, m]) => (
                                        <div key={key} className="flex justify-between bg-black/20 px-2 py-1 rounded text-[10px]">
                                            <span className="text-gray-500 uppercase">{key}</span>
                                            <span className="text-gray-300 font-mono">
                                                {m.value} <span className="text-gray-600">{m.op}</span> {m.threshold}
                                            </span>
                                        </div>
                                    ))}
                                </div>
                            )}
                        </div>
                    ))}
                </div>
            )}

            {/* Progress Bar Footer */}
            <div className="absolute bottom-0 left-0 w-full h-1 bg-gray-800">
                <div
                    className="h-full bg-gradient-to-r from-blue-600 to-purple-600 transition-all duration-500"
                    style={{ width: `${data.score}%` }}
                ></div>
            </div>
        </div>
    );
}
