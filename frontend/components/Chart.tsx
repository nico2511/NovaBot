'use client'
import { useEffect, useRef, useMemo, useState } from 'react'
import {
    createChart,
    ColorType,
    IChartApi,
    ISeriesApi,
    CrosshairMode,
    LineStyle,
    UTCTimestamp,
    CandlestickSeries,
    LineSeries
} from 'lightweight-charts'
import useSWR from 'swr'

// --- TYPES ---
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

// --- INDICATOR HELPERS (Client Side Calculation) ---
// Calcule les Bandes de Bollinger (20, 2 std dev) localement pour fluidité maximale
const calculateBollingerBands = (data: any[], period = 20, multiplier = 2) => {
    const basis = []
    const upper = []
    const lower = []

    for (let i = 0; i < data.length; i++) {
        if (i < period - 1) {
            basis.push({ time: data[i].time, value: NaN })
            upper.push({ time: data[i].time, value: NaN })
            lower.push({ time: data[i].time, value: NaN })
            continue
        }
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
    const candleSeriesRef = useRef<ISeriesApi<"Candlestick"> | null>(null)

    // Indicators Refs
    const bbUpperRef = useRef<ISeriesApi<"Line"> | null>(null)
    const bbLowerRef = useRef<ISeriesApi<"Line"> | null>(null)
    const bbBasisRef = useRef<ISeriesApi<"Line"> | null>(null)

    // Trade Lines Refs (pour nettoyage propre)
    const tradeLinesRef = useRef<any[]>([])

    // DATA FETCHING (Refresh rapide 5s)
    const { data: candleData, error } = useSWR(
        symbol ? `/api/candles?limit=300&symbol=${symbol}` : null,
        fetcher,
        {
            refreshInterval: 5000,
            dedupingInterval: 2000,
            keepPreviousData: true  // Keep previous data during revalidation
        }
    )

    // --- 1. INITIALIZATION ---
    useEffect(() => {
        if (!chartContainerRef.current) return

        // Configuration Deep Dark Theme Pro
        const chart = createChart(chartContainerRef.current, {
            layout: {
                background: { type: ColorType.Solid, color: '#0b0e11' }, // Fond très sombre
                textColor: '#9ca3af', // Gris Tailwind 400
                fontFamily: "'Inter', sans-serif",
            },
            grid: {
                vertLines: { color: '#1f2937', style: LineStyle.Dotted }, // Grille subtile
                horzLines: { color: '#1f2937', style: LineStyle.Dotted },
            },
            crosshair: {
                mode: CrosshairMode.Normal,
                vertLine: { width: 1, color: '#6366f1', style: LineStyle.Dashed, labelBackgroundColor: '#6366f1' },
                horzLine: { width: 1, color: '#6366f1', style: LineStyle.Dashed, labelBackgroundColor: '#6366f1' },
            },
            rightPriceScale: {
                borderColor: '#374151',
                scaleMargins: { top: 0.1, bottom: 0.1 }, // Marges pour indicateurs
            },
            timeScale: {
                borderColor: '#374151',
                timeVisible: true,
                secondsVisible: false,
            },
        })

        // Séries Bougies (Couleurs TradingView)
        const candleSeries = chart.addSeries(CandlestickSeries, {
            upColor: '#26a69a', downColor: '#ef5350',
            borderUpColor: '#26a69a', borderDownColor: '#ef5350',
            wickUpColor: '#26a69a', wickDownColor: '#ef5350',
        })
        candleSeriesRef.current = candleSeries

        // Séries Bollinger (Subtiles)
        bbUpperRef.current = chart.addSeries(LineSeries, { color: 'rgba(59, 130, 246, 0.3)', lineWidth: 1, crosshairMarkerVisible: false })
        bbLowerRef.current = chart.addSeries(LineSeries, { color: 'rgba(59, 130, 246, 0.3)', lineWidth: 1, crosshairMarkerVisible: false })
        bbBasisRef.current = chart.addSeries(LineSeries, { color: 'rgba(251, 146, 60, 0.5)', lineWidth: 1, lineStyle: LineStyle.Solid, crosshairMarkerVisible: false }) // Basis Orange

        chartRef.current = chart

        // Resize Observer Responsive
        const handleResize = () => {
            if (chartContainerRef.current) {
                chart.applyOptions({ width: chartContainerRef.current.clientWidth, height: chartContainerRef.current.clientHeight })
            }
        }
        window.addEventListener('resize', handleResize)
        return () => { window.removeEventListener('resize', handleResize); chart.remove() }
    }, [])

    // --- 2. DATA UPDATES & INDICATORS CALCULATION ---
    useEffect(() => {
        if (!chartRef.current || !candleData) return

        // Ensure candleData is an array
        const rawData = Array.isArray(candleData) ? candleData : []
        if (rawData.length === 0) return

        // Formatage des données
        const formattedData = rawData.map((c: any) => ({
            time: c.time as UTCTimestamp, open: c.open, high: c.high, low: c.low, close: c.close
        }))
        candleSeriesRef.current?.setData(formattedData)

        // Calcul et mise à jour des Bollinger Bands
        const bbData = calculateBollingerBands(formattedData)
        bbBasisRef.current?.setData(bbData.basis.filter(d => !isNaN(d.value)))
        bbUpperRef.current?.setData(bbData.upper.filter(d => !isNaN(d.value)))
        bbLowerRef.current?.setData(bbData.lower.filter(d => !isNaN(d.value)))

    }, [candleData])

    // --- 3. ACTIVE TRADE LINES MANAGEMENT (TP/SL) ---
    useEffect(() => {
        if (!candleSeriesRef.current) return

        // Nettoyage impératif des anciennes lignes
        tradeLinesRef.current.forEach(line => candleSeriesRef.current?.removePriceLine(line))
        tradeLinesRef.current = []

        if (activeTrade) {
            // ENTRY LINE (Jaune plein)
            tradeLinesRef.current.push(candleSeriesRef.current.createPriceLine({
                price: activeTrade.entry, color: '#fbbf24', lineWidth: 2, lineStyle: LineStyle.Solid, axisLabelVisible: true, title: `ENTRY ${activeTrade.side}`,
            }))
            // SL LINE (Rouge pointillé)
            if (activeTrade.sl) {
                tradeLinesRef.current.push(candleSeriesRef.current.createPriceLine({
                    price: activeTrade.sl, color: '#ef4444', lineWidth: 2, lineStyle: LineStyle.Dashed, axisLabelVisible: true, title: `SL`,
                }))
            }
            // TP LINE (Vert pointillé)
            if (activeTrade.tp) {
                tradeLinesRef.current.push(candleSeriesRef.current.createPriceLine({
                    price: activeTrade.tp, color: '#10b981', lineWidth: 2, lineStyle: LineStyle.Dashed, axisLabelVisible: true, title: `TP`,
                }))
            }
        }
    }, [activeTrade])

    return (
        <div className="w-full h-full relative group rounded-xl overflow-hidden shadow-2xl border border-gray-800 bg-[#0b0e11]">
            {/* Header Overlay Flottant */}
            <div className="absolute top-4 left-4 z-10 flex gap-2 pointer-events-none">
                <div className="bg-[#1f2937]/80 backdrop-blur-md px-3 py-1.5 rounded-lg border border-gray-700/50 flex items-center gap-3">
                    <div className="flex flex-col">
                        <span className="font-bold text-gray-100 text-lg leading-none">{symbol}</span>
                        <span className="text-[10px] text-gray-400 font-mono mt-0.5">PERP • 15m</span>
                    </div>
                    {activeTrade && (
                        <div className={`px-2 py-0.5 rounded text-[10px] font-bold border ${activeTrade.side === 'BUY' ? 'bg-green-500/20 text-green-400 border-green-500/30' : 'bg-red-500/20 text-red-400 border-red-500/30'
                            }`}>
                            {activeTrade.side} OPEN
                        </div>
                    )}
                </div>
            </div>
            {/* Conteneur du Graphique */}
            <div ref={chartContainerRef} className="w-full h-full" />
            {/* Loading State */}
            {!candleData && (
                <div className="absolute inset-0 flex items-center justify-center bg-[#0b0e11]/80 z-0">
                    <div className="animate-pulse text-indigo-400 font-mono text-sm">LOADING MARKET DATA...</div>
                </div>
            )}
        </div>
    )
}
