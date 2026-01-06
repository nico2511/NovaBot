'use client'
import { useEffect, useRef, useState, useMemo } from 'react'
import { createChart, ColorType, IChartApi, ISeriesApi, Time, CandlestickSeries, LineSeries, LineStyle } from 'lightweight-charts'
import useSWR from 'swr'

interface ChartProps {
    symbol: string
    strategy?: string
    activeTrade?: {
        entry: number
        sl: number
        tp: number
        side: string
    } | null
}

const fetcher = (url: string) => fetch(url).then(res => res.json())

function calculateBollingerBands(data: any[], period = 20, std = 2) {
    const upper: any[] = []
    const basis: any[] = []
    const lower: any[] = []

    for (let i = 0; i < data.length; i++) {
        if (i < period - 1) {
            continue
        }

        const slice = data.slice(i - period + 1, i + 1)
        const closes = slice.map(d => d.close)
        const sum = closes.reduce((a, b) => a + b, 0)
        const mean = sum / period

        const squaredDiffs = closes.map(c => Math.pow(c - mean, 2))
        const variance = squaredDiffs.reduce((a, b) => a + b, 0) / period
        const stdDev = Math.sqrt(variance)

        const time = data[i].time
        basis.push({ time, value: mean })
        upper.push({ time, value: mean + (stdDev * std) })
        lower.push({ time, value: mean - (stdDev * std) })
    }

    return { upper, basis, lower }
}

