'use client'

import React, { createContext, useContext, useMemo } from 'react'

type TierName = 'Goblin' | 'Mercenary' | 'Whale'

interface ThemeColors {
    primary: string
    secondary: string
    accent: string
    gradient: string
}

interface ThemeContextType {
    colors: ThemeColors
    tier: TierName
}

const ThemeContext = createContext<ThemeContextType | undefined>(undefined)

const TIER_THEMES: Record<TierName, ThemeColors> = {
    Goblin: {
        // NEBULA: Blue/Purple
        primary: '#3B82F6',      // Blue
        secondary: '#8B5CF6',    // Purple
        accent: '#6366F1',       // Indigo
        gradient: 'from-blue-500 to-purple-500'
    },
    Mercenary: {
        // PROTOSTAR: Silver/Gray
        primary: '#C0C0C0',      // Silver
        secondary: '#A8A8A8',    // Gray
        accent: '#9CA3AF',       // Cool Gray
        gradient: 'from-gray-300 to-gray-400'
    },
    Whale: {
        // SUPERNOVA: Gold/Fire
        primary: '#D4AF37',      // Gold
        secondary: '#FF6B35',    // Fire Orange
        accent: '#FFB627',       // Amber
        gradient: 'from-yellow-600 to-orange-500'
    }
}

export function ThemeProvider({
    children,
    tier = 'Goblin'
}: {
    children: React.ReactNode
    tier?: TierName
}) {
    const theme = useMemo(() => ({
        colors: TIER_THEMES[tier],
        tier
    }), [tier])

    return (
        <ThemeContext.Provider value={theme}>
            {children}
        </ThemeContext.Provider>
    )
}

export function useTheme() {
    const context = useContext(ThemeContext)
    if (!context) {
        throw new Error('useTheme must be used within ThemeProvider')
    }
    return context
}
