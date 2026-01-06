import useSWR from 'swr'
import axios from 'axios'

const API_URL = ''
const fetcher = (url: string) => axios.get(url).then(res => res.data)

export function useDiagnostics() {
    const { data, error, mutate, isLoading } = useSWR(`${API_URL}/api/dev/diagnostics`, fetcher, {
        refreshInterval: 5000
    })

    const refresh = () => mutate()

    return {
        data,
        error,
        isLoading,
        refresh
    }
}