export default function Chart({ symbol, strategy, activeTrade }: ChartProps) {
    const chartContainerRef = useRef<HTMLDivElement>(null)
    const chartRef = useRef<IChartApi | null>(null)

    // Series Refs
    const seriesRef = useRef<ISeriesApi<"Candlestick"> | null>(null)
    const bbBasisRef = useRef<ISeriesApi<"Line"> | null>(null)
    const bbUpperRef = useRef<ISeriesApi<"Line"> | null>(null)
    const bbLowerRef = useRef<ISeriesApi<"Line"> | null>(null)

    const extraSeriesRefs = useRef<Map<string, ISeriesApi<"Line">>>(new Map())
    const priceLinesRef = useRef<any[]>([])

    // OPTIMIZATION: Fetch candles with optimized SWR config
    const { data: candleData, error } = useSWR(
        symbol ? `/api/candles?limit=200&strategy=${strategy || 'ScalpEmaRsi'}&symbol=${symbol}` : null,
        fetcher,
        {
            refreshInterval: 5000,
            dedupingInterval: 2000,
            revalidateOnFocus: false,
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

        const resizeObserver = new ResizeObserver(() => handleResize())
        resizeObserver.observe(chartContainerRef.current)

        return () => {
            resizeObserver.disconnect()
        }
    }, [])

    // Initialize Chart
    useEffect(() => {
        if (!chartContainerRef.current) return
        if (chartRef.current) return

        console.log("Initializing chart instance...")

        const chart = createChart(chartContainerRef.current, {
            layout: {
                background: { type: ColorType.Solid, color: 'transparent' },
                textColor: '#9CA3AF',
            },
            grid: {
                vertLines: { color: 'rgba(42, 46, 57, 0.1)' },
                horzLines: { color: 'rgba(42, 46, 57, 0.1)' },
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
                mode: 1,
            },
        })

        // Add candlestick series
        const series = chart.addSeries(CandlestickSeries, {
            upColor: '#22c55e',
            downColor: '#ef4444',
            borderVisible: false,
            wickUpColor: '#22c55e',
            wickDownColor: '#ef4444',
        })
        seriesRef.current = series

        // Init BB Series
        // Basis (Orange/Yellow)
        const basis = chart.addSeries(LineSeries, {
            color: '#fbbf24', // Amber-400
            lineWidth: 1,
            title: 'BB Basis'
        })
        bbBasisRef.current = basis

        // Upper (Blue/Transparent)
        const upper = chart.addSeries(LineSeries, {
            color: 'rgba(59, 130, 246, 0.5)', // Blue-500 transparent
            lineWidth: 1,
            title: 'BB Upper'
        })
        bbUpperRef.current = upper

        // Lower (Blue/Transparent)
        const lower = chart.addSeries(LineSeries, {
            color: 'rgba(59, 130, 246, 0.5)',
            lineWidth: 1,
            title: 'BB Lower'
        })
        bbLowerRef.current = lower

        chartRef.current = chart

        return () => {
            chart.remove()
            chartRef.current = null
        }
    }, [])

    // Update Data & Indicators
    useEffect(() => {
        if (!seriesRef.current || !candleData?.candles || candleData.candles.length === 0) return

        // Format and Sort
        const sortedCandles = [...candleData.candles]
            .sort((a: any, b: any) => a.time - b.time)
            .filter((v, i, a) => i === a.findIndex((t: any) => t.time === v.time))

        try {
            // 1. Update Candles
            seriesRef.current.setData(sortedCandles)

            // 2. Client-Side Bollinger Bands
            const { upper, basis, lower } = calculateBollingerBands(sortedCandles)
            bbBasisRef.current?.setData(basis)
            bbUpperRef.current?.setData(upper)
            bbLowerRef.current?.setData(lower)

            // 3. Handle Other Backend Indicators (EMAs, etc.)
            if (chartRef.current) {
                const firstCandle = sortedCandles[0]
                const backendIndicators = Object.keys(firstCandle).filter(k =>
                    (k.startsWith('EMA') || k.startsWith('SMA')) &&
                    !['time', 'open', 'high', 'low', 'close', 'volume'].includes(k)
                )

                const colorMap: { [key: string]: string } = {
                    'EMA_9': '#3b82f6',
                    'EMA_20': '#3b82f6',
                    'EMA_21': '#f59e0b',
                    'EMA_50': '#8b5cf6',
                    'EMA_200': '#ffffff',
                }

                // Clean old extra series not in current data? 
                // For simplicity, we just add new ones or update existing
                backendIndicators.forEach(ind => {
                    let lineSeries = extraSeriesRefs.current.get(ind)

                    if (!lineSeries) {
                        const color = colorMap[ind] || '#' + Math.floor(Math.random() * 16777215).toString(16)
                        const newSeries = chartRef.current!.addSeries(LineSeries, {
                            color: color,
                            lineWidth: 1,
                            title: ind,
                        })
                        lineSeries = newSeries
                        extraSeriesRefs.current.set(ind, newSeries)
                    }

                    if (lineSeries) {
                        const lineData = sortedCandles.map((c: any) => ({
                            time: c.time,
                            value: c[ind]
                        })).filter((d: any) => !isNaN(d.value) && d.value !== null)
                        lineSeries.setData(lineData)
                    }
                })
            }
        } catch (e) {
            console.error("Error setting chart data:", e)
        }
    }, [candleData, symbol])

    // Manage Active Trade Lines (Robust TP/SL)
    useEffect(() => {
        if (!seriesRef.current) return

        // 1. Clean up ALL existing price lines
        const series = seriesRef.current
        priceLinesRef.current.forEach(line => {
            try {
                series.removePriceLine(line)
            } catch (e) {
                // Ignore matching errors if series changed
            }
        })
        priceLinesRef.current = []

        // If no active trade, we stop here (clean state)
        if (!activeTrade) return

        try {
            // 2. Add Entry Line
            if (activeTrade.entry) {
                const entryLine = series.createPriceLine({
                    price: activeTrade.entry,
                    color: '#3b82f6', // Blue
                    lineWidth: 2,
                    lineStyle: LineStyle.Dotted,
                    axisLabelVisible: true,
                    title: `ENTRY ${activeTrade.side}`,
                })
                priceLinesRef.current.push(entryLine)
            }

            // 3. Add SL Line (Red, Dashed)
            if (activeTrade.sl) {
                const slLine = series.createPriceLine({
                    price: activeTrade.sl,
                    color: '#ef4444', // Red
                    lineWidth: 2,
                    axisLabelVisible: true,
                    title: 'SL',
                    lineStyle: LineStyle.Dashed,
                })
                priceLinesRef.current.push(slLine)
            }

            // 4. Add TP Line (Green, Dashed)
            if (activeTrade.tp) {
                const tpLine = series.createPriceLine({
                    price: activeTrade.tp,
                    color: '#10b981', // Green
                    lineWidth: 2,
                    axisLabelVisible: true,
                    title: 'TP',
                    lineStyle: LineStyle.Dashed,
                })
                priceLinesRef.current.push(tpLine)
            }

        } catch (e) {
            console.error("Error drawing trade lines:", e)
        }

    }, [activeTrade, candleData])

    return (
        <div className="w-full relative">
            <div className="absolute top-6 left-6 z-10 flex gap-2">
                <div className="bg-surface/80 backdrop-blur px-3 py-1 rounded text-sm border border-border/50 shadow-sm flex items-center gap-2">
                    <span className="font-bold text-white">{symbol}</span>
                    <span className="text-gray-400">15m</span>
                    {error && <span className="text-red-500 text-xs ml-2">⚠️ Data Error</span>}
                </div>
            </div>
            <div ref={chartContainerRef} className="w-full h-[400px]" />
        </div>
    )
}
