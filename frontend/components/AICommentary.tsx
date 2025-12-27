"use client";

import { useEffect, useState } from 'react';
import { Sparkles, TrendingUp, AlertTriangle, Clock, Brain } from 'lucide-react';

interface AIAnalysis {
    raw_output?: string;
    model?: string;
}

interface SignalAnalysis {
    signal: any;
    analysis: AIAnalysis;
    timestamp: string;
}

interface AICommentaryProps {
    symbol: string;
}

export default function AICommentary({ symbol }: AICommentaryProps) {
    const [marketAnalysis, setMarketAnalysis] = useState<any>(null);
    const [positionAnalysis, setPositionAnalysis] = useState<any>(null);
    const [signalHistory, setSignalHistory] = useState<SignalAnalysis[]>([]);
    const [loading, setLoading] = useState(true);

    useEffect(() => {
        fetchAIData();
        const interval = setInterval(fetchAIData, 60000); // Refresh every minute
        return () => clearInterval(interval);
    }, [symbol]);

    const fetchAIData = async () => {
        try {
            // Fetch market commentary
            const marketRes = await fetch('http://localhost:8001/api/ai/market_commentary');
            if (marketRes.ok) {
                const data = await marketRes.json();
                setMarketAnalysis(data);
            }

            // Fetch position analysis if available
            const posRes = await fetch('http://localhost:8001/api/ai/position_analysis');
            if (posRes.ok) {
                const data = await posRes.json();
                if (!data.error) {
                    setPositionAnalysis(data);
                }
            }

            // Fetch AI history
            const historyRes = await fetch('http://localhost:8001/api/ai/history');
            if (historyRes.ok) {
                const data = await historyRes.json();
                if (data.signal_analyses) {
                    setSignalHistory(data.signal_analyses);
                }
            }

            setLoading(false);
        } catch (error) {
            console.error('Error fetching AI data:', error);
            setLoading(false);
        }
    };

    const parseAIOutput = (analysis: AIAnalysis | null) => {
        if (!analysis || !analysis.raw_output) return null;
        try {
            return JSON.parse(analysis.raw_output);
        } catch {
            return null;
        }
    };

    const marketData = marketAnalysis ? parseAIOutput(marketAnalysis.analysis) : null;
    const positionData = positionAnalysis ? parseAIOutput(positionAnalysis.analysis) : null;

    const getAlertColor = (level: string) => {
        switch (level) {
            case 'CRITICAL': return 'text-red-500 bg-red-500/10';
            case 'HIGH': return 'text-orange-500 bg-orange-500/10';
            case 'MEDIUM': return 'text-yellow-500 bg-yellow-500/10';
            case 'LOW': return 'text-green-500 bg-green-500/10';
            default: return 'text-gray-500 bg-gray-500/10';
        }
    };

    const getRiskColor = (level: string) => {
        switch (level) {
            case 'CRITICAL': return 'text-red-600';
            case 'HIGH': return 'text-orange-500';
            case 'MEDIUM': return 'text-yellow-500';
            case 'LOW': return 'text-green-500';
            default: return 'text-gray-500';
        }
    };

    if (loading) {
        return (
            <div className="bg-gray-800/50 backdrop-blur-sm rounded-lg p-6 border border-gray-700">
                <div className="flex items-center gap-2 mb-4">
                    <Brain className="w-5 h-5 text-purple-400 animate-pulse" />
                    <h3 className="text-lg font-semibold text-white">AI Commentary</h3>
                </div>
                <p className="text-gray-400">Chargement des analyses IA...</p>
            </div>
        );
    }

    return (
        <div className="space-y-4">
            {/* Market Analysis */}
            {marketData && (
                <div className="bg-gradient-to-br from-purple-900/20 to-blue-900/20 backdrop-blur-sm rounded-lg p-6 border border-purple-500/30">
                    <div className="flex items-center justify-between mb-4">
                        <div className="flex items-center gap-2">
                            <TrendingUp className="w-5 h-5 text-purple-400" />
                            <h3 className="text-lg font-semibold text-white">Analyse de Marché</h3>
                        </div>
                        {marketData.alert_level && (
                            <span className={`px-3 py-1 rounded-full text-xs font-medium ${getAlertColor(marketData.alert_level)}`}>
                                {marketData.alert_level}
                            </span>
                        )}
                    </div>

                    {marketData.summary && (
                        <p className="text-gray-200 mb-4 leading-relaxed">{marketData.summary}</p>
                    )}

                    {marketData.changes && Array.isArray(marketData.changes) && (
                        <div className="space-y-2 mb-4">
                            <p className="text-sm text-gray-400 font-medium">Changements détectés :</p>
                            <ul className="space-y-1">
                                {marketData.changes.map((change: string, idx: number) => (
                                    <li key={idx} className="text-sm text-gray-300 flex items-start gap-2">
                                        <span className="text-purple-400 mt-1">•</span>
                                        <span>{change}</span>
                                    </li>
                                ))}
                            </ul>
                        </div>
                    )}

                    {marketData.implications && (
                        <div className="bg-black/20 rounded-lg p-3 mt-3">
                            <p className="text-xs text-gray-400 mb-1">Implications :</p>
                            <p className="text-sm text-gray-200">{marketData.implications}</p>
                        </div>
                    )}

                    {marketAnalysis.timestamp && (
                        <div className="flex items-center gap-1 mt-4 text-xs text-gray-500">
                            <Clock className="w-3 h-3" />
                            <span>{new Date(marketAnalysis.timestamp).toLocaleTimeString('fr-FR')}</span>
                            {marketAnalysis.cached && <span className="ml-2">(en cache)</span>}
                        </div>
                    )}
                </div>
            )}

            {/* Position Analysis */}
            {positionData && (
                <div className="bg-gradient-to-br from-blue-900/20 to-cyan-900/20 backdrop-blur-sm rounded-lg p-6 border border-blue-500/30">
                    <div className="flex items-center justify-between mb-4">
                        <div className="flex items-center gap-2">
                            <AlertTriangle className="w-5 h-5 text-blue-400" />
                            <h3 className="text-lg font-semibold text-white">Position Active</h3>
                        </div>
                        {positionData.risk_level && (
                            <span className={`px-3 py-1 rounded-full text-xs font-medium ${getRiskColor(positionData.risk_level)}`}>
                                Risque: {positionData.risk_level}
                            </span>
                        )}
                    </div>

                    {positionData.reasoning && (
                        <p className="text-gray-200 mb-4">{positionData.reasoning}</p>
                    )}

                    {positionData.recommendations && Array.isArray(positionData.recommendations) && (
                        <div className="space-y-2 mb-4">
                            <p className="text-sm text-gray-400 font-medium">Recommandations :</p>
                            <ul className="space-y-2">
                                {positionData.recommendations.map((rec: string, idx: number) => (
                                    <li key={idx} className="text-sm text-gray-300 flex items-start gap-2 bg-black/20 rounded p-2">
                                        <span className="text-blue-400 mt-0.5">→</span>
                                        <span>{rec}</span>
                                    </li>
                                ))}
                            </ul>
                        </div>
                    )}

                    {positionData.actions && (
                        <div className="bg-black/30 rounded-lg p-3 mt-3">
                            <p className="text-xs text-gray-400 mb-1">Action suggérée :</p>
                            <p className="text-sm font-medium text-blue-300">{positionData.actions}</p>
                        </div>
                    )}
                </div>
            )}

            {/* Signal History */}
            {signalHistory.length > 0 && (
                <div className="bg-gray-800/50 backdrop-blur-sm rounded-lg p-6 border border-gray-700">
                    <div className="flex items-center gap-2 mb-4">
                        <Sparkles className="w-5 h-5 text-yellow-400" />
                        <h3 className="text-lg font-semibold text-white">Analyses de Signaux Récents</h3>
                    </div>

                    <div className="space-y-3 max-h-96 overflow-y-auto">
                        {signalHistory.slice().reverse().map((item, idx) => {
                            const analysis = parseAIOutput(item.analysis);
                            if (!analysis) return null;

                            return (
                                <div key={idx} className="bg-black/20 rounded-lg p-4 border border-gray-700/50">
                                    <div className="flex items-center justify-between mb-2">
                                        <div className="flex items-center gap-2">
                                            <span className={`px-2 py-1 rounded text-xs font-bold ${item.signal.signal === 'BUY' ? 'bg-green-500/20 text-green-400' : 'bg-red-500/20 text-red-400'
                                                }`}>
                                                {item.signal.signal}
                                            </span>
                                            <span className="text-sm text-gray-400">{item.signal.strategy}</span>
                                        </div>
                                        {analysis.confidence && (
                                            <span className="text-xs text-gray-500">
                                                Confiance: {analysis.confidence}
                                            </span>
                                        )}
                                    </div>

                                    {analysis.explanation && (
                                        <p className="text-sm text-gray-300 mb-2">{analysis.explanation}</p>
                                    )}

                                    {analysis.recommendation && (
                                        <p className="text-xs text-gray-400 italic">💡 {analysis.recommendation}</p>
                                    )}

                                    <div className="flex items-center gap-1 mt-2 text-xs text-gray-600">
                                        <Clock className="w-3 h-3" />
                                        <span>{new Date(item.timestamp).toLocaleString('fr-FR')}</span>
                                    </div>
                                </div>
                            );
                        })}
                    </div>
                </div>
            )}

            {/* No Data State */}
            {!marketData && !positionData && signalHistory.length === 0 && (
                <div className="bg-gray-800/50 backdrop-blur-sm rounded-lg p-8 border border-gray-700 text-center">
                    <Brain className="w-12 h-12 text-gray-600 mx-auto mb-3" />
                    <p className="text-gray-400">Aucune analyse IA disponible pour le moment</p>
                    <p className="text-sm text-gray-500 mt-2">Les analyses apparaîtront lorsque le bot sera actif</p>
                </div>
            )}
        </div>
    );
}
