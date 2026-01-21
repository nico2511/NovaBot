'use client';

import ActivePosition from './ActivePosition';

interface ActivePositionsListProps {
    positions: any[];
}

export default function ActivePositionsList({ positions }: ActivePositionsListProps) {
    if (!positions || positions.length === 0) {
        return null; // Or show "No Active Positions" placeholders if desired, but user preferred hidden if 0
    }

    return (
        <div className="space-y-4 mb-6">
            <h3 className="text-lg font-bold text-gray-200 flex items-center gap-2">
                Active Positions ({positions.length})
            </h3>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {positions.map((pos, index) => (
                    <ActivePosition
                        key={pos.symbol || index}
                        symbol={pos.symbol}
                        side={pos.side}
                        size={pos.size}
                        entryPrice={pos.entry_price}
                        currentPrice={pos.mark_price || pos.entry_price} // Fallback if mark_price missing
                        leverage={pos.leverage}
                        pnl={pos.pnl}
                        pnlPercent={(pos.pnl / (pos.size / pos.leverage)) * 100} // Estimate PnL% using margin
                        duration="--" // Duration not currently passed from backend
                        isMock={false}
                    />
                ))}
            </div>
        </div>
    );
}
