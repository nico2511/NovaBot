import useSWR from 'swr';
import { BotStatus } from '../lib/api';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8001';

const fetcher = (url: string) => fetch(url).then((res) => {
    if (!res.ok) throw new Error('Failed to fetch');
    return res.json();
});

export function useBotStatus() {
    const { data, error, isLoading, mutate } = useSWR<BotStatus>(
        `${API_BASE_URL}/api/status`,
        fetcher,
        {
            refreshInterval: 1000, // Poll every 1 second
            revalidateOnFocus: true,
            dedupingInterval: 500,
        }
    );

    return {
        data,
        error,
        isLoading,
        mutate,
        isConnected: !error,
        isStopped: data ? !data.is_running : false,
    };
}
