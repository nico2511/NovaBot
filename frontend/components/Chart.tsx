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
        metadata?: any
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

// Calcule l'EMA (Exponential Moving Average)
const calculateEMA = (data: any[], period: number) => {
    const ema = []
    const multiplier = 2 / (period + 1)

    for (let i = 0; i < data.length; i++) {
        if (i < period - 1) {
            ema.push({ time: data[i].time, value: NaN })
            continue
        }

        if (i === period - 1) {
            // First EMA = SMA
            const slice = data.slice(0, period)
            const sum = slice.reduce((acc: number, val: any) => acc + val.close, 0)
            ema.push({ time: data[i].time, value: sum / period })
        } else {
            // EMA = (Close - EMA_prev) * multiplier + EMA_prev
            const prevEMA: number = ema[i - 1].value
            const currentEMA = (data[i].close - prevEMA) * multiplier + prevEMA
            ema.push({ time: data[i].time, value: currentEMA })
        }
    }

    return ema
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
    const ema21Ref = useRef<ISeriesApi<"Line"> | null>(null)
    const ema200Ref = useRef<ISeriesApi<"Line"> | null>(null)

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

        // Fetch Metadata for precision
        fetch('/api/meta').then(async res => {
            const meta = await res.json()
            if (symbol && meta[symbol]) {
                // Heuristic: If size decimals is 0 (like PEPE/DOGE), price precision is usually high (6-8)
                // If size decimals is 3-5 (like BTC/ETH), price precision is usually 2
                // This matches Hyperliquid's logic roughly
                const szDecimals = meta[symbol].szDecimals
                let pricePrecision = 2
                let minMove = 0.01

                if (szDecimals === 0) {
                    pricePrecision = 8
                    minMove = 0.00000001
                } else if (szDecimals >= 3) {
                    pricePrecision = 2
                    minMove = 0.01
                }

                chart.applyOptions({
                    localization: {
                        priceFormatter: (p: number) => p.toFixed(pricePrecision),
                    },
                })

                // We will update the series options later when we create it or now if possible
                // Ideally we set it on the series. capture ref to set it later or set state.
            }
        }).catch(e => console.error("Meta fetch error", e))


        // Séries Bougies (Couleurs TradingView)
        const candleSeries = chart.addSeries(CandlestickSeries, {
            upColor: '#26a69a', downColor: '#ef5350',
            borderUpColor: '#26a69a', borderDownColor: '#ef5350',
            wickUpColor: '#26a69a', wickDownColor: '#ef5350',
            priceFormat: {
                type: 'price',
                precision: 8, // Support up to 8 decimals for memecoins
                minMove: 0.00000001,
            },
        })
        candleSeriesRef.current = candleSeries

        // Séries Bollinger (Subtiles)
        bbUpperRef.current = chart.addSeries(LineSeries, { color: 'rgba(59, 130, 246, 0.3)', lineWidth: 1, crosshairMarkerVisible: false })
        bbLowerRef.current = chart.addSeries(LineSeries, { color: 'rgba(59, 130, 246, 0.3)', lineWidth: 1, crosshairMarkerVisible: false })
        bbBasisRef.current = chart.addSeries(LineSeries, { color: 'rgba(251, 146, 60, 0.5)', lineWidth: 1, lineStyle: LineStyle.Solid, crosshairMarkerVisible: false }) // Basis Orange

        // EMA 21 (Yellow - Short-term trend)
        ema21Ref.current = chart.addSeries(LineSeries, { color: 'rgba(234, 179, 8, 0.8)', lineWidth: 2, lineStyle: LineStyle.Solid, crosshairMarkerVisible: false })

        // EMA 200 (Purple - Long-term trend)
        ema200Ref.current = chart.addSeries(LineSeries, { color: 'rgba(168, 85, 247, 0.6)', lineWidth: 2, lineStyle: LineStyle.Solid, crosshairMarkerVisible: false })

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

        // Ensure candleData is handled correctly (API returns { candles: [...] })
        const rawData = candleData?.candles || (Array.isArray(candleData) ? candleData : [])
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

        // Calcul et mise à jour de l'EMA 21
        const ema21Data = calculateEMA(formattedData, 21)
        ema21Ref.current?.setData(ema21Data.filter(d => !isNaN(d.value)))

        // Calcul et mise à jour de l'EMA 200
        const ema200Data = calculateEMA(formattedData, 200)
        ema200Ref.current?.setData(ema200Data.filter(d => !isNaN(d.value)))

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

            // CUSTOM STRATEGY LINES (Metadata)
            if (activeTrade.metadata) {
                // FIBO 61.8
                if (activeTrade.metadata.fibo_618) {
                    tradeLinesRef.current.push(candleSeriesRef.current.createPriceLine({
                        price: activeTrade.metadata.fibo_618,
                        color: '#d97706', // Amber-600
                        lineWidth: 1,
                        lineStyle: LineStyle.Dotted,
                        axisLabelVisible: true,
                        title: `FIB 61.8%`,
                    }))
                }
                // SWING HIGH/LOW (Optional but helpful)
                // if (activeTrade.metadata.swing_high) { ... }
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

            {/* Chart Legend */}
            <div className="absolute bottom-12 left-4 z-10 flex flex-wrap gap-3 pointer-events-none">
                <div className="bg-[#1f2937]/80 backdrop-blur-md px-3 py-1.5 rounded-lg border border-gray-700/50 flex items-center gap-2">
                    <div className="w-3 h-0.5 bg-[#eab308]"></div>
                    <span className="text-[10px] text-gray-300 font-medium">EMA 21</span>
                </div>
                <div className="bg-[#1f2937]/80 backdrop-blur-md px-3 py-1.5 rounded-lg border border-gray-700/50 flex items-center gap-2">
                    <div className="w-3 h-0.5 bg-[#a855f7]"></div>
                    <span className="text-[10px] text-gray-300 font-medium">EMA 200</span>
                </div>
                <div className="bg-[#1f2937]/80 backdrop-blur-md px-3 py-1.5 rounded-lg border border-gray-700/50 flex items-center gap-2">
                    <div className="w-3 h-0.5 bg-[#fb923c]"></div>
                    <span className="text-[10px] text-gray-300 font-medium">BB Basis</span>
                </div>
                <div className="bg-[#1f2937]/80 backdrop-blur-md px-3 py-1.5 rounded-lg border border-gray-700/50 flex items-center gap-2">
                    <div className="w-3 h-0.5 bg-[#3b82f6] opacity-50"></div>
                    <span className="text-[10px] text-gray-300 font-medium">BB Bands</span>
                </div>
                {activeTrade?.metadata?.fibo_618 && (
                    <div className="bg-[#1f2937]/80 backdrop-blur-md px-3 py-1.5 rounded-lg border border-gray-700/50 flex items-center gap-2">
                        <div className="w-3 h-0.5 border-t border-dashed border-[#d97706]"></div>
                        <span className="text-[10px] text-gray-300 font-medium">Fibo 61.8%</span>
                    </div>
                )}
            </div>

            {/* Loading State */}
            {!candleData && (
                <div className="absolute inset-0 flex items-center justify-center bg-[#0b0e11]/80 z-0">
                    <div className="text-gray-400 text-sm">Loading chart...</div>
                </div>
            )}
        </div>
    )
}
