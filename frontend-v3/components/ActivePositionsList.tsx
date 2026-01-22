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
                {positions.map((pos, index) => {
                    const safeFloat = (val: any) => {
                        if (typeof val === 'number') return val;
                        if (typeof val === 'string') return parseFloat(val.replace(',', '.'));
                        return 0;
                    };

                    const entryPrice = safeFloat(pos.entry_price || pos.entryPx);
                    const sizeQuantity = safeFloat(pos.size || pos.szi);
                    const leverage = safeFloat(pos.leverage || 1) || 1;
                    const pnl = safeFloat(pos.pnl || pos.unrealized_pnl);

                    // Correct Margin Calculation: (Entry * Size) / Leverage
                    const notionalValue = entryPrice * sizeQuantity;
                    const margin = notionalValue / leverage;

                    // Prevention against "Dust" positions causing ROI explosion (e.g. +6000% on $0.00)
                    // If notional value is < $1, we consider it dust and zero out the ROI display to avoid confusion
                    const isDust = notionalValue < 1.0;
                    const pnlPercent = (!isDust && margin > 0.01) ? (pnl / margin) * 100 : 0;

                    return (
                        <ActivePosition
                            key={pos.symbol || index}
                            symbol={pos.symbol}
                            side={pos.side}
                            size={notionalValue} // Display as USD Notional
                            entryPrice={entryPrice}
                            currentPrice={pos.mark_price || pos.entry_price}
                            leverage={leverage}
                            pnl={pnl}
                            pnlPercent={pnlPercent}
                            duration={pos.duration || "--"}
                            isMock={false}
                        />
                    );
                })}
            </div>
        </div>
    );
}
