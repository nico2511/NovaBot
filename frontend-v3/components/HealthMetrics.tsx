'use client';

import { Activity, TrendingUp, AlertOctagon } from 'lucide-react';

interface HealthMetricsProps {
    marginUsage: number;
    winRate: number;
    maxDrawdown: number;
}

export default function HealthMetrics({ marginUsage, winRate, maxDrawdown }: HealthMetricsProps) {

    // Determine color for Margin Usage
    const getMarginColor = (val: number) => {
        if (val < 20) return 'text-profit';
        if (val < 50) return 'text-yellow-500';
        return 'text-loss';
    };

    // Determine color for Win Rate
    const getWinRateColor = (val: number) => {
        if (val >= 60) return 'text-profit';
        if (val >= 45) return 'text-yellow-500';
        return 'text-loss';
    };

    return (
        <div className="grid grid-cols-3 gap-4 mt-6">
            {/* Margin Usage */}
            <div className="bg-[#111] border border-gray-800 rounded-lg p-3 flex flex-col items-center">
                <div className="flex items-center gap-1 text-gray-400 text-xs mb-1 uppercase tracking-wider">
                    <Activity className="w-3 h-3" /> Margin
                </div>
                <div className={`text-xl font-bold ${getMarginColor(marginUsage)}`}>
                    {marginUsage.toFixed(1)}%
                </div>
            </div>

            {/* Win Rate */}
            <div className="bg-[#111] border border-gray-800 rounded-lg p-3 flex flex-col items-center">
                <div className="flex items-center gap-1 text-gray-400 text-xs mb-1 uppercase tracking-wider">
                    <TrendingUp className="w-3 h-3" /> Winrate
                </div>
                <div className={`text-xl font-bold ${getWinRateColor(winRate)}`}>
                    {winRate.toFixed(0)}%
                </div>
                {/* <div className="text-[10px] text-gray-600">Last 20 trades</div> */}
            </div>

            {/* Max Drawdown */}
            <div className="bg-[#111] border border-gray-800 rounded-lg p-3 flex flex-col items-center">
                <div className="flex items-center gap-1 text-gray-400 text-xs mb-1 uppercase tracking-wider">
                    <AlertOctagon className="w-3 h-3" /> DD
                </div>
                <div className="text-xl font-bold text-loss">
                    -{maxDrawdown.toFixed(1)}%
                </div>
            </div>
        </div>
    );
}
