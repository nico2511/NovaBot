interface StatusPillProps {
    isRunning: boolean;
}

export default function StatusPill({ isRunning }: StatusPillProps) {
    return (
        <div
            className={`inline-flex items-center px-6 py-3 rounded-full font-semibold text-sm ${isRunning
                    ? 'bg-profit/20 border-2 border-profit text-profit'
                    : 'bg-loss/20 border-2 border-loss text-loss'
                }`}
        >
            <span className={`w-2 h-2 rounded-full mr-2 ${isRunning ? 'bg-profit' : 'bg-loss'}`} />
            {isRunning ? 'RUNNING' : 'STOPPED'}
        </div>
    );
}
