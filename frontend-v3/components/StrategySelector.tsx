'use client';

import React, { useState, useEffect } from 'react';
import useSWR, { mutate } from 'swr';
import { api, Strategy, fetcher } from '../lib/api';
import { Settings, Check, ChevronDown, Loader2, Info } from 'lucide-react';
import { cn } from '../lib/utils';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8001';

export function StrategySelector() {
    const { data: strategies, error, isLoading } = useSWR<Strategy[]>(`${API_BASE_URL}/api/config/strategy-list`, fetcher);
    const [isChanging, setIsChanging] = useState(false);
    const [isOpen, setIsOpen] = useState(false);

    const activeStrategies = strategies?.filter(s => s.enabled) || [];

    const handleSelect = async (id: string) => {
        // Toggle logic (Backend handles the toggle now)
        setIsChanging(true);
        try {
            await api.selectStrategy(id);
            await mutate(`${API_BASE_URL}/api/config/strategy-list`);
            // Don't close logic so user can select multiple
        } catch (err) {
            console.error('Failed to change strategy:', err);
        } finally {
            setIsChanging(false);
        }
    };

    if (error) return <div className="text-red-400 text-xs p-2">Failed to load strategies</div>;
    if (isLoading && !strategies) return <div className="h-10 w-full animate-pulse bg-neutral-900 rounded-lg" />;

    return (
        <div className="relative w-full mb-6">
            <label className="text-[10px] uppercase tracking-widest text-neutral-500 font-bold mb-2 block">
                Active Strategy
            </label>

            <button
                onClick={() => setIsOpen(!isOpen)}
                disabled={isChanging}
                className={cn(
                    "w-full flex items-center justify-between px-4 py-3 bg-neutral-950 border border-neutral-800 rounded-xl transition-all hover:bg-neutral-900 hover:border-neutral-700",
                    isOpen && "border-blue-500/50 ring-1 ring-blue-500/20"
                )}
            >
                <div className="flex items-center gap-3">
                    <div className="p-2 bg-blue-500/10 rounded-lg">
                        <Settings className="w-4 h-4 text-blue-400" />
                    </div>
                    <div className="text-left">
                        <div className="text-sm font-medium text-neutral-200">
                            {activeStrategies.length === 0 && 'Select Strategy'}
                            {activeStrategies.length === 1 && activeStrategies[0].name}
                            {activeStrategies.length > 1 && `Multiple Active (${activeStrategies.length})`}
                        </div>
                        <div className="text-[10px] text-neutral-500 uppercase">
                            {activeStrategies.length > 0 ? (
                                activeStrategies.length === 1 ? activeStrategies[0].type : "Multi-Strategy Mode"
                            ) : (
                                "No Strategy"
                            )}
                        </div>
                    </div>
                </div>
                {isChanging ? (
                    <Loader2 className="w-4 h-4 text-neutral-500 animate-spin" />
                ) : (
                    <ChevronDown className={cn("w-4 h-4 text-neutral-500 transition-transform", isOpen && "rotate-180")} />
                )}
            </button>

            {isOpen && (
                <>
                    <div
                        className="fixed inset-0 z-10"
                        onClick={() => setIsOpen(false)}
                    />
                    <div className="absolute top-full left-0 w-full mt-2 bg-neutral-950 border border-neutral-800 rounded-xl shadow-2xl z-20 overflow-hidden animate-in fade-in slide-in-from-top-2 duration-200">
                        <div className="p-2 max-h-[300px] overflow-y-auto">
                            {strategies?.map((strategy) => (
                                <button
                                    key={strategy.id}
                                    onClick={() => handleSelect(strategy.id)}
                                    className={cn(
                                        "w-full flex items-start gap-3 p-3 rounded-lg transition-colors text-left",
                                        strategy.enabled
                                            ? "bg-blue-500/10"
                                            : "hover:bg-neutral-900"
                                    )}
                                >
                                    <div className="mt-1">
                                        <div className={cn(
                                            "w-4 h-4 rounded border flex items-center justify-center transition-colors",
                                            strategy.enabled
                                                ? "bg-blue-500 border-blue-500"
                                                : "border-neutral-600 group-hover:border-neutral-500"
                                        )}>
                                            {strategy.enabled && <Check className="w-3 h-3 text-white" />}
                                        </div>
                                    </div>
                                    <div className="flex-1">
                                        <div className="flex items-center justify-between">
                                            <span className={cn(
                                                "text-sm font-medium",
                                                strategy.enabled ? "text-blue-400" : "text-neutral-300"
                                            )}>
                                                {strategy.name}
                                            </span>
                                            <span className="text-[9px] px-1.5 py-0.5 rounded bg-neutral-800 text-neutral-400 uppercase">
                                                {strategy.type}
                                            </span>
                                        </div>
                                        {strategy.description && (
                                            <p className="text-xs text-neutral-500 mt-1 line-clamp-2">
                                                {strategy.description}
                                            </p>
                                        )}
                                    </div>
                                </button>
                            ))}
                        </div>
                        <div className="bg-neutral-900/50 p-2 border-t border-neutral-800 flex items-center gap-2">
                            <Info className="w-3 h-3 text-neutral-500" />
                            <span className="text-[10px] text-neutral-500">
                                You can select multiple strategies.
                            </span>
                        </div>
                    </div>
                </>
            )}
        </div>
    );
}
