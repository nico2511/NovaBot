'use client'
import { useEffect, useRef, useState } from 'react'
import { createChart, ColorType, IChartApi, ISeriesApi, Time, CandlestickSeries, LineSeries } from 'lightweight-charts'
import useSWR from 'swr'

interface ChartProps {
    symbol: string
    strategy?: string
}

const fetcher = (url: string) => fetch(url).then(res => res.json())

export default function Chart({ symbol, strategy }: ChartProps) {
    const chartContainerRef = useRef<HTMLDivElement>(null)
    const chartRef = useRef<IChartApi | null>(null)
    const seriesRef = useRef<ISeriesApi<"Candlestick"> | null>(null)

    // Fetch candles
    const { data: candleData } = useSWR(
        symbol ? `/api/candles?limit=200&strategy=${strategy || 'ScalpEmaRsi'}` : null,
        fetcher,
        { refreshInterval: 15000 }
    )

    // Refs for extra series
    const extraSeriesRefs = useRef<Map<string, ISeriesApi<"Line">>>(new Map())

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
            crosshair: {
                mode: 1, // CrosshairMode.Normal
            },
        })

        // Add candlestick series
        try {
            // @ts-ignore
            const series = chart.addSeries(CandlestickSeries, {
                upColor: '#22c55e',
                downColor: '#ef4444',
                borderVisible: false,
                wickUpColor: '#22c55e',
                wickDownColor: '#ef4444',
            }) as ISeriesApi<"Candlestick">
            seriesRef.current = series;
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

            // Set Candle Data
            seriesRef.current.setData(uniqueCandles)

            // Handle Indicators
            if (chartRef.current) {
                const indicators = Object.keys(uniqueCandles[0]).filter(k =>
                    !['time', 'open', 'high', 'low', 'close', 'volume'].includes(k)
                )

                // Define colors for known indicators
                const colorMap: { [key: string]: string } = {
                    'EMA_9': '#3b82f6', // Blue
                    'EMA_20': '#3b82f6',
                    'EMA_21': '#f59e0b', // Orange
                    'EMA_50': '#8b5cf6', // Purple
                    'EMA_200': '#ffffff', // White
                    'BBU_20_2.0': '#10b981', // Green
                    'BBL_20_2.0': '#10b981',
                    'BBM_20_2.0': '#10b981', // Middle
                }

                indicators.forEach(ind => {
                    // Only plot Price Overlays (EMA, BB, SMA) to standard chart
                    // Ignore Oscillators (RSI, ADX, ATR, etc) for now as they have different scale
                    if (ind.startsWith('EMA') || ind.startsWith('BB') || ind.startsWith('SMA')) {
                        let lineSeries = extraSeriesRefs.current.get(ind)

                        if (!lineSeries) {
                            // Create new series
                            const color = colorMap[ind] || '#' + Math.floor(Math.random() * 16777215).toString(16)
                            // @ts-ignore
                            lineSeries = chartRef.current!.addSeries(LineSeries, {
                                color: color,
                                lineWidth: 1,
                                title: ind,
                                priceLineVisible: false,
                                lastValueVisible: false,
                            }) as ISeriesApi<"Line">
                            extraSeriesRefs.current.set(ind, lineSeries)
                        }

                        if (lineSeries) {
                            // Prepare data
                            const lineData = uniqueCandles.map((c: any) => ({
                                time: c.time,
                                value: c[ind]
                            })).filter((d: any) => !isNaN(d.value))

                            lineSeries.setData(lineData)
                        }
                    }
                })
            }

            // Fit content if it's the first load
            try {
                // Determine if we should fit content (simple heuristic: first load)
                // chartRef.current?.timeScale().fitContent() 
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
