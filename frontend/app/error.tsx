'use client'

import { useEffect } from 'react'

export default function Error({
    error,
    reset,
}: {
    error: Error & { digest?: string }
    reset: () => void
}) {
    useEffect(() => {
        console.error(error)
    }, [error])

    return (
        <div className="flex flex-col items-center justify-center min-h-screen bg-black text-white p-4">
            <h2 className="text-xl font-bold text-red-500 mb-4">Something went wrong!</h2>
            <div className="bg-gray-900 p-4 rounded-lg mb-4 max-w-2xl overflow-auto border border-gray-800">
                <p className="font-mono text-sm text-gray-300">{error.message}</p>
                {error.digest && (
                    <p className="font-mono text-xs text-gray-500 mt-2">Digest: {error.digest}</p>
                )}
            </div>
            <button
                onClick={() => reset()}
                className="px-4 py-2 bg-blue-600 rounded hover:bg-blue-700 transition-colors"
            >
                Try again
            </button>
        </div>
    )
}
