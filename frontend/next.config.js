/** @type {import('next').NextConfig} */
const nextConfig = {
    reactStrictMode: true,
    async rewrites() {
        return [
            {
                source: '/api/:path*',
                destination: 'http://localhost:8001/api/:path*' // Proxy to backend on port 8001
            }
        ]
    }
}

module.exports = nextConfig
