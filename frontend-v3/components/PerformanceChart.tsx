'use client';

import { createChart, ColorType, IChartApi, AreaSeries, UTCTimestamp } from 'lightweight-charts';
import { useEffect, useRef, useState } from 'react';
import { api } from '@/lib/api';
import { cn } from '@/lib/utils';
import { TrendingUp, Calendar } from 'lucide-react';

const TIMEFRAMES = [
    { label: '24H', hours: 24 },
    { label: '7D', hours: 24 * 7 },
    { label: '30D', hours: 24 * 30 },
    { label: 'ALL', hours: 0 },
];

export default function PerformanceChart() {
    const chartContainerRef = useRef<HTMLDivElement>(null);
    const chartInstance = useRef<IChartApi | null>(null);
    const [rawData, setRawData] = useState<{ time: number; value: number }[]>([]);
    const [selectedTimeframe, setSelectedTimeframe] = useState('ALL');

    useEffect(() => {
        api.getEquityHistory().then(setRawData).catch(console.error);
    }, []);

    const filteredData = rawData.filter(d => {
        if (selectedTimeframe === 'ALL') return true;
        const timeframe = TIMEFRAMES.find(t => t.label === selectedTimeframe);
        if (!timeframe) return true;
        const cutoff = Date.now() / 1000 - timeframe.hours * 3600;
        return d.time >= cutoff;
    });

    useEffect(() => {
        if (!chartContainerRef.current) return;

        const handleResize = () => {
            if (chartInstance.current && chartContainerRef.current) {
                chartInstance.current.applyOptions({ width: chartContainerRef.current.clientWidth });
            }
        };

        if (!chartInstance.current) {
            chartInstance.current = createChart(chartContainerRef.current, {
                layout: {
                    background: { type: ColorType.Solid, color: 'transparent' },
                    textColor: '#9ca3af',
                    fontFamily: "'Inter', sans-serif",
                    fontSize: 11,
                },
                width: chartContainerRef.current.clientWidth,
                height: 240,
                grid: {
                    vertLines: { visible: false },
                    horzLines: { color: 'rgba(51, 65, 85, 0.3)', style: 3 },
                },
                rightPriceScale: {
                    borderColor: 'rgba(51, 65, 85, 0.3)',
                    scaleMargins: {
                        top: 0.2,
                        bottom: 0.1,
                    },
                },
                timeScale: {
                    borderColor: 'rgba(51, 65, 85, 0.3)',
                    timeVisible: true,
                    secondsVisible: false,
                    fixLeftEdge: true,
                    rightOffset: 5,
                },
                crosshair: {
                    vertLine: {
                        color: 'rgba(59, 130, 246, 0.5)',
                        width: 1,
                        style: 3,
                        labelBackgroundColor: '#1e3a8a',
                    },
                    horzLine: {
                        color: 'rgba(59, 130, 246, 0.5)',
                        width: 1,
                        style: 3,
                        labelBackgroundColor: '#1e3a8a',
                    },
                },
                handleScale: {
                    axisPressedMouseMove: false,
                },
                handleScroll: {
                    mouseWheel: false,
                    pressedMouseMove: false,
                }
            });

            const areaSeries = chartInstance.current.addSeries(AreaSeries, {
                lineColor: '#22c55e',
                topColor: '#2962FF',
                bottomColor: 'rgba(41, 98, 255, 0.28)',
                lineWidth: 2,
            });

            (chartInstance.current as any).areaSeries = areaSeries;
        }

        const areaSeries = (chartInstance.current as any).areaSeries;

        // Dynamic coloring logic based on filtered data only
        const finalValue = filteredData.length > 0 ? filteredData[filteredData.length - 1].value : 0;
        const initialValue = filteredData.length > 0 ? filteredData[0].value : 0;
        const isPositive = finalValue >= initialValue;

        const color = isPositive ? '#10b981' : '#ef4444'; // Emerald-500 or Red-500
        const topColor = isPositive ? 'rgba(16, 185, 129, 0.5)' : 'rgba(239, 68, 68, 0.5)';
        const bottomColor = isPositive ? 'rgba(16, 185, 129, 0.05)' : 'rgba(239, 68, 68, 0.05)';

        areaSeries.applyOptions({
            lineColor: color,
            topColor: topColor,
            bottomColor: bottomColor,
        });

        // Ensure distinct timestamps
        const distinctData = filteredData.filter((v, i, a) => i === 0 || v.time > a[i - 1].time);

        areaSeries.setData(distinctData as any);
        chartInstance.current.timeScale().fitContent();

        window.addEventListener('resize', handleResize);

        return () => {
            window.removeEventListener('resize', handleResize);
            // Don't dispose chart here to preserve instance, or dispose if full unmount
        };
    }, [filteredData]); // Re-run when filteredData changes

    return (
        <div className="bg-neutral-950 border border-neutral-800 rounded-2xl p-6 mt-6 shadow-xl overflow-hidden">
            <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between mb-6 gap-4">
                <div className="flex items-center gap-3">
                    <div className="p-2 bg-emerald-500/10 rounded-lg">
                        <TrendingUp className="w-5 h-5 text-emerald-400" />
                    </div>
                    <div>
                        <h3 className="text-lg font-bold text-neutral-100">
                            Performance
                        </h3>
                        <div className="text-xs text-neutral-500">
                            Equity Curve & Profitability
                        </div>
                    </div>
                </div>

                {/* Timeframe Selector */}
                <div className="flex items-center gap-1 p-1 bg-neutral-900 rounded-lg border border-neutral-800">
                    {TIMEFRAMES.map((tf) => (
                        <button
                            key={tf.label}
                            onClick={() => setSelectedTimeframe(tf.label)}
                            className={cn(
                                "text-[10px] font-medium px-3 py-1.5 rounded-md transition-all",
                                selectedTimeframe === tf.label
                                    ? "bg-neutral-800 text-white shadow-sm ring-1 ring-white/10"
                                    : "text-neutral-500 hover:text-neutral-300 hover:bg-neutral-800/50"
                            )}
                        >
                            {tf.label}
                        </button>
                    ))}
                </div>
            </div>

            <div className="relative">
                {filteredData.length === 0 ? (
                    <div className="h-[240px] flex flex-col items-center justify-center text-neutral-500 gap-3 bg-neutral-900/20 rounded-xl border border-dashed border-neutral-800">
                        <Calendar className="w-8 h-8 opacity-20" />
                        <span className="text-sm font-medium">No data in this timeframe</span>
                    </div>
                ) : (
                    <div ref={chartContainerRef} className="w-full h-[240px]" />
                )}
            </div>

            <div className="mt-4 grid grid-cols-3 gap-4 border-t border-neutral-900/50 pt-4">
                <div className="text-center">
                    <div className="text-[10px] text-neutral-500 uppercase tracking-wider mb-1">Total PnL</div>
                    <div className={cn("text-sm font-mono font-bold", filteredData.length > 0 && (filteredData[filteredData.length - 1].value - filteredData[0].value) >= 0 ? "text-emerald-400" : "text-red-400")}>
                        {filteredData.length > 0 ? (
                            <>
                                {(filteredData[filteredData.length - 1].value - filteredData[0].value) >= 0 ? '+' : ''}
                                ${(filteredData[filteredData.length - 1].value - filteredData[0].value).toFixed(2)}
                            </>
                        ) : '---'}
                    </div>
                </div>
                <div className="text-center border-l border-neutral-800">
                    <div className="text-[10px] text-neutral-500 uppercase tracking-wider mb-1">Trades</div>
                    <div className="text-sm font-mono font-bold text-neutral-300">
                        {filteredData.length}
                    </div>
                </div>
                <div className="text-center border-l border-neutral-800">
                    <div className="text-[10px] text-neutral-500 uppercase tracking-wider mb-1">Period</div>
                    <div className="text-sm font-mono font-bold text-neutral-300">
                        {selectedTimeframe}
                    </div>
                </div>
            </div>
        </div>
    );
}
