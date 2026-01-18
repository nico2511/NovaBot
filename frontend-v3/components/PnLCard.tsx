interface PnLCardProps {
    dailyPnL: number;
    activePositions: number;
    lastUpdated: string | null;
}

export default function PnLCard({ dailyPnL, activePositions, lastUpdated }: PnLCardProps) {
    const isProfit = dailyPnL > 0;
    const isNeutral = dailyPnL === 0;

    const colorClass = isProfit ? 'text-profit' : isNeutral ? 'text-gray-400' : 'text-loss';
    const bgClass = isProfit ? 'bg-profit/10' : isNeutral ? 'bg-gray-800' : 'bg-loss/10';
    const borderClass = isProfit ? 'border-profit/30' : isNeutral ? 'border-gray-700' : 'border-loss/30';

    return (
        <div className={`${bgClass} ${borderClass} border-2 rounded-2xl p-8`}>
            <div className="text-center">
                <div className="text-sm text-gray-400 mb-2">Daily PnL</div>
                <div className={`text-6xl font-bold ${colorClass} mb-4`}>
                    {isProfit && '+'}${dailyPnL.toFixed(2)}
                </div>
                <div className="flex items-center justify-center gap-6 text-sm text-gray-400">
                    <div>
                        <span className="font-semibold text-white">{activePositions}</span> Active Position{activePositions !== 1 ? 's' : ''}
                    </div>
                    {lastUpdated && (
                        <div className="text-xs">
                            Updated: {new Date(lastUpdated).toLocaleTimeString()}
                        </div>
                    )}
                </div>
            </div>
        </div>
    );
}
