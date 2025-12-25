'use client'
import { useEffect, useRef, useState } from 'react'
import { createChart, ColorType, IChartApi, ISeriesApi, Time, CandlestickSeries } from 'lightweight-charts'
import useSWR from 'swr'

interface ChartProps {
    symbol: string
}

const fetcher = (url: string) => fetch(url).then(res => res.json())

export default function Chart({ symbol }: ChartProps) {
    const chartContainerRef = useRef<HTMLDivElement>(null)
    const chartRef = useRef<IChartApi | null>(null)
    const seriesRef = useRef<ISeriesApi<"Candlestick"> | null>(null)

    // Fetch candles
    const { data: candleData } = useSWR(
        `/api/candles?limit=200`,
        fetcher,
        { refreshInterval: 15000 } // Refresh every 15s (15m candles don't change fast)
    )

    useEffect(() => {
        if (!chartContainerRef.current) return

        // Create chart
        const chart = createChart(chartContainerRef.current, {
            layout: {
                background: { type: ColorType.Solid, color: 'transparent' },
                textColor: '#9CA3AF',
            },
            grid: {
                vertLines: { color: 'rgba(42, 46, 57, 0.2)' },
                horzLines: { color: 'rgba(42, 46, 57, 0.2)' },
            },
            width: chartContainerRef.current.clientWidth,
            height: 400,
            timeScale: {
                timeVisible: true,
                secondsVisible: false,
            },
        })

        // Add candlestick series
        try {
            // V5 syntax check
            if (chart.addSeries) {
                // @ts-ignore - TS might complain if types mismatch versions but runtime works
                const series = chart.addSeries(CandlestickSeries, {
                    upColor: '#22c55e',
                    downColor: '#ef4444',
                    borderVisible: false,
                    wickUpColor: '#22c55e',
                    wickDownColor: '#ef4444',
                });
                seriesRef.current = series;
            } else {
                // V4 fallback
                // @ts-ignore
                const series = chart.addCandlestickSeries({
                    upColor: '#22c55e',
                    downColor: '#ef4444',
                    borderVisible: false,
                    wickUpColor: '#22c55e',
                    wickDownColor: '#ef4444',
                });
                seriesRef.current = series;
            }
        } catch (e) {
            console.error("Failed to add series:", e);
        }

        chartRef.current = chart

        // Resize handler
        const handleResize = () => {
            if (chartContainerRef.current) {
                chart.applyOptions({ width: chartContainerRef.current.clientWidth })
            }
        }

        window.addEventListener('resize', handleResize)

        return () => {
            window.removeEventListener('resize', handleResize)
            chart.remove()
        }
    }, [])

    // Update data when available
    useEffect(() => {
        if (seriesRef.current && candleData?.candles && candleData.candles.length > 0) {
            // Sort by time just in case
            const sortedCandles = [...candleData.candles].sort((a: any, b: any) => a.time - b.time)

            // Limit to unique times to avoid errors
            const uniqueCandles = sortedCandles.filter((v, i, a) =>
                i === a.findIndex((t: any) => t.time === v.time)
            )

            seriesRef.current.setData(uniqueCandles)

            // Fit content if it's the first load
            try {
                chartRef.current?.timeScale().fitContent()
            } catch (e) {
                console.error("Fit content error:", e)
            }
        }
    }, [candleData])

    return (
        <div className="w-full relative bg-background/50 backdrop-blur border border-border/30 rounded-2xl overflow-hidden p-4">
            <div className="absolute top-6 left-6 z-10 flex gap-2">
                <div className="bg-surface/80 backdrop-blur px-3 py-1 rounded text-sm border border-border/50 shadow-sm">
                    <span className="font-bold text-white">{symbol}</span>
                    <span className="ml-2 text-gray-400">15m</span>
                </div>
            </div>
            <div ref={chartContainerRef} className="w-full h-[400px]" />
        </div>
    )
}
