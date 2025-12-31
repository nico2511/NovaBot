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
                primary: '#3b82f6',
                'primary-dark': '#2563eb',
                background: '#050505', // Nearly pure black
                surface: '#121212',    // Dark neutral gray (Material Dark)
                'surface-light': '#27272a', // Zinc-800
                border: '#3f3f46',     // Zinc-700
                success: '#22c55e',
                warning: '#f97316',
                error: '#ef4444',
            },
        },
    },
    plugins: [],
}
