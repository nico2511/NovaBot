import { TrendingUp, TrendingDown, Clock, Activity, DollarSign, RefreshCw, Shield } from 'lucide-react';
import { api } from '@/lib/api';
import { useState } from 'react';
import { mutate } from 'swr';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8001';

interface ActivePositionProps {
    symbol?: string;
    side?: 'LONG' | 'SHORT';
    size?: number;
    entryPrice?: number;
    currentPrice?: number;
    leverage?: number;
    pnl?: number;
    pnlPercent?: number;
    duration?: string;
    isMock?: boolean;
}

export default function ActivePosition({
    symbol = 'SUI-PERP',
    side = 'LONG',
    size = 1500,
    entryPrice = 1.42,
    currentPrice = 1.45,
    leverage = 5,
    pnl = 45.00,
    pnlPercent = 12.5,
    duration = '1h 30m',
    isMock = false
}: ActivePositionProps) {
    const [isSyncing, setIsSyncing] = useState(false);
    const [isBeProcesing, setIsBeProcessing] = useState(false);
    const [isClosing, setIsClosing] = useState(false);
    const [isRecalibrating, setIsRecalibrating] = useState(false);

    const isProfit = pnl >= 0;

    // Calculate Progress Bar Width
    // Range: -20% to +20% (Adjustable)
    const MAX_RANGE = 20;
    const clampedPercent = Math.max(-MAX_RANGE, Math.min(MAX_RANGE, pnlPercent));
    const absPercent = Math.abs(clampedPercent);
    const barWidth = (absPercent / MAX_RANGE) * 50; // 0 to 50%

    const handleForceSync = async () => {
        if (isMock) return;
        setIsSyncing(true);
        try {
            await api.forceSync();
            mutate(`${API_BASE_URL}/api/status`); // Refresh dashboard
        } catch (e) {
            console.error(e);
        } finally {
            setTimeout(() => setIsSyncing(false), 1000);
        }
    };

    const handleForceBE = async () => {
        if (isMock) return;
        setIsBeProcessing(true);
        try {
            await api.forceBreakEven(symbol);
            mutate(`${API_BASE_URL}/api/status`);
        } catch (e) {
            console.error(e);
        } finally {
            setIsBeProcessing(false);
        }
    };

    const handleClose = async () => {
        if (isMock) return;
        if (!window.confirm('Are you sure you want to CLOSE this position at market price?')) return;

        setIsClosing(true);
        try {
            await api.closeTrade(symbol);
            mutate(`${API_BASE_URL}/api/status`);
        } catch (e) {
            console.error(e);
            alert('Failed to close position');
        } finally {
            setIsClosing(false);
        }
    };

    const handleRecalibrate = async () => {
        if (isMock) return;
        setIsRecalibrating(true);
        try {
            await api.recalibrateStops(symbol);
            mutate(`${API_BASE_URL}/api/status`);
        } catch (e) {
            console.error(e);
        } finally {
            setIsRecalibrating(false);
        }
    };

    return (
        <div className={`bg-neutral-900 border ${isProfit ? 'border-green-900/50' : 'border-red-900/50'} rounded-lg p-4 relative overflow-hidden transition-all duration-300`}>
            {/* Background Pulse Effect */}
            <div className={`absolute top-0 right-0 w-32 h-32 blur-[80px] rounded-full opacity-10 transition-colors duration-500 ${isProfit ? 'bg-green-500' : 'bg-red-500'}`} />

            {/* Header */}
            <div className="flex justify-between items-start mb-4 relative z-10">
                <div>
                    <div className="flex items-baseline gap-2">
                        <h3 className="text-xl font-bold text-white">{symbol}</h3>
                        <span className={`text-xs font-bold px-1.5 py-0.5 rounded ${side === 'LONG' ? 'bg-green-500/20 text-green-400' : 'bg-red-500/20 text-red-400'
                            }`}>
                            {side} {leverage}x
                        </span>
                    </div>
                    {isMock && <span className="text-[10px] text-gray-500 uppercase tracking-wider">Mock Position</span>}
                </div>
                <div className="text-right">
                    <div className={`text-2xl font-mono font-bold ${isProfit ? 'text-green-400' : 'text-red-400'}`}>
                        {isProfit ? '+' : ''}{pnl.toFixed(2)}$
                    </div>
                    <div className={`text-xs ${isProfit ? 'text-green-500' : 'text-red-500'}`}>
                        {isProfit ? '+' : ''}{pnlPercent.toFixed(2)}%
                    </div>
                </div>
            </div>

            {/* PnL Progress Bar (Centered at 0) */}
            <div className="relative h-1.5 bg-neutral-800 rounded-full mb-4 w-full overflow-hidden">
                {/* Center Marker */}
                <div className="absolute left-1/2 top-0 bottom-0 w-[1px] bg-neutral-600 z-10"></div>

                {/* Bar */}
                <div
                    className={`absolute top-0 bottom-0 transition-all duration-500 ease-out ${isProfit ? 'bg-green-500 left-1/2 rounded-r-full' : 'bg-red-500 right-1/2 rounded-l-full'}`}
                    style={{
                        width: `${barWidth}%`,
                        left: isProfit ? '50%' : undefined,
                        right: !isProfit ? '50%' : undefined
                    }}
                />
            </div>

            {/* Grid Stats */}
            <div className="grid grid-cols-2 gap-3 text-sm relative z-10 mb-4">
                <div className="bg-neutral-800/50 p-2 rounded border border-neutral-700/30">
                    <div className="text-gray-500 text-[10px] uppercase mb-1">Entry Price</div>
                    <div className="font-mono text-sm">{entryPrice.toFixed(4)}</div>
                </div>
                <div className="bg-neutral-800/50 p-2 rounded border border-neutral-700/30">
                    <div className="text-gray-500 text-[10px] uppercase mb-1">Mark Price</div>
                    <div className="font-mono text-white text-sm">{currentPrice.toFixed(4)}</div>
                </div>
                <div className="bg-neutral-800/50 p-2 rounded border border-neutral-700/30">
                    <div className="text-gray-500 text-[10px] uppercase mb-1">Size</div>
                    <div className="font-mono text-sm">{size.toLocaleString()} <span className="text-[10px] text-gray-500">USD</span></div>
                </div>
                <div className="bg-neutral-800/50 p-2 rounded border border-neutral-700/30">
                    <div className="text-gray-500 text-[10px] uppercase mb-1">Duration</div>
                    <div className="flex items-center gap-1 font-mono text-gray-300 text-sm">
                        <Clock className="w-3 h-3" /> {duration}
                    </div>
                </div>
            </div>

            {/* Action Buttons */}
            <div className="space-y-2 relative z-10">
                {/* Main Close Action */}
                <button
                    onClick={handleClose}
                    disabled={isClosing}
                    className="w-full bg-red-500/10 hover:bg-red-500/20 text-red-400 border border-red-500/20 py-2 rounded text-xs font-bold transition-colors uppercase tracking-wide disabled:opacity-50"
                >
                    {isClosing ? 'CLOSING...' : 'CLOSE MARKET'}
                </button>

                {/* Secondary Actions Grid */}
                <div className="grid grid-cols-3 gap-2">
                    <button
                        onClick={handleRecalibrate}
                        disabled={isRecalibrating}
                        className="bg-neutral-800 hover:bg-neutral-700 text-gray-300 border border-neutral-700 py-1.5 rounded text-xs font-bold transition-colors disabled:opacity-50"
                        title="Auto-Recalibrate Take Profit & Stop Loss"
                    >
                        {isRecalibrating ? '...' : 'TP/SL'}
                    </button>

                    <button
                        onClick={handleForceSync}
                        disabled={isSyncing}
                        className="flex items-center justify-center gap-1.5 bg-neutral-800 hover:bg-neutral-700 text-gray-400 border border-neutral-700 py-1.5 rounded text-xs transition-colors disabled:opacity-50"
                        title="Force synchronization with exchange"
                    >
                        <RefreshCw className={`w-3 h-3 ${isSyncing ? 'animate-spin' : ''}`} /> Sync
                    </button>

                    <button
                        onClick={handleForceBE}
                        disabled={isBeProcesing}
                        className="flex items-center justify-center gap-1.5 bg-neutral-800 hover:bg-neutral-700 text-blue-400 border border-neutral-700 py-1.5 rounded text-xs transition-colors disabled:opacity-50"
                        title="Move Stop Loss to Break Even"
                    >
                        <Shield className="w-3 h-3" /> BE
                    </button>
                </div>
            </div>
        </div>
    );
}
