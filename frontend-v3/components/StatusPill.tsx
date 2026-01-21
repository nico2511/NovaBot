interface StatusPillProps {
    isRunning: boolean;
}

export default function StatusPill({ isRunning }: StatusPillProps) {
    const borderColor = isRunning ? 'border-profit' : 'border-loss';
    const bgColor = isRunning ? 'bg-profit/20' : 'bg-loss/20';
    const dotColor = isRunning ? 'bg-profit' : 'bg-loss';
    const textColor = isRunning ? 'text-profit' : 'text-loss';

    return (
        <div className={`flex items-center gap-2 px-4 py-1.5 rounded-full border ${borderColor} ${bgColor}`}>
            <div className={`w-2 h-2 rounded-full ${dotColor} ${isRunning ? 'animate-pulse shadow-[0_0_8px_rgba(34,197,94,0.6)]' : ''}`} />
            <span className={`text-sm font-medium ${textColor}`}>
                {isRunning ? 'RUNNING' : 'STOPPED'}
            </span>
        </div>
    );
}
