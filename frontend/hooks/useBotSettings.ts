import { useState, useEffect } from 'react'
import useSWR, { mutate } from 'swr'
import axios from 'axios'

const API_URL = ''

export interface Settings {
    asset: string
    execution_mode: string
    trading_enabled: boolean
    size_type: string
    size_value: number
    leverage: number
    max_positions: number
    daily_stop_loss: number
    scanner: {
        enabled: boolean
        interval: number
        min_score: number
        auto_switch: boolean
        gamification_enabled?: boolean
    }
}

const defaultSettings: Settings = {
    asset: 'BTC',
    execution_mode: 'Manual (Phantom)',
    trading_enabled: false,
    size_type: 'Fixed (USDC)',
    size_value: 100,
    leverage: 5,
    max_positions: 3,
    daily_stop_loss: 100,
    scanner: {
        enabled: false,
        interval: 15,
        min_score: 75,
        auto_switch: false,
        gamification_enabled: true
    }
}

export function useBotSettings() {
    const [settings, setSettings] = useState<Settings>(defaultSettings)
    const [isSaving, setIsSaving] = useState(false)
    const [isLoading, setIsLoading] = useState(true)

    // --- DATA FETCHING ---
    const { data: statusData } = useSWR(`${API_URL}/api/status`, async (url) => {
        const res = await axios.get(url)
        return res.data
    }, { refreshInterval: 2000 })

    const { data: serverSettings } = useSWR(`${API_URL}/api/settings`, async (url) => {
        const res = await axios.get(url)
        return res.data
    }, { refreshInterval: 2000 })

    // Tokens & Gamification (Exposed for components)
    const { data: tokenData } = useSWR(`${API_URL}/api/tokens`, async (url) => {
        const res = await axios.get(url)
        return res.data
    }, { revalidateOnFocus: false, dedupingInterval: 60000 })

    const { data: gamStatus } = useSWR(`${API_URL}/api/gamification_status`, async (url) => {
        const res = await axios.get(url)
        return res.data
    }, { refreshInterval: 5000 })

    // --- SYNC LOGIC ---
    useEffect(() => {
        if (serverSettings || statusData) {
            setSettings(prev => ({
                ...prev,
                ...serverSettings,
                // Prioritize active_symbol from status if available
                asset: statusData?.active_symbol || serverSettings?.asset || prev.asset,
                // Ensure correct types
                size_value: parseFloat(serverSettings?.size_value || prev.size_value),
                leverage: parseInt(serverSettings?.leverage || prev.leverage),
                max_positions: parseInt(serverSettings?.max_positions || prev.max_positions),
                daily_stop_loss: parseFloat(serverSettings?.daily_stop_loss || prev.daily_stop_loss),
                trading_enabled: statusData?.trading_enabled ?? serverSettings?.trading_enabled ?? prev.trading_enabled,
                scanner: {
                    ...prev.scanner,
                    ...(serverSettings?.scanner || {})
                }
            }))
            setIsLoading(false)
        }
    }, [serverSettings, statusData])

    // --- ACTIONS ---
    const updateSettings = (key: keyof Settings, value: any) => {
        setSettings(prev => ({ ...prev, [key]: value }))
    }

    const updateScannerSettings = (key: string, value: any) => {
        setSettings(prev => ({
            ...prev,
            scanner: {
                ...prev.scanner,
                [key]: value
            }
        }))
    }

    const saveSettings = async () => {
        setIsSaving(true)
        try {
            await axios.post(`${API_URL}/api/settings`, settings)
            await axios.post(`${API_URL}/api/symbol/switch`, { symbol: settings.asset })

            // Explicitly sync trading enabled status if it changed locally but wasn't synced
            if (statusData?.trading_enabled !== settings.trading_enabled) {
                const endpoint = settings.trading_enabled ? '/api/trading/enable' : '/api/trading/disable'
                await axios.post(`${API_URL}${endpoint}`)
            }

            mutate(`${API_URL}/api/settings`)
            mutate(`${API_URL}/api/status`)
            alert('✅ Settings saved successfully!')
        } catch (error) {
            console.error('Failed to save settings:', error)
            alert('❌ Failed to save settings')
        } finally {
            setIsSaving(false)
        }
    }

    const toggleEngine = async () => {
        try {
            const endpoint = statusData?.is_running ? '/api/engine/stop' : '/api/engine/start'
            await axios.post(`${API_URL}${endpoint}`)
            mutate(`${API_URL}/api/status`)
        } catch (error) {
            console.error('Failed to toggle engine:', error)
            alert('❌ Failed to toggle engine')
        }
    }

    const toggleGamification = async (enabled: boolean) => {
        // Optimistic update
        updateScannerSettings('gamification_enabled', enabled)
        try {
            await axios.post(`${API_URL}/api/toggle_gamification`, { enabled })
            mutate(`${API_URL}/api/gamification_status`)
        } catch (error) {
            console.error('Failed to toggle gamification:', error)
            // Revert
            updateScannerSettings('gamification_enabled', !enabled)
        }
    }

    return {
        settings,
        statusData,
        tokenData,
        gamStatus,
        isLoading,
        isSaving,
        updateSettings,
        updateScannerSettings,
        saveSettings,
        toggleEngine,
        toggleGamification
    }
}
