'use client';

import { useState, useEffect } from 'react';
import useSWR, { mutate } from 'swr';
import { Save, RefreshCw } from 'lucide-react';
import { StrategySelector } from './StrategySelector';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8001';

interface ScannerSettings {
    enabled: boolean;
    interval: number;
    min_score: number;
    auto_switch: boolean;
    gamification_enabled: boolean;
    max_funding_long: number;
    min_funding_short: number;
    funding_filter_enabled: boolean;
}

interface GlobalSettings {
    max_positions: number;
    daily_stop_loss: number;
    trading_timeframe: string;
    default_leverage: number;
    default_margin_type: string;
    cooldown_minutes: number;
    bot_persona: string;
    risk_profile: string;
}

interface BotStatus {
    active_symbol: string;
    // other status properties if any
}

const fetcher = (url: string) => fetch(url).then(res => res.json());

// Fallback tokens if API fails
const FALLBACK_TOKENS = ['BTC', 'ETH', 'SOL', 'SUI', 'DOGE', 'AVAX'];

const PERSONAS = ['Conservative Scalper', 'Aggressive Day Trader', 'Sniper'];
const RISK_PROFILES = ['Capital Preservation First', 'Balanced Growth', 'High Volatility Hunter'];
const TIMEFRAMES = ['15m', '1h', '4h', '1d'];
const LEVERAGES = [1, 2, 3, 5, 10, 20];

interface ConfigPanelProps {
    currentSymbol?: string;
}

