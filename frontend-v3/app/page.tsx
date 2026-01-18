'use client';

import StatusPill from '@/components/StatusPill';
import PnLCard from '@/components/PnLCard';
import ControlButtons from '@/components/ControlButtons';
import CopilotCard from '@/components/CopilotCard';
import ConfigPanel from '@/components/ConfigPanel';
import ActivePosition from '@/components/ActivePosition';
import { useBotStatus } from '@/hooks/useBotStatus';
import { useState } from 'react';
import { Settings, X } from 'lucide-react';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8001';

export default function Home() {
  const { data, error, isLoading, mutate } = useBotStatus();
  const hasConnectionError = !!error;
  const [showConfig, setShowConfig] = useState(false);

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
            {/* Status Pill */}
            <div className="flex justify-center">
              <StatusPill isRunning={data.is_running} />
            </div>

            {/* PnL Card */}
            <PnLCard
              dailyPnL={data.daily_pnl}
              activePositions={data.active_positions}
              lastUpdated={data.last_updated}
            />

            {/* Co-pilot Card (AI Reasoning) */}
            <CopilotCard />

            {/* Control Buttons */}
            <ControlButtons
              isRunning={data.is_running}
              onStatusChange={() => mutate()}
            />

            {/* Active Position Card (only shown if trade is active) */}
            {data.active_trade && (
              <ActivePosition
                symbol={data.active_trade.symbol}
                side={data.active_trade.side}
                pnl={data.active_trade.pnl}
                size={data.active_trade.size}
                entryPrice={data.active_trade.entry_price}
                currentPrice={data.active_trade.current_price}
              />
            )}

            {/* Additional Info */}
            <div className="text-center text-sm text-gray-500 mt-4">
              <div className="mt-1">
                Status: <span className={data.is_running ? 'text-green-500 font-bold' : 'text-red-500 font-bold'}>
                  {data.is_running ? 'RUNNING' : 'STOPPED'}
                </span>
              </div>
            </div>

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
                href="/logs"
                className="text-sm text-gray-500 hover:text-gray-300 transition-colors underline underline-offset-4 block"
              >
                View Full Logs →
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
                <ConfigPanel />
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
