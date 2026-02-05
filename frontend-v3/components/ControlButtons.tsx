'use client';

import { useState } from 'react';
import { Button } from '@/components/ui/button';
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
} from '@/components/ui/dialog';
import { api } from '@/lib/api';

interface ControlButtonsProps {
    isRunning: boolean;
    tradingEnabled: boolean;
    onStatusChange: () => void;
}

export default function ControlButtons({ isRunning, tradingEnabled, onStatusChange }: ControlButtonsProps) {
    const [showDialog, setShowDialog] = useState(false);
    const [isLoading, setIsLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const handleStop = async () => {
        setIsLoading(true);
        setError(null);
        try {
            await api.stopEngine();
            setShowDialog(false);
            onStatusChange(); // Trigger SWR revalidation
        } catch (err) {
            setError('Failed to stop trading. Please try again.');
            console.error('Stop error:', err);
        } finally {
            setIsLoading(false);
        }
    };

    const handleStart = async () => {
        setIsLoading(true);
        setError(null);
        try {
            await api.startEngine();
            onStatusChange(); // Trigger SWR revalidation
        } catch (err) {
            setError('Failed to start trading. Please try again.');
            console.error('Start error:', err);
        } finally {
            setIsLoading(false);
        }
    };

    const handlePanic = async () => {
        if (!confirm("🚨 ARE YOU SURE?\n\nThis will STOP the bot and MARKET CLOSE all open positions immediately.\nThis action cannot be undone.")) {
            return;
        }

        setIsLoading(true);
        setError(null);
        try {
            await api.panicClose();
            setShowDialog(false);
            onStatusChange();
        } catch (err) {
            setError('Failed to execute panic close. Login to exchange manually!');
            console.error('Panic error:', err);
        } finally {
            setIsLoading(false);
        }
    };

    return (
        <>
            <div className="flex justify-center">
                {tradingEnabled ? (
                    <Button
                        variant="outline"
                        size="lg"
                        onClick={() => setShowDialog(true)}
                        disabled={isLoading}
                        className="w-full max-w-xs font-semibold min-h-[48px] touch-target border-red-500 text-red-500 hover:bg-red-500/10 hover:text-red-400 transition-all duration-300"
                    >
                        {isLoading ? 'STOPPING...' : 'STOP TRADING'}
                    </Button>
                ) : (
                    <Button
                        variant="default"
                        size="lg"
                        onClick={handleStart}
                        disabled={isLoading}
                        className="w-full max-w-xs font-semibold bg-profit hover:bg-profit/90 text-black min-h-[48px] touch-target"
                    >
                        {isLoading ? 'STARTING...' : 'START TRADING'}
                    </Button>
                )}
            </div>

            {error && (
                <div className="text-center text-loss text-sm mt-2">
                    {error}
                </div>
            )}

            {/* Confirmation Dialog */}
            <Dialog open={showDialog} onOpenChange={setShowDialog}>
                <DialogContent className="bg-void border-loss/50">
                    <DialogHeader>
                        <DialogTitle className="text-loss text-xl">⚠️ Stop Trading?</DialogTitle>
                        <DialogDescription className="text-gray-300 text-base">
                            This will immediately halt the bot from opening new trades.
                            <br />
                            <br />
                            Existing positions will remain open. Are you sure you want to continue?
                        </DialogDescription>
                    </DialogHeader>
                    <DialogFooter className="gap-2 sm:justify-between flex-col sm:flex-row">
                        <div className="flex gap-2">
                            <Button
                                variant="outline"
                                onClick={() => setShowDialog(false)}
                                disabled={isLoading}
                                className="border-gray-600"
                            >
                                Cancel
                            </Button>
                            <Button
                                variant="destructive"
                                onClick={handleStop}
                                disabled={isLoading}
                            >
                                {isLoading ? 'Stopping...' : 'Stop Bot Only'}
                            </Button>
                        </div>

                        <Button
                            variant="destructive"
                            onClick={handlePanic}
                            disabled={isLoading}
                            className="bg-red-600 hover:bg-red-700 font-bold border border-red-400 w-full sm:w-auto mt-2 sm:mt-0"
                        >
                            🚨 Stop & Close All
                        </Button>
                    </DialogFooter>
                </DialogContent>
            </Dialog>
        </>
    );
}
