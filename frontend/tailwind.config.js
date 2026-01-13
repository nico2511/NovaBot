/** @type {import('tailwindcss').Config} */
module.exports = {
    content: [
        './pages/**/*.{js,ts,jsx,tsx,mdx}',
        './components/**/*.{js,ts,jsx,tsx,mdx}',
        './app/**/*.{js,ts,jsx,tsx,mdx}',
    ],
    theme: {
        extend: {
            colors: {
                // Dark/Minimalist Palette
                primary: '#3b82f6',
                'primary-dark': '#2563eb',
                background: '#0B0E11',    // Deep dark (PRD requirement)
                surface: '#1A1D23',       // Dark surface
                'surface-light': '#2A2D35', // Lighter surface
                border: '#2A2D35',        // Subtle borders

                // Tier Colors (Subtle Gradients)
                nebula: {
                    from: '#4A5568',      // Gray
                    to: '#2D3748'
                },
                protostar: {
                    from: '#C0C0C0',      // Silver
                    to: '#A8A8A8'
                },
                supernova: {
                    from: '#D4AF37',      // Gold
                    to: '#B8960F'
                },

                // Status colors (kept for functionality)
                success: '#22c55e',
                warning: '#f97316',
                error: '#ef4444',
            },
        },
    },
    plugins: [],
}
