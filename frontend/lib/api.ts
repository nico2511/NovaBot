import axios from 'axios'

// Create axios instance with API key
// Create axios instance with dynamic base URL for LAN access
const getBaseUrl = () => {
    if (typeof window !== 'undefined') {
        // Browser: Use current hostname (works for localhost And LAN IP)
        return `${window.location.protocol}//${window.location.hostname}:8001`
    }
    // Server: Fallback to env or localhost
    return process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8001'
}

const api = axios.create({
    baseURL: getBaseUrl(),
    headers: {
        'X-API-Key': process.env.NEXT_PUBLIC_API_KEY || '',
        'Content-Type': 'application/json'
    }
})

// Add response interceptor for error handling
api.interceptors.response.use(
    (response) => response,
    (error) => {
        if (error.response?.status === 401) {
            console.error('API Key invalid or missing')
        }
        return Promise.reject(error)
    }
)

export default api
