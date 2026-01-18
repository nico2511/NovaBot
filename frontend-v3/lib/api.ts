// API Configuration
const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8001';

// Type Definitions
export interface BotStatus {
    is_running: boolean;
    trading_enabled: boolean;
    active_symbol: string;
    active_trade: any | null;
    daily_pnl: number;
    active_positions: number;
    last_updated: string | null;
}

export interface ApiResponse {
    status: string;
    message: string;
}

// API Client
export const api = {
    async getStatus(): Promise<BotStatus> {
        const response = await fetch(`${API_BASE_URL}/api/status`);
        if (!response.ok) {
            throw new Error('Failed to fetch status');
        }
        return response.json();
    },

    async stopEngine(): Promise<ApiResponse> {
        const response = await fetch(`${API_BASE_URL}/api/engine/stop`, {
            method: 'POST',
        });
        if (!response.ok) {
            throw new Error('Failed to stop engine');
        }
        return response.json();
    },

    async startEngine(): Promise<ApiResponse> {
        const response = await fetch(`${API_BASE_URL}/api/engine/start`, {
            method: 'POST',
        });
        if (!response.ok) {
            throw new Error('Failed to start engine');
        }
        return response.json();
    },

    async forceSync(): Promise<ApiResponse> {
        const response = await fetch(`${API_BASE_URL}/api/force_sync`, {
            method: 'POST',
        });
        if (!response.ok) {
            throw new Error('Failed to force sync');
        }
        return response.json();
    },

    async forceBreakEven(): Promise<ApiResponse> {
        const response = await fetch(`${API_BASE_URL}/api/force_breakeven`, {
            method: 'POST',
        });
        if (!response.ok) {
            throw new Error('Failed to force break even');
        }
        return response.json();
    },

    async closeTrade(): Promise<ApiResponse> {
        const response = await fetch(`${API_BASE_URL}/api/close_trade`, {
            method: 'POST',
        });
        if (!response.ok) {
            throw new Error('Failed to close trade');
        }
        return response.json();
    },

    async recalibrateStops(): Promise<ApiResponse> {
        const response = await fetch(`${API_BASE_URL}/api/recalibrate_stops`, {
            method: 'POST',
        });
        if (!response.ok) {
            throw new Error('Failed to recalibrate stops');
        }
        return response.json();
    },

    async getMeta(): Promise<Record<string, any>> {
        const response = await fetch(`${API_BASE_URL}/api/meta`);
        if (!response.ok) {
            throw new Error('Failed to fetch meta');
        }
        return response.json();
    },
};

// SWR Fetcher
export const fetcher = (url: string) => fetch(url).then((res) => res.json());
