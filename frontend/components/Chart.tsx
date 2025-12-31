'use client'
import { useEffect, useRef, useState, useMemo } from 'react'
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
    const extraSeriesRefs = useRef<Map<string, ISeriesApi<"Line">>>(new Map())

    // OPTIMIZATION: Fetch candles with optimized SWR config
    const { data: candleData, error } = useSWR(
        symbol ? `/api/candles?limit=200&strategy=${strategy || 'ScalpEmaRsi'}&symbol=${symbol}` : null,
        fetcher,
        {
            refreshInterval: 15000,
            dedupingInterval: 10000,  // Dedupe requests within 10s
            revalidateOnFocus: false,  // Don't refetch on window focus
            revalidateOnReconnect: false,  // Don't refetch on reconnect
            shouldRetryOnError: true
        }
    )

    // Resize observer
    useEffect(() => {
        if (!chartContainerRef.current) return;

        const handleResize = () => {
            if (chartContainerRef.current && chartRef.current) {
                chartRef.current.applyOptions({
                    width: chartContainerRef.current.clientWidth,
                    height: 400
                })
            }
        }

        window.addEventListener('resize', handleResize)

        return () => {
            window.removeEventListener('resize', handleResize)
        }
    }, [])

    // Initialize Chart
    useEffect(() => {
        if (!chartContainerRef.current) return

        if (chartRef.current) {
            // Already initialized
            return;
        }

        console.log("Initializing chart instance...")

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
                borderColor: 'rgba(42, 46, 57, 0.4)',
            },
            rightPriceScale: {
                borderColor: 'rgba(42, 46, 57, 0.4)',
            },
            crosshair: {
                mode: 1, // CrosshairMode.Normal
            },
        })

        // Add candlestick series
        try {
            const series = chart.addSeries(CandlestickSeries, {
                upColor: '#22c55e',
                downColor: '#ef4444',
                borderVisible: false,
                wickUpColor: '#22c55e',
                wickDownColor: '#ef4444',
            })
            seriesRef.current = series;
        } catch (e) {
            console.error("Failed to add candlestick series:", e);
        }

        chartRef.current = chart

        return () => {
            // Cleanup handled by ref check or parent unmount
            // But we usually want to keep it unless unmounted
            console.log("Cleaning up chart instance")
            chart.remove()
            chartRef.current = null
        }
    }, [])

    // Update Data
    useEffect(() => {
        if (!seriesRef.current || !candleData?.candles) {
            console.log("Waiting for data or series...", { hasSeries: !!seriesRef.current, hasData: !!candleData })
            return
        }

        if (candleData.candles.length === 0) {
            console.log("Empty candles array")
            return
        }

        console.log(`Received ${candleData.candles.length} candles`)

        // Format and Sort
        const sortedCandles = [...candleData.candles]
            .sort((a: any, b: any) => a.time - b.time)
            .filter((v, i, a) => i === a.findIndex((t: any) => t.time === v.time)) // Unique by time

        try {
            // Update candles
            seriesRef.current.setData(sortedCandles)

            // Fit content on first load if we haven't
            // We can use a simple flag or just check if generic data exists
            // chartRef.current?.timeScale().fitContent()

        } catch (e) {
            console.error("Error setting candle data:", e)
        }

        // Handle Indicators
        if (chartRef.current) {
            const firstCandle = sortedCandles[0]
            const indicators = Object.keys(firstCandle).filter(k =>
                !['time', 'open', 'high', 'low', 'close', 'volume'].includes(k)
            )

            const colorMap: { [key: string]: string } = {
                'EMA_9': '#3b82f6',
                'EMA_20': '#3b82f6',
                'EMA_21': '#f59e0b',
                'EMA_50': '#8b5cf6',
                'EMA_200': '#ffffff',
                'BBU_20_2.0': 'rgba(52, 211, 153, 0.3)',
                'BBL_20_2.0': 'rgba(52, 211, 153, 0.3)',
                'BBM_20_2.0': '#10b981',
            }

            indicators.forEach(ind => {
                if (ind.startsWith('EMA') || ind.startsWith('BB') || ind.startsWith('SMA')) {
                    let lineSeries = extraSeriesRefs.current.get(ind)

                    if (!lineSeries) {
                        try {
                            const color = colorMap[ind] || '#' + Math.floor(Math.random() * 16777215).toString(16)
                            const newSeries = chartRef.current!.addSeries(LineSeries, {
                                color: color,
                                lineWidth: 1,
                                title: ind,
                                crosshairMarkerVisible: true,
                                priceLineVisible: false,
                            })
                            lineSeries = newSeries
                            extraSeriesRefs.current.set(ind, newSeries)
                        } catch (e) {
                            console.error(`Failed to create series ${ind}:`, e)
                        }
                    }

                    if (lineSeries) {
                        const lineData = sortedCandles.map((c: any) => ({
                            time: c.time,
                            value: c[ind]
                        })).filter((d: any) => !isNaN(d.value) && d.value !== null)

                        lineSeries.setData(lineData)
                    }
                }
            })
        }

    }, [candleData])

    return (
        <div className="w-full relative">
            <div className="absolute top-6 left-6 z-10 flex gap-2">
                <div className="bg-surface/80 backdrop-blur px-3 py-1 rounded text-sm border border-border/50 shadow-sm">
                    <span className="font-bold text-white">{symbol}</span>
                    <span className="ml-2 text-gray-400">15m</span>
                    {error && <span className="ml-2 text-red-500">Error loading data</span>}
                </div>
            </div>
            <div ref={chartContainerRef} className="w-full h-[400px]" />
        </div>
    )
}
