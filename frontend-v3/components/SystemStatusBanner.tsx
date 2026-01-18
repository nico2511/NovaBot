'use client';

import React from 'react';
import { useBotStatus } from '../hooks/useBotStatus';
import { AlertTriangle, WifiOff, Octagon } from 'lucide-react';
import { cn } from '@/lib/utils';

export default function SystemStatusBanner() {
    const { data, error, isLoading, isStopped } = useBotStatus();

    // 1. Connection Error State (Highest Priority)
    if (error) {
        return (
            <>
                <div className="fixed top-0 left-0 right-0 h-1 bg-loss z-[60] animate-pulse" />
                <div className="fixed top-0 left-0 right-0 bg-loss text-white px-4 py-3 text-center z-50 shadow-lg flex items-center justify-center gap-2">
                    <WifiOff className="w-5 h-5" />
                    <span className="font-bold tracking-wider">CONNECTION LOST</span>
                    <span className="text-sm opacity-90 hidden md:inline">- Unable to reach bot API</span>
                </div>
            </>
        );
    }

    // 2. Stopped State (High Priority)
    if (isStopped && !isLoading) {
        return (
            <>
                {/* Red Pulse Line */}
                <div className="fixed top-0 left-0 right-0 h-1 bg-loss z-[60]" />

                {/* Persistent Banner */}
                <div className="fixed bottom-0 left-0 right-0 bg-loss/10 border-t border-loss/30 backdrop-blur-md px-4 py-2 z-50 flex items-center justify-center gap-3 md:justify-between text-loss">
                    <div className="flex items-center gap-2">
                        <Octagon className="w-5 h-5 animate-pulse" />
                        <span className="font-bold tracking-widest text-sm md:text-base">SYSTEM STOPPED</span>
                    </div>
                    <span className="text-xs md:text-sm hidden md:inline opacity-80 font-mono">
                        TRADING DISABLED • POSITIONS MONITORED ONLY
                    </span>
                </div>
            </>
        );
    }

    // 3. Running State (Normal)
    if (data?.is_running) {
        return (
            <div className="fixed top-0 left-0 right-0 h-0.5 bg-profit/50 z-[60] shadow-[0_0_10px_rgba(34,197,94,0.5)]" />
        );
    }

    return null;
}
