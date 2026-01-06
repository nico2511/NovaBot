'use client'
import { useEffect, useRef } from 'react'
import {
    createChart,
    ColorType,
    IChartApi,
    ISeriesApi,
    LineStyle,
    UTCTimestamp,
    CandlestickSeries, // INDISPENSABLE POUR V5
    LineSeries         // INDISPENSABLE POUR V5
} from 'lightweight-charts'
import useSWR from 'swr'

// --- TYPES ---
interface ChartProps {
    symbol: string
    strategy?: string  // AJOUTÉ: Corrige l'erreur de build dans page.tsx
    activeTrade?: {
        entry: number
        sl: number
        tp: number
        side: string
    } | null
}

// --- HELPERS ---
const calculateBollingerBands = (data: any[], period = 20, multiplier = 2) => {
    const basis = []
    const upper = []
    const lower = []

    for (let i = 0; i < data.length; i++) {
        if (i < period - 1) continue

        const slice = data.slice(i - period + 1, i + 1)
        const sum = slice.reduce((acc: number, val: any) => acc + val.close, 0)
        const mean = sum / period

        const squaredDiffs = slice.map((val: any) => Math.pow(val.close - mean, 2))
        const variance = squaredDiffs.reduce((acc: number, val: number) => acc + val, 0) / period
        const stdDev = Math.sqrt(variance)

        basis.push({ time: data[i].time, value: mean })
        upper.push({ time: data[i].time, value: mean + (stdDev * multiplier) })
        lower.push({ time: data[i].time, value: mean - (stdDev * multiplier) })
    }
    return { basis, upper, lower }
}

const fetcher = (url: string) => fetch(url).then(res => res.json())

