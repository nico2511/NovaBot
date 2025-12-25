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
                background: '#0f172a',
                surface: '#1e293b',
                'surface-light': '#334155',
                border: '#475569',
                success: '#22c55e',
                warning: '#f97316',
                error: '#ef4444',
            },
        },
    },
    plugins: [],
}
