/** @type {import('next').NextConfig} */
const nextConfig = {
    reactStrictMode: true,
    async rewrites() {
        return [
            {
                source: '/api/:path*',
                destination: 'http://127.0.0.1:8001/api/:path*' // Proxy to backend on port 8001 (IPv4)
            }
        ]
    }
}

module.exports = nextConfig