export default function Chart({ symbol, strategy, activeTrade }: ChartProps) {
    const chartContainerRef = useRef<HTMLDivElement>(null)
    const chartRef = useRef<IChartApi | null>(null)

    // Refs Séries (Typage générique V5)
    const candleSeriesRef = useRef<ISeriesApi<"Candlestick"> | null>(null)
    const bbUpperRef = useRef<ISeriesApi<"Line"> | null>(null)
    const bbLowerRef = useRef<ISeriesApi<"Line"> | null>(null)
    const bbBasisRef = useRef<ISeriesApi<"Line"> | null>(null)

    const tradeLinesRef = useRef<any[]>([])

    const { data: candleData } = useSWR(
        symbol ? `/api/candles?limit=300&symbol=${symbol}` : null,
        fetcher,
        { refreshInterval: 5000, dedupingInterval: 2000, keepPreviousData: true }
    )

    // --- 1. INITIALISATION (SYNTAXE V5) ---
    useEffect(() => {
        if (!chartContainerRef.current) return

        const chart = createChart(chartContainerRef.current, {
            layout: {
                background: { type: ColorType.Solid, color: '#0b0e11' },
                textColor: '#9ca3af',
                fontFamily: "'Inter', sans-serif",
            },
            grid: {
                vertLines: { color: '#1f2937', style: LineStyle.Dotted },
                horzLines: { color: '#1f2937', style: LineStyle.Dotted },
            },
            timeScale: {
                borderColor: '#374151',
                timeVisible: true,
                secondsVisible: false,
            },
        })

        // --- CORRECTION V5 ---
        // On utilise chart.addSeries(Classe, Options)
        candleSeriesRef.current = chart.addSeries(CandlestickSeries, {
            upColor: '#26a69a', downColor: '#ef5350',
            borderUpColor: '#26a69a', borderDownColor: '#ef5350',
            wickUpColor: '#26a69a', wickDownColor: '#ef5350',
        })

        bbUpperRef.current = chart.addSeries(LineSeries, { color: 'rgba(59, 130, 246, 0.3)', lineWidth: 1, crosshairMarkerVisible: false })
        bbLowerRef.current = chart.addSeries(LineSeries, { color: 'rgba(59, 130, 246, 0.3)', lineWidth: 1, crosshairMarkerVisible: false })
        bbBasisRef.current = chart.addSeries(LineSeries, { color: 'rgba(251, 146, 60, 0.5)', lineWidth: 1, lineStyle: LineStyle.Solid, crosshairMarkerVisible: false })

        chartRef.current = chart

        const handleResize = () => {
            if (chartContainerRef.current) {
                chart.applyOptions({ width: chartContainerRef.current.clientWidth, height: chartContainerRef.current.clientHeight })
            }
        }
        window.addEventListener('resize', handleResize)
        handleResize()

        return () => { window.removeEventListener('resize', handleResize); chart.remove() }
    }, [])

    // --- 2. DATA UPDATE (SECURE SORT) ---
    useEffect(() => {
        if (!chartRef.current || !candleData) return

        const rawData = Array.isArray(candleData) ? candleData : []
        if (rawData.length === 0) return

        // 1. Map & Format
        let formattedData = rawData.map((c: any) => ({
            time: c.time as UTCTimestamp,
            open: c.open, high: c.high, low: c.low, close: c.close
        }))

        // 2. SORT (Vital pour éviter crash v5)
        formattedData.sort((a: any, b: any) => a.time - b.time)

        // 3. DEDUPLICATE (Vital pour éviter crash v5)
        formattedData = formattedData.filter((item: any, index: number, self: any[]) =>
            index === self.findIndex((t: any) => t.time === item.time)
        )

        try {
            candleSeriesRef.current?.setData(formattedData)

            const bbData = calculateBollingerBands(formattedData)
            bbBasisRef.current?.setData(bbData.basis)
            bbUpperRef.current?.setData(bbData.upper)
            bbLowerRef.current?.setData(bbData.lower)
        } catch (e) {
            console.error("Chart Data Error:", e)
        }

    }, [candleData])

    // --- 3. TRADE LINES ---
    useEffect(() => {
        if (!candleSeriesRef.current) return
        tradeLinesRef.current.forEach(line => candleSeriesRef.current?.removePriceLine(line))
        tradeLinesRef.current = []

        if (activeTrade) {
            tradeLinesRef.current.push(candleSeriesRef.current.createPriceLine({
                price: activeTrade.entry, color: '#fbbf24', lineWidth: 2, title: `ENTRY ${activeTrade.side}`
            }))
            if (activeTrade.sl) tradeLinesRef.current.push(candleSeriesRef.current.createPriceLine({
                price: activeTrade.sl, color: '#ef4444', lineWidth: 2, lineStyle: LineStyle.Dashed, title: 'SL'
            }))
            if (activeTrade.tp) tradeLinesRef.current.push(candleSeriesRef.current.createPriceLine({
                price: activeTrade.tp, color: '#10b981', lineWidth: 2, lineStyle: LineStyle.Dashed, title: 'TP'
            }))
        }
    }, [activeTrade])

    return (
        <div className="w-full h-full relative group rounded-xl overflow-hidden shadow-2xl border border-gray-800 bg-[#0b0e11]">
            <div className="absolute top-4 left-4 z-10 flex gap-2 pointer-events-none">
                <div className="bg-[#1f2937]/80 backdrop-blur-md px-3 py-1.5 rounded-lg border border-gray-700/50 flex items-center gap-3">
                    <div className="flex flex-col">
                        <span className="font-bold text-gray-100 text-lg leading-none">{symbol}</span>
                        <span className="text-[10px] text-gray-400 font-mono mt-0.5">PERP • 15m</span>
                    </div>
                    {/* Affichage de la stratégie si disponible */}
                    {strategy && (
                        <div className="hidden sm:block px-2 py-0.5 rounded text-[10px] font-bold border bg-indigo-500/20 text-indigo-300 border-indigo-500/30">
                            {strategy}
                        </div>
                    )}
                </div>
            </div>
            <div ref={chartContainerRef} className="w-full h-full" />
            {!candleData && (
                <div className="absolute inset-0 flex items-center justify-center bg-[#0b0e11]/80 z-0">
                    <div className="animate-pulse text-indigo-400 font-mono text-sm">LOADING MARKET DATA...</div>
                </div>
            )}
        </div>
    )
}