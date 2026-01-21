'use client';

import { useState, useEffect } from 'react';
import { api } from '@/lib/api';

interface Settings {
    notifications: {
        discord_webhook_alerts: string;
        discord_webhook_logs: string;
    };
    operations: {
        log_level: string;
        auto_start_trading: boolean;
        trading_timeframe: string;
    };
    risk_defaults: {
        max_positions: number;
        daily_stop_loss: number;
        bot_persona: string;
        risk_profile: string;
        default_leverage: number;
    };
    ai_config: {
        model_name: string;
        provider: string;
        call_cooldown: number;
        conf_threshold_high: number;
        conf_threshold_medium: number;
        conf_threshold_low: number;
    };
}

type SettingsSection = keyof Settings;

export default function AdvancedSettings() {
    const [settings, setSettings] = useState<Settings | null>(null);
    const [activeTab, setActiveTab] = useState<SettingsSection>('operations');
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);

    useEffect(() => {
        loadSettings();
    }, []);

    const loadSettings = async () => {
        try {
            const data = await api.getAllSettings();
            setSettings(data as Settings);
        } catch (error) {
            console.error('Failed to load settings:', error);
        } finally {
            setLoading(false);
        }
    };

    const handleSave = async (section: SettingsSection) => {
        if (!settings) return;

        setSaving(true);
        try {
            await api.updateSettings(section, settings[section]);
            alert(`✅ ${section} settings saved successfully!`);
        } catch (error) {
            alert(`❌ Failed to save ${section} settings`);
            console.error(error);
        } finally {
            setSaving(false);
        }
    };

    const updateField = (section: SettingsSection, field: string, value: any) => {
        if (!settings) return;
        setSettings({
            ...settings,
            [section]: {
                ...settings[section],
                [field]: value,
            },
        });
    };

    if (loading) return <div className="text-gray-400">Loading settings...</div>;
    if (!settings) return <div className="text-red-400">Failed to load settings</div>;

    const tabs: { key: SettingsSection; label: string; icon: string }[] = [
        { key: 'operations', label: 'Operations', icon: '⚙️' },
        { key: 'risk_defaults', label: 'Risk Defaults', icon: '🛡️' },
        { key: 'ai_config', label: 'AI Config', icon: '🤖' },
        { key: 'notifications', label: 'Notifications', icon: '📢' },
    ];

    return (
        <div className="bg-[#111] border border-[#333] rounded-2xl p-6 mt-6">
            <h2 className="text-xl font-bold text-gray-200 mb-4">⚙️ Advanced Settings</h2>

            {/* Tabs */}
            <div className="flex gap-2 mb-6 border-b border-[#333]">
                {tabs.map((tab) => (
                    <button
                        key={tab.key}
                        onClick={() => setActiveTab(tab.key)}
                        className={`px-4 py-2 font-medium transition-colors ${activeTab === tab.key
                            ? 'text-emerald-400 border-b-2 border-emerald-400'
                            : 'text-gray-500 hover:text-gray-300'
                            }`}
                    >
                        {tab.icon} {tab.label}
                    </button>
                ))}
            </div>

            {/* Tab Content */}
            <div className="space-y-4">
                {activeTab === 'operations' && (
                    <>
                        <div>
                            <label className="block text-sm text-gray-400 mb-1">Log Level</label>
                            <select
                                value={settings.operations.log_level}
                                onChange={(e) => updateField('operations', 'log_level', e.target.value)}
                                className="w-full bg-[#1a1a1a] border border-[#333] rounded px-3 py-2 text-gray-200"
                            >
                                <option value="DEBUG">DEBUG</option>
                                <option value="INFO">INFO</option>
                                <option value="WARNING">WARNING</option>
                                <option value="ERROR">ERROR</option>
                            </select>
                        </div>
                        <div>
                            <label className="flex items-center gap-2 text-sm text-gray-400">
                                <input
                                    type="checkbox"
                                    checked={settings.operations.auto_start_trading}
                                    onChange={(e) => updateField('operations', 'auto_start_trading', e.target.checked)}
                                    className="rounded"
                                />
                                Auto-start Trading on Bot Launch
                            </label>
                        </div>
                        <div>
                            <label className="block text-sm text-gray-400 mb-1">Trading Timeframe</label>
                            <select
                                value={settings.operations.trading_timeframe}
                                onChange={(e) => updateField('operations', 'trading_timeframe', e.target.value)}
                                className="w-full bg-[#1a1a1a] border border-[#333] rounded px-3 py-2 text-gray-200"
                            >
                                <option value="1m">1 Minute</option>
                                <option value="5m">5 Minutes</option>
                                <option value="15m">15 Minutes</option>
                                <option value="1h">1 Hour</option>
                            </select>
                        </div>
                    </>
                )}

                {activeTab === 'risk_defaults' && (
                    <>
                        <div>
                            <label className="block text-sm text-gray-400 mb-1">Max Positions</label>
                            <input
                                type="number"
                                value={settings.risk_defaults.max_positions}
                                onChange={(e) => updateField('risk_defaults', 'max_positions', parseInt(e.target.value))}
                                className="w-full bg-[#1a1a1a] border border-[#333] rounded px-3 py-2 text-gray-200"
                                min="1"
                                max="10"
                            />
                        </div>
                        <div>
                            <label className="block text-sm text-gray-400 mb-1">Daily Stop Loss ($)</label>
                            <input
                                type="number"
                                value={settings.risk_defaults.daily_stop_loss}
                                onChange={(e) => updateField('risk_defaults', 'daily_stop_loss', parseFloat(e.target.value))}
                                className="w-full bg-[#1a1a1a] border border-[#333] rounded px-3 py-2 text-gray-200"
                                step="10"
                            />
                        </div>
                        <div>
                            <label className="block text-sm text-gray-400 mb-1">Bot Persona</label>
                            <select
                                value={settings.risk_defaults.bot_persona}
                                onChange={(e) => updateField('risk_defaults', 'bot_persona', e.target.value)}
                                className="w-full bg-[#1a1a1a] border border-[#333] rounded px-3 py-2 text-gray-200"
                            >
                                <option value="Conservative Scalper">Conservative Scalper</option>
                                <option value="Aggressive Day Trader">Aggressive Day Trader</option>
                                <option value="Sniper">Sniper</option>
                            </select>
                            <p className="text-xs text-gray-500 mt-1">
                                {settings.risk_defaults.bot_persona === 'Conservative Scalper' && '🛡️ Capital preservation, tight stops, 3+ confirmations'}
                                {settings.risk_defaults.bot_persona === 'Aggressive Day Trader' && '⚡ Momentum plays, wider stops, 2+ confirmations'}
                                {settings.risk_defaults.bot_persona === 'Sniper' && '🎯 Perfect setups only, 4+ confirmations, low frequency'}
                            </p>
                        </div>
                        <div>
                            <label className="block text-sm text-gray-400 mb-1">Risk Profile</label>
                            <select
                                value={settings.risk_defaults.risk_profile}
                                onChange={(e) => updateField('risk_defaults', 'risk_profile', e.target.value)}
                                className="w-full bg-[#1a1a1a] border border-[#333] rounded px-3 py-2 text-gray-200"
                            >
                                <option value="Capital Preservation First">Capital Preservation First</option>
                                <option value="Balanced Growth">Balanced Growth</option>
                                <option value="High Volatility Hunter">High Volatility Hunter</option>
                            </select>
                            <p className="text-xs text-gray-500 mt-1">
                                {settings.risk_defaults.risk_profile === 'Capital Preservation First' && '🛡️ 1-2% risk, 2:1 R:R, max 3x leverage'}
                                {settings.risk_defaults.risk_profile === 'Balanced Growth' && '⚖️ 2-5% risk, 1.5:1 R:R, max 5x leverage'}
                                {settings.risk_defaults.risk_profile === 'High Volatility Hunter' && '🔥 5-10% risk, 1:1 R:R, max 10x leverage'}
                            </p>
                        </div>
                        <div>
                            <label className="block text-sm text-gray-400 mb-1">Default Leverage</label>
                            <select
                                value={settings.risk_defaults.default_leverage}
                                onChange={(e) => updateField('risk_defaults', 'default_leverage', parseInt(e.target.value))}
                                className="w-full bg-[#1a1a1a] border border-[#333] rounded px-3 py-2 text-gray-200"
                            >
                                {[1, 2, 3, 5, 10, 20, 50].map(lev => (
                                    <option key={lev} value={lev}>{lev}x</option>
                                ))}
                            </select>
                        </div>
                    </>
                )}

                {activeTab === 'ai_config' && (
                    <>
                        <div>
                            <label className="block text-sm text-gray-400 mb-1">AI Model</label>
                            <input
                                type="text"
                                value={settings.ai_config.model_name}
                                onChange={(e) => updateField('ai_config', 'model_name', e.target.value)}
                                className="w-full bg-[#1a1a1a] border border-[#333] rounded px-3 py-2 text-gray-200"
                                placeholder="deepseek/deepseek-v3.2"
                            />
                            <p className="text-xs text-gray-500 mt-1">OpenRouter model identifier</p>
                        </div>
                        <div>
                            <label className="block text-sm text-gray-400 mb-1">Call Cooldown (seconds)</label>
                            <input
                                type="number"
                                value={settings.ai_config.call_cooldown}
                                onChange={(e) => updateField('ai_config', 'call_cooldown', parseInt(e.target.value))}
                                className="w-full bg-[#1a1a1a] border border-[#333] rounded px-3 py-2 text-gray-200"
                                min="0"
                            />
                            <p className="text-xs text-gray-500 mt-1">⏱️ Minimum delay between AI API calls to avoid rate limits</p>
                        </div>
                        <div className="grid grid-cols-3 gap-4">
                            <div>
                                <label className="block text-sm text-gray-400 mb-1">High Risk Threshold (%)</label>
                                <input
                                    type="number"
                                    value={settings.ai_config.conf_threshold_high}
                                    onChange={(e) => updateField('ai_config', 'conf_threshold_high', parseInt(e.target.value))}
                                    className="w-full bg-[#1a1a1a] border border-[#333] rounded px-3 py-2 text-gray-200"
                                    min="0"
                                    max="101"
                                />
                            </div>
                            <div>
                                <label className="block text-sm text-gray-400 mb-1">Medium Risk Threshold (%)</label>
                                <input
                                    type="number"
                                    value={settings.ai_config.conf_threshold_medium}
                                    onChange={(e) => updateField('ai_config', 'conf_threshold_medium', parseInt(e.target.value))}
                                    className="w-full bg-[#1a1a1a] border border-[#333] rounded px-3 py-2 text-gray-200"
                                    min="0"
                                    max="100"
                                />
                            </div>
                            <div>
                                <label className="block text-sm text-gray-400 mb-1">Low Risk Threshold (%)</label>
                                <input
                                    type="number"
                                    value={settings.ai_config.conf_threshold_low}
                                    onChange={(e) => updateField('ai_config', 'conf_threshold_low', parseInt(e.target.value))}
                                    className="w-full bg-[#1a1a1a] border border-[#333] rounded px-3 py-2 text-gray-200"
                                    min="0"
                                    max="101"
                                />
                            </div>
                        </div>
                    </>
                )}

                {activeTab === 'notifications' && (
                    <>
                        <div>
                            <label className="block text-sm text-gray-400 mb-1">Discord Webhook (Alerts)</label>
                            <input
                                type="text"
                                value={settings.notifications.discord_webhook_alerts}
                                onChange={(e) => updateField('notifications', 'discord_webhook_alerts', e.target.value)}
                                className="w-full bg-[#1a1a1a] border border-[#333] rounded px-3 py-2 text-gray-200 font-mono text-xs"
                                placeholder="https://discord.com/api/webhooks/..."
                            />
                        </div>
                        <div>
                            <label className="block text-sm text-gray-400 mb-1">Discord Webhook (Logs)</label>
                            <input
                                type="text"
                                value={settings.notifications.discord_webhook_logs}
                                onChange={(e) => updateField('notifications', 'discord_webhook_logs', e.target.value)}
                                className="w-full bg-[#1a1a1a] border border-[#333] rounded px-3 py-2 text-gray-200 font-mono text-xs"
                                placeholder="https://discord.com/api/webhooks/..."
                            />
                        </div>
                    </>
                )}

                {/* Save Button */}
                <button
                    onClick={() => handleSave(activeTab)}
                    disabled={saving}
                    className="w-full bg-emerald-600 hover:bg-emerald-700 disabled:bg-gray-600 text-white font-medium py-2 px-4 rounded transition-colors"
                >
                    {saving ? 'Saving...' : `💾 Save ${tabs.find(t => t.key === activeTab)?.label}`}
                </button>
            </div>
        </div >
    );
}
