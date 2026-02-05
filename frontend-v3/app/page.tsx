'use client';

import StatusPill from '@/components/StatusPill';
import PnLCard from '@/components/PnLCard';
import ControlButtons from '@/components/ControlButtons';
import CopilotCard from '@/components/CopilotCard';
import PositionCopilot from '@/components/PositionCopilot';
import ConfigPanel from '@/components/ConfigPanel';
import ActivePosition from '@/components/ActivePosition';
import ActivePositionsList from '@/components/ActivePositionsList';

import NotificationLog from '@/components/NotificationLog';
import HealthMetrics from '@/components/HealthMetrics';
import MarketAnalysis from '@/components/MarketAnalysis';
import PerformanceChart from '@/components/PerformanceChart';
import { PriceChart } from '@/components/PriceChart';
import { useBotStatus } from '@/hooks/useBotStatus';
import { useState } from 'react';
import { Settings, X } from 'lucide-react';
import AdvancedSettings from '@/components/AdvancedSettings';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8001';

export default function Home() {
  const { data, error, isLoading, mutate } = useBotStatus();
  const hasConnectionError = !!error;
  const [showConfig, setShowConfig] = useState(false);

  // Calculate Live Daily PnL (Realized + Unrealized)
  const calculateLivePnL = () => {
    if (!data) return 0;

    // Realized PnL (from backend)
    const realized = data.daily_pnl || 0;

    // Unrealized PnL (from open positions)
    const unrealized = (data.open_positions || []).reduce((total: number, pos: any) => {
      let pnl = 0;
      if (typeof pos.pnl === 'number') pnl = pos.pnl;
      else if (typeof pos.unrealized_pnl === 'number') pnl = pos.unrealized_pnl;
      else if (typeof pos.pnl === 'string') pnl = parseFloat(pos.pnl);
      else if (typeof pos.unrealized_pnl === 'string') pnl = parseFloat(pos.unrealized_pnl);

      return total + (isNaN(pnl) ? 0 : pnl);
    }, 0);

    return realized + unrealized;
  };

  const liveDailyPnL = calculateLivePnL();

  return (
    <main className="flex min-h-screen flex-col items-center justify-center p-4 md:p-8 bg-[#0a0a0a] text-white">
      <div className="w-full max-w-2xl space-y-6">
        {/* Header */}
        <div className="text-center mb-8">
          <h1 className="text-3xl md:text-4xl font-bold text-white mb-2">
            Novabot
          </h1>
          <p className="text-gray-400">Your Serenity Machine</p>
        </div>

        {/* Loading State */}
        {isLoading && !data && (
          <div className="text-center text-gray-400 py-12">
            <div className="animate-pulse">Loading dashboard...</div>
          </div>
        )}

        {/* Dashboard Content */}
        {data && (
          <>
            {/* Active Token Badge */}
            <div className="flex justify-center mb-4">
              <div className="bg-gradient-to-r from-blue-500/10 to-purple-500/10 border border-blue-500/30 rounded-full px-6 py-2 flex items-center gap-2">
                <div className="w-2 h-2 bg-blue-400 rounded-full animate-pulse"></div>
                <span className="text-sm font-medium text-gray-300">Active Token:</span>
                <span className="text-lg font-bold text-white">{data.active_symbol || 'BTC'}</span>
              </div>
            </div>

            {/* Status Pill */}
            <div className="flex justify-center">
              <StatusPill isRunning={data.is_running} />
            </div>

            {/* Position Copilot (New) */}
            <div className="w-full">
              <PositionCopilot />
            </div>

            {/* PnL Card - LIVE Update */}
            <PnLCard
              dailyPnL={liveDailyPnL}
              activePositions={data.active_positions}
              lastUpdated={data.last_updated}
            />

            {/* Active Position Cards (Dynamic List) */}
            <ActivePositionsList positions={data.open_positions || []} />

            {/* Performance Chart */}
            <PerformanceChart />

            {/* Health Metrics */}
            <HealthMetrics
              marginUsage={data.margin_usage || 0}
              winRate={data.win_rate || 0}
              maxDrawdown={data.max_drawdown || 0}
            />



            {/* Co-pilot Card (AI Reasoning) */}
            <CopilotCard />

            {/* Control Buttons */}
            <ControlButtons
              isRunning={data.is_running}
              tradingEnabled={data.trading_enabled}
              onStatusChange={() => mutate()}
            />

            {/* Price Chart - Disabled per user request */}
            {/* <div className="w-full">
              <PriceChart symbol={data.active_symbol || "BTC"} />
            </div> */}



            {/* Notification Logs */}
            <NotificationLog logs={data.logs || []} />

            {/* Settings Toggle */}
            <div className="text-center pt-4 space-y-2">
              <button
                onClick={() => setShowConfig(!showConfig)}
                className="text-sm text-gray-500 hover:text-gray-300 transition-colors flex items-center gap-2 mx-auto"
              >
                <Settings className="w-4 h-4" />
                {showConfig ? 'Hide Settings' : 'Show Settings'}
              </button>
              <a
                href="/activity-logs"
                className="text-sm text-gray-500 hover:text-gray-300 transition-colors underline underline-offset-4 block"
              >
                View Full Logs →
              </a>
              <a
                href="/sentiment-history"
                className="text-sm text-gray-500 hover:text-gray-300 transition-colors underline underline-offset-4 block"
              >
                Sentiment History →
              </a>
              <a
                href="/signal-analysis"
                className="text-sm text-gray-500 hover:text-gray-300 transition-colors underline underline-offset-4 block"
              >
                Signal Analysis →
              </a>
              <a
                href="/strategies"
                className="text-sm text-blue-500 hover:text-blue-400 transition-colors underline underline-offset-4 block font-bold"
              >
                Strategy Monitor (Live) →
              </a>
            </div>

            {/* Config Panel (Collapsible) */}
            {showConfig && (
              <div className="bg-neutral-900 border border-neutral-800 rounded-lg p-4">
                <div className="flex items-center justify-between mb-4">
                  <h3 className="font-bold">Settings</h3>
                  <button onClick={() => setShowConfig(false)} className="text-gray-500 hover:text-white">
                    <X className="w-5 h-5" />
                  </button>
                </div>
                <ConfigPanel currentSymbol={data.active_symbol} />
                <AdvancedSettings />
              </div>
            )}
          </>
        )}

        {/* Error State (No Connection) */}
        {hasConnectionError && !data && (
          <div className="text-center py-12">
            <div className="text-loss text-lg mb-2">Unable to connect to bot</div>
            <div className="text-gray-500 text-sm">
              Make sure the backend is running at {API_BASE_URL}
            </div>
          </div>
        )}
      </div>
    </main>
  );
}
