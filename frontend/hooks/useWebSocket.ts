import { useEffect, useRef, useState, useCallback } from 'react'

interface UseWebSocketOptions {
    onMessage?: (data: any) => void
    onOpen?: () => void
    onClose?: () => void
    onError?: (error: Event) => void
    reconnectInterval?: number
    maxReconnectAttempts?: number
}

export function useWebSocket(url: string, options: UseWebSocketOptions = {}) {
    const {
        onMessage,
        onOpen,
        onClose,
        onError,
        reconnectInterval = 3000,
        maxReconnectAttempts = 5
    } = options

    const [isConnected, setIsConnected] = useState(false)
    const [lastMessage, setLastMessage] = useState<any>(null)
    const wsRef = useRef<WebSocket | null>(null)
    const reconnectAttemptsRef = useRef(0)
    const reconnectTimeoutRef = useRef<NodeJS.Timeout>()

    const connect = useCallback(() => {
        try {
            const ws = new WebSocket(url)

            ws.onopen = () => {
                console.log('WebSocket connected')
                setIsConnected(true)
                reconnectAttemptsRef.current = 0
                onOpen?.()
            }

            ws.onmessage = (event) => {
                try {
                    const data = JSON.parse(event.data)
                    setLastMessage(data)
                    onMessage?.(data)
                } catch (error) {
                    console.error('Failed to parse WebSocket message:', error)
                }
            }

            ws.onclose = () => {
                console.log('WebSocket disconnected')
                setIsConnected(false)
                onClose?.()

                // Auto-reconnect
                if (reconnectAttemptsRef.current < maxReconnectAttempts) {
                    reconnectAttemptsRef.current++
                    console.log(`Reconnecting... (${reconnectAttemptsRef.current}/${maxReconnectAttempts})`)
                    reconnectTimeoutRef.current = setTimeout(connect, reconnectInterval)
                }
            }

            ws.onerror = (error) => {
                console.error('WebSocket error:', error)
                onError?.(error)
            }

            wsRef.current = ws
        } catch (error) {
            console.error('Failed to create WebSocket:', error)
        }
    }, [url, onMessage, onOpen, onClose, onError, reconnectInterval, maxReconnectAttempts])

    const sendMessage = useCallback((data: any) => {
        if (wsRef.current?.readyState === WebSocket.OPEN) {
            wsRef.current.send(JSON.stringify(data))
        } else {
            console.warn('WebSocket is not connected')
        }
    }, [])

    const disconnect = useCallback(() => {
        if (reconnectTimeoutRef.current) {
            clearTimeout(reconnectTimeoutRef.current)
        }
        wsRef.current?.close()
        wsRef.current = null
    }, [])

    useEffect(() => {
        connect()
        return () => disconnect()
    }, [connect, disconnect])

    return {
        isConnected,
        lastMessage,
        sendMessage,
        disconnect
    }
}
