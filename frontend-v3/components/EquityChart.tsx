'use client';

import { createChart, ColorType, IChartApi, AreaSeries } from 'lightweight-charts';
import { useEffect, useRef, useState } from 'react';
import { api } from '@/lib/api';

export default function EquityChart() {
    const chartContainerRef = useRef<HTMLDivElement>(null);
    const chartInstance = useRef<IChartApi | null>(null);
    const [data, setData] = useState<{ time: number; value: number }[]>([]);

    useEffect(() => {
        api.getEquityHistory().then(setData).catch(console.error);
    }, []);

    useEffect(() => {
        if (!chartContainerRef.current || data.length === 0) return;

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
                },
                width: chartContainerRef.current.clientWidth,
                height: 200,
                grid: {
                    vertLines: { visible: false },
                    horzLines: { color: '#333' },
                },
                rightPriceScale: {
                    borderColor: '#333',
                },
                timeScale: {
                    borderColor: '#333',
                    timeVisible: true,
                    secondsVisible: false,
                },
            });

            const areaSeries = chartInstance.current.addSeries(AreaSeries, {
                lineColor: '#22c55e',
                topColor: '#2962FF',
                bottomColor: 'rgba(41, 98, 255, 0.28)',
            });

            // Color based on overall PnL trend?
            const isPositive = data[data.length - 1].value >= 0;
            areaSeries.applyOptions({
                lineColor: isPositive ? '#22c55e' : '#ef4444',
                topColor: isPositive ? 'rgba(34, 197, 94, 0.56)' : 'rgba(239, 68, 68, 0.56)',
                bottomColor: isPositive ? 'rgba(34, 197, 94, 0.04)' : 'rgba(239, 68, 68, 0.04)',
            });

            areaSeries.setData(data as any);
            chartInstance.current.timeScale().fitContent();
        }

        window.addEventListener('resize', handleResize);

        return () => {
            window.removeEventListener('resize', handleResize);
            if (chartInstance.current) {
                chartInstance.current.remove();
                chartInstance.current = null;
            }
        };
    }, [data]);

    // if (data.length === 0) return null;

    return (
        <div className="bg-[#111] border border-[#333] rounded-2xl p-6 mt-6">
            <h3 className="text-lg font-bold text-gray-200 mb-4 flex items-center gap-2">
                📈 Performance (Equity Curve)
            </h3>
            {data.length === 0 ? (
                <div className="text-gray-500 text-sm">No data available yet. Close a trade to see history.</div>
            ) : (
                <div ref={chartContainerRef} className="w-full h-[200px]" />
            )}
        </div>
    );
}
