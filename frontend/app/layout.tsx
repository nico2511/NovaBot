import './globals.css'
import type { Metadata } from 'next'
import { Inter } from 'next/font/google'
import { ThemeProvider } from '@/contexts/ThemeContext'

const inter = Inter({
    subsets: ['latin'],
    display: 'swap',  // Avoid FOIT (Flash of Invisible Text)
    preload: true,
    variable: '--font-inter'
})

export const metadata: Metadata = {
    title: {
        default: 'HyperLiquid AI Trader',
        template: '%s | HyperLiquid AI Trader'
    },
    description: 'Advanced algorithmic trading bot with AI-powered strategies for HyperLiquid DEX. Real-time market analysis, automated trading, and risk management.',
    keywords: ['trading bot', 'hyperliquid', 'AI trading', 'algorithmic trading', 'crypto', 'automated trading', 'DeFi'],
    robots: {
        index: true,
        follow: true,
    },
    openGraph: {
        type: 'website',
        locale: 'en_US',
        title: 'HyperLiquid AI Trader',
        description: 'Advanced algorithmic trading with AI-powered strategies',
        siteName: 'HyperLiquid AI Trader',
    },
    twitter: {
        card: 'summary_large_image',
        title: 'HyperLiquid AI Trader',
        description: 'Advanced algorithmic trading with AI-powered strategies',
    },
}

export default function RootLayout({
    children,
}: {
    children: React.ReactNode
}) {
    return (
        <html lang="en" className={inter.variable}>
            <body className={inter.className}>
                <ThemeProvider tier="Mercenary">
                    {children}
                </ThemeProvider>
            </body>
        </html>
    )
}
