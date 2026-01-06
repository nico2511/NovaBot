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
        <div className="flex h-screen flex-col items-center justify-center bg-[#0b0e11] text-white">
            <h2 className="mb-4 text-2xl font-bold text-red-500">Something went wrong!</h2>
            <p className="mb-4 text-gray-400 font-mono text-sm max-w-md text-center">
                {error.message || "An unexpected error occurred."}
            </p>
            <button
                className="rounded bg-blue-600 px-4 py-2 font-bold text-white hover:bg-blue-700 transition-colors"
                onClick={
                    // Attempt to recover by trying to re-render the segment
                    () => reset()
                }
            >
                Try again
            </button>
        </div>
    )
}
