import axios from 'axios'
import { getApiUrl } from '@/utils/apiConfig'

const api = axios.create({
    baseURL: getApiUrl(),
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
