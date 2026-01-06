import { Trade } from '@/hooks/useTradeHistory'
import { useMemo } from 'react'
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, ReferenceLine } from 'recharts'

interface PnLChartProps {
    trades: Trade[]
}

export default function PnLChart({ trades }: PnLChartProps) {
    const chartData = useMemo(() => {
        // Sort oldest first for cumulative math
        const sorted = [...trades].reverse()
        let runningPnL = 0
        return sorted.map(t => {
            const pnl = t.pnl ?? 0
            runningPnL += pnl
            // Use timestamp or exit_time for label
            const date = new Date(t.exit_time || t.timestamp || 0)
            return {
                time: date.toLocaleDateString(), // Simple date for XAxis
                fullTime: date.toLocaleString(), // Tooltip
                pnl: runningPnL,
                trade_pnl: pnl
            }
        })
    }, [trades])

    if (trades.length === 0) return null

    return (
        <div className="w-full h-full">
            <ResponsiveContainer width="100%" height="100%">
                <LineChart data={chartData}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#ffffff10" />
                    <XAxis
                        dataKey="time"
                        stroke="#6b7280"
                        fontSize={10}
                        tick={{ fill: '#6b7280' }}
                        minTickGap={30}
                    />
                    <YAxis
                        stroke="#6b7280"
                        fontSize={10}
                        tick={{ fill: '#6b7280' }}
                    />
                    <Tooltip
                        contentStyle={{ backgroundColor: '#1f2937', borderColor: '#374151', borderRadius: '8px' }}
                        itemStyle={{ color: '#fff' }}
                        labelFormatter={(label, payload) => payload[0]?.payload?.fullTime}
                    />
                    <ReferenceLine y={0} stroke="#ffffff30" />
                    <Line
                        type="monotone"
                        dataKey="pnl"
                        stroke="#8b5cf6"
                        strokeWidth={2}
                        dot={false}
                        activeDot={{ r: 6 }}
                    />
                </LineChart>
            </ResponsiveContainer>
        </div>
    )
}