export default function ConfigPanel({ currentSymbol }: ConfigPanelProps) {
    const { data: scannerSettings, error: scannerError } = useSWR<ScannerSettings>(
        `${API_BASE_URL}/api/settings/scanner`, fetcher
    );

    // Determine active symbol: prop > API status > local state
    const { data: status } = useSWR<BotStatus>(`${API_BASE_URL}/api/status`, fetcher);

    const [activeSymbol, setActiveSymbol] = useState(currentSymbol || '');
    const [scanner, setScanner] = useState<ScannerSettings | null>(null);
    const [saving, setSaving] = useState(false);
    const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

    // Dynamic Token List from /api/meta (universe array)
    const { data: meta } = useSWR<{ universe?: Array<{ name: string, isDelisted?: boolean }> }>(`${API_BASE_URL}/api/meta`, fetcher, { revalidateOnFocus: false });

    // Extract active (non-delisted) token names from universe
    const baseTokens = meta?.universe
        ? meta.universe
            .filter(t => !t.isDelisted)
            .map(t => t.name)
            .sort()
        : FALLBACK_TOKENS;

    // Ensure activeSymbol is always in the list
    const availableTokens = (activeSymbol && !baseTokens.includes(activeSymbol))
        ? [activeSymbol, ...baseTokens]
        : baseTokens;


    // Sync with parent prop if provided, otherwise fallback to internal status
    useEffect(() => {
        if (currentSymbol) {
            setActiveSymbol(currentSymbol);
        } else if (status?.active_symbol) {
            setActiveSymbol(status.active_symbol);
        }
    }, [currentSymbol, status]);

    useEffect(() => {
        if (scannerSettings) setScanner(scannerSettings);
    }, [scannerSettings]);

    const handleSave = async () => {
        setSaving(true);
        setMessage(null);

        try {
            // Save scanner settings
            if (scanner) {
                const res = await fetch(`${API_BASE_URL}/api/settings/scanner`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(scanner),
                });
                if (!res.ok) throw new Error('Failed to save scanner settings');
            }

            // Change active symbol if modified
            if (status?.active_symbol !== activeSymbol) {
                const res = await fetch(`${API_BASE_URL}/api/switch_symbol`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ symbol: activeSymbol }),
                });
                if (!res.ok) throw new Error('Failed to change symbol');
            }

            setMessage({ type: 'success', text: 'Settings saved successfully!' });
            mutate(`${API_BASE_URL}/api/status`);
            mutate(`${API_BASE_URL}/api/settings/scanner`);
        } catch (err: any) {
            setMessage({ type: 'error', text: err.message || 'Failed to save' });
        } finally {
            setSaving(false);
        }
    };

    if (!scanner) {
        return <div className="text-gray-500 p-4">Loading settings...</div>;
    }

    return (
        <div className="space-y-6">
            <StrategySelector />

            {/* Message */}
            {message && (
                <div className={`p-3 rounded text-sm ${message.type === 'success' ? 'bg-green-900/30 text-green-400' : 'bg-red-900/30 text-red-400'
                    }`}>
                    {message.text}
                </div>
            )}

            {/* Active Token */}
            <div className="bg-neutral-900 border border-neutral-800 rounded-lg p-4">
                <h3 className="text-sm text-gray-400 mb-3">Active Token</h3>
                <select
                    className="w-full bg-neutral-950 border border-neutral-800 rounded p-2 text-white"
                    value={activeSymbol}
                    onChange={(e) => setActiveSymbol(e.target.value)}
                >
                    {availableTokens.map(token => (
                        <option key={token} value={token}>{token}</option>
                    ))}
                </select>
            </div>

            {/* Scanner Settings */}
            <div className="bg-neutral-900 border border-neutral-800 rounded-lg p-4">
                <h3 className="text-sm text-gray-400 mb-3">Scanner</h3>
                <div className="space-y-3">
                    <label className="flex items-center justify-between">
                        <span>Scanner Enabled</span>
                        <input
                            type="checkbox"
                            checked={scanner.enabled}
                            onChange={(e) => setScanner({ ...scanner, enabled: e.target.checked })}
                            className="w-5 h-5 rounded"
                        />
                    </label>
                    <label className="flex items-center justify-between">
                        <span>Gamification</span>
                        <input
                            type="checkbox"
                            checked={scanner.gamification_enabled}
                            onChange={(e) => setScanner({ ...scanner, gamification_enabled: e.target.checked })}
                            className="w-5 h-5 rounded"
                        />
                    </label>
                    <label className="flex items-center justify-between">
                        <span>Auto Switch</span>
                        <input
                            type="checkbox"
                            checked={scanner.auto_switch}
                            onChange={(e) => setScanner({ ...scanner, auto_switch: e.target.checked })}
                            className="w-5 h-5 rounded"
                        />
                    </label>
                    <label className="flex flex-col gap-1">
                        <span className="text-sm">Min Score: {scanner.min_score}</span>
                        <input
                            type="range"
                            min="0"
                            max="100"
                            value={scanner.min_score}
                            onChange={(e) => setScanner({ ...scanner, min_score: parseInt(e.target.value) })}
                            className="w-full"
                        />
                    </label>

                    {/* Funding Rate Filter */}
                    <div className="border-t border-neutral-800 pt-3 mt-3">
                        <label className="flex items-center justify-between mb-3">
                            <span>Funding Filter</span>
                            <input
                                type="checkbox"
                                checked={scanner.funding_filter_enabled}
                                onChange={(e) => setScanner({ ...scanner, funding_filter_enabled: e.target.checked })}
                                className="w-5 h-5 rounded"
                            />
                        </label>

                        {scanner.funding_filter_enabled && (
                            <div className="space-y-3 pl-4 border-l-2 border-neutral-700">
                                <label className="flex flex-col gap-1">
                                    <span className="text-xs text-gray-400">Max Funding (Long): {(scanner.max_funding_long * 100).toFixed(3)}%</span>
                                    <input
                                        type="range"
                                        min="0.0001"
                                        max="0.005"
                                        step="0.0001"
                                        value={scanner.max_funding_long}
                                        onChange={(e) => setScanner({ ...scanner, max_funding_long: parseFloat(e.target.value) })}
                                        className="w-full"
                                    />
                                    <span className="text-xs text-gray-500">Reject longs when funding &gt; this threshold</span>
                                </label>

                                <label className="flex flex-col gap-1">
                                    <span className="text-xs text-gray-400">Min Funding (Short): {(scanner.min_funding_short * 100).toFixed(3)}%</span>
                                    <input
                                        type="range"
                                        min="-0.005"
                                        max="-0.0001"
                                        step="0.0001"
                                        value={scanner.min_funding_short}
                                        onChange={(e) => setScanner({ ...scanner, min_funding_short: parseFloat(e.target.value) })}
                                        className="w-full"
                                    />
                                    <span className="text-xs text-gray-500">Reject shorts when funding &lt; this threshold</span>
                                </label>
                            </div>
                        )}
                    </div>
                </div>
            </div>


            {/* Save Button */}
            <button
                onClick={handleSave}
                disabled={saving}
                className="w-full bg-blue-600 hover:bg-blue-700 disabled:bg-blue-800 text-white font-bold py-3 rounded flex items-center justify-center gap-2"
            >
                {saving ? <RefreshCw className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
                {saving ? 'Saving...' : 'Save Settings'}
            </button>
        </div>
    );
}
