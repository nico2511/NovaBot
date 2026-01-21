"use client"

import React, { useEffect, useRef, useState } from 'react';
import { createChart, ColorType, IChartApi, ISeriesApi, UTCTimestamp } from 'lightweight-charts';
import useSWR from 'swr';
// Replaced missing UI components with standard HTML/Tailwind
// import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
// import { Badge } from "@/components/ui/badge";
import { Loader2, RefreshCcw } from "lucide-react";

interface CandleData {
    time: number;
    open: number;
    high: number;
    low: number;
    close: number;
    volume: number;
}

interface PriceChartProps {
    symbol: string;
    interval?: string;
    height?: number;
}

const fetcher = (url: string) => fetch(url).then((res) => res.json());

export function PriceChart({ symbol, interval = "15m", height = 400 }: PriceChartProps) {
    const chartContainerRef = useRef<HTMLDivElement>(null);
    const chartRef = useRef<IChartApi | null>(null);
    const candlestickSeriesRef = useRef<ISeriesApi<"Candlestick"> | null>(null);
    const volumeSeriesRef = useRef<ISeriesApi<"Histogram"> | null>(null);

    // Data Fetching
    const { data: candles, error, mutate } = useSWR<CandleData[]>(
        `http://localhost:8001/api/market/candles?symbol=${symbol}&interval=${interval}&limit=200`,
        fetcher,
        { refreshInterval: 10000 } // Poll every 10s
    );

    const isLoading = !candles && !error;

    // Initialize Chart
    useEffect(() => {
        if (!chartContainerRef.current) return;

        import('lightweight-charts').then(({ createChart, ColorType, CandlestickSeries, HistogramSeries }) => {
            const chart = createChart(chartContainerRef.current!, {
                layout: {
                    background: { type: ColorType.Solid, color: '#09090b' }, // Zinc 950
                    textColor: '#a1a1aa',
                },
                grid: {
                    vertLines: { color: '#27272a' },
                    horzLines: { color: '#27272a' },
                },
                width: chartContainerRef.current!.clientWidth,
                height: height,
                timeScale: {
                    timeVisible: true,
                    secondsVisible: false,
                    borderColor: '#27272a',
                },
                rightPriceScale: {
                    borderColor: '#27272a',
                },
            });

            // Add Candlestick Series (v5 API)
            const candlestickSeries = chart.addSeries(CandlestickSeries, {
                upColor: '#22c55e', // Green 500
                downColor: '#ef4444', // Red 500
                borderVisible: false,
                wickUpColor: '#22c55e',
                wickDownColor: '#ef4444',
            });

            // Add Volume Series (v5 API)
            const volumeSeries = chart.addSeries(HistogramSeries, {
                color: '#3f3f46', // Zinc 700 - Default
                priceFormat: {
                    type: 'volume',
                },
                priceScaleId: '', // Overlay on same scale but separate
            });

            // Settings for Volume to sit at bottom
            volumeSeries.priceScale().applyOptions({
                scaleMargins: {
                    top: 0.8, // Highest volume bar takes up bottom 20%
                    bottom: 0,
                },
            });

            chartRef.current = chart;
            candlestickSeriesRef.current = candlestickSeries;
            volumeSeriesRef.current = volumeSeries;

            // Resize Observer
            const handleResize = () => {
                if (chartContainerRef.current) {
                    chart.applyOptions({ width: chartContainerRef.current.clientWidth });
                }
            };

            window.addEventListener('resize', handleResize);
        });

        return () => {
            // Cleanup logic (if needed, chart.remove() handles most)
            if (chartRef.current) {
                chartRef.current.remove();
                chartRef.current = null;
            }
        };
    }, [height]);

    // Update Data
    useEffect(() => {
        if (candles && candlestickSeriesRef.current && volumeSeriesRef.current) {
            const formattedCandles = candles.map(c => ({
                time: c.time as UTCTimestamp,
                open: c.open,
                high: c.high,
                low: c.low,
                close: c.close
            })).sort((a, b) => (a.time as number) - (b.time as number));

            const formattedVolume = candles.map(c => ({
                time: c.time as UTCTimestamp,
                value: c.volume,
                color: c.close >= c.open ? '#22c55e80' : '#ef444480' // Green/Red with opacity
            })).sort((a, b) => (a.time as number) - (b.time as number));

            candlestickSeriesRef.current.setData(formattedCandles);
            volumeSeriesRef.current.setData(formattedVolume);

            // Fit Content only on first load ideally, or stick to right?
            // chartRef.current?.timeScale().fitContent();
        }
    }, [candles]);

    return (
        <div className="w-full bg-zinc-900/50 border border-zinc-800 rounded-xl shadow-xl overflow-hidden">
            <div className="py-3 px-4 border-b border-zinc-800 flex flex-row items-center justify-between bg-zinc-900/80">
                <div className="flex items-center gap-2">
                    <h3 className="text-zinc-100 text-sm font-medium flex items-center gap-2">
                        {symbol} PRICE ACTION
                        {isLoading && <Loader2 className="h-3 w-3 animate-spin text-zinc-500" />}
                    </h3>
                    <span className="inline-flex items-center rounded-md border border-zinc-700 px-2 py-0.5 text-xs font-semibold transition-colors focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 text-zinc-400 font-mono h-5">
                        {interval}
                    </span>
                </div>

                <button
                    onClick={() => mutate()}
                    className="text-zinc-500 hover:text-zinc-300 transition-colors"
                    title="Refresh Chart"
                >
                    <RefreshCcw size={14} className={isLoading ? "animate-spin" : ""} />
                </button>
            </div>
            <div className="p-0 relative bg-[#09090b]">
                <div ref={chartContainerRef} className="w-full" style={{ height: height }} />

                {(!candles || candles.length === 0) && !isLoading && (
                    <div className="absolute inset-0 flex items-center justify-center text-zinc-500 text-sm bg-zinc-900/20 backdrop-blur-sm pointer-events-none">
                        No market data available
                    </div>
                )}
            </div>
        </div>
    );
}
