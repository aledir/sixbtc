import { useBacktestRanking, useLiveRanking, useDegradationAnalysis } from '../hooks/useApi';
import type { RankedStrategy } from '../types';
import { TrendingUp, Trophy, AlertCircle, AlertTriangle } from 'lucide-react';
import type { ReactElement } from 'react';
import { ScatterChart, Scatter, XAxis, YAxis, ZAxis, Tooltip, ResponsiveContainer, CartesianGrid, ReferenceLine, Cell } from 'recharts';

// === Utility Functions ===

function formatPercent(value: number | null | undefined): string {
  if (value === null || value === undefined) return '-';
  return `${(value * 100).toFixed(2)}%`;
}

function formatNumber(value: number | null | undefined, decimals: number = 2): string {
  if (value === null || value === undefined) return '-';
  return value.toFixed(decimals);
}

function getScoreColor(score: number | null): string {
  if (score === null) return 'text-muted';
  if (score >= 70) return 'text-profit';
  if (score >= 50) return 'text-warning';
  return 'text-loss';
}

function getRankBadge(rank: number): ReactElement {
  const colors = {
    1: 'bg-yellow-500/20 text-yellow-500 border-yellow-500/50',
    2: 'bg-gray-400/20 text-gray-400 border-gray-400/50',
    3: 'bg-orange-600/20 text-orange-600 border-orange-600/50',
  };

  const color = colors[rank as keyof typeof colors] || 'bg-white/5 text-muted border-border';

  return (
    <div className={`w-8 h-8 rounded flex items-center justify-center text-xs font-bold border ${color}`}>
      #{rank}
    </div>
  );
}

// === Components ===

interface RankingTableProps {
  title: string;
  subtitle: string;
  data: RankedStrategy[];
  rankingType: 'backtest' | 'live';
  isLoading: boolean;
  error: Error | null;
  avgScore: number;
  avgSharpe?: number | null;
  avgPnl?: number | null;
}

function RankingTable({ title, subtitle, data, rankingType, isLoading, error, avgScore, avgSharpe, avgPnl }: RankingTableProps) {
  if (isLoading) {
    return (
      <div className="bg-card border border-border rounded-lg p-6">
        <div className="flex items-center justify-center py-12">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-profit"></div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-card border border-border rounded-lg p-6">
        <div className="flex items-center gap-2 text-loss">
          <AlertCircle size={20} />
          <span className="text-sm">Error loading {title}: {error.message}</span>
        </div>
      </div>
    );
  }

  return (
    <div className="bg-card border border-border rounded-lg">
      {/* Header */}
      <div className="p-4 border-b border-border">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-lg font-semibold flex items-center gap-2">
              {rankingType === 'backtest' ? <TrendingUp size={20} /> : <Trophy size={20} />}
              {title}
            </h2>
            <p className="text-xs text-muted mt-1">{subtitle}</p>
          </div>
          <div className="text-right">
            <div className="text-2xl font-bold text-profit">{data.length}</div>
            <div className="text-xs text-muted">strategies</div>
          </div>
        </div>

        {/* Stats Summary */}
        <div className="flex gap-6 mt-4 text-sm">
          <div>
            <span className="text-muted">Avg Score:</span>
            <span className={`ml-2 font-semibold ${getScoreColor(avgScore)}`}>
              {avgScore.toFixed(1)}
            </span>
          </div>
          {avgSharpe !== null && avgSharpe !== undefined && (
            <div>
              <span className="text-muted">Avg Sharpe:</span>
              <span className="ml-2 font-semibold text-foreground">{avgSharpe.toFixed(2)}</span>
            </div>
          )}
          {avgPnl !== null && avgPnl !== undefined && (
            <div>
              <span className="text-muted">Avg PnL:</span>
              <span className={`ml-2 font-semibold ${avgPnl >= 0 ? 'text-profit' : 'text-loss'}`}>
                ${avgPnl.toFixed(2)}
              </span>
            </div>
          )}
        </div>
      </div>

      {/* Table */}
      {data.length === 0 ? (
        <div className="p-12 text-center text-muted">
          No strategies found
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-white/5 border-b border-border">
              <tr className="text-left text-xs text-muted">
                <th className="py-2 px-4 font-medium">Rank</th>
                <th className="py-2 px-4 font-medium">Strategy</th>
                <th className="py-2 px-4 font-medium">Type</th>
                <th className="py-2 px-4 font-medium">TF</th>
                <th className="py-2 px-4 font-medium text-right">Score</th>
                <th className="py-2 px-4 font-medium text-right">Sharpe</th>
                <th className="py-2 px-4 font-medium text-right">Win%</th>
                <th className="py-2 px-4 font-medium text-right">Trades</th>
                <th className="py-2 px-4 font-medium text-right">DD</th>
                {rankingType === 'live' && (
                  <>
                    <th className="py-2 px-4 font-medium text-right">PnL</th>
                    <th className="py-2 px-4 font-medium text-right">Degrad</th>
                  </>
                )}
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {data.map((strategy, index) => (
                <tr key={strategy.id} className="hover:bg-white/5">
                  <td className="py-3 px-4">
                    {getRankBadge(index + 1)}
                  </td>
                  <td className="py-3 px-4">
                    <div className="font-medium text-foreground">{strategy.name}</div>
                  </td>
                  <td className="py-3 px-4">
                    <span className="px-2 py-1 rounded bg-white/10 text-xs font-mono">
                      {strategy.strategy_type}
                    </span>
                  </td>
                  <td className="py-3 px-4">
                    <span className="text-xs font-mono text-muted">{strategy.timeframe}</span>
                  </td>
                  <td className="py-3 px-4 text-right">
                    <span className={`font-bold ${getScoreColor(strategy.score)}`}>
                      {formatNumber(strategy.score, 1)}
                    </span>
                  </td>
                  <td className="py-3 px-4 text-right font-mono">
                    {formatNumber(strategy.sharpe)}
                  </td>
                  <td className="py-3 px-4 text-right font-mono">
                    {formatPercent(strategy.win_rate)}
                  </td>
                  <td className="py-3 px-4 text-right font-mono text-muted">
                    {strategy.total_trades ?? '-'}
                  </td>
                  <td className="py-3 px-4 text-right font-mono">
                    <span className={strategy.max_drawdown && strategy.max_drawdown > 0.25 ? 'text-loss' : ''}>
                      {formatPercent(strategy.max_drawdown)}
                    </span>
                  </td>
                  {rankingType === 'live' && (
                    <>
                      <td className="py-3 px-4 text-right font-mono font-semibold">
                        <span className={strategy.total_pnl && strategy.total_pnl >= 0 ? 'text-profit' : 'text-loss'}>
                          ${formatNumber(strategy.total_pnl)}
                        </span>
                      </td>
                      <td className="py-3 px-4 text-right font-mono">
                        <span className={strategy.degradation_pct && strategy.degradation_pct > 0.3 ? 'text-warning' : ''}>
                          {formatPercent(strategy.degradation_pct)}
                        </span>
                      </td>
                    </>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

// === Main Page ===

export default function Rankings() {
  const { data: backtestData, isLoading: backtestLoading, error: backtestError } = useBacktestRanking({ limit: 50 });
  const { data: liveData, isLoading: liveLoading, error: liveError } = useLiveRanking({ limit: 20 });
  const { data: degradation } = useDegradationAnalysis({ threshold: 0.3 });

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div>
        <h1 className="text-2xl font-bold">Strategy Rankings</h1>
        <p className="text-sm text-muted mt-1">
          Leaderboards for backtest and live performance
        </p>
      </div>

      {/* Degradation Analysis */}
      {degradation && degradation.total_live_strategies > 0 && (
        <div className="bg-card border border-border rounded-lg p-6">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h2 className="text-lg font-semibold flex items-center gap-2">
                <AlertTriangle size={20} />
                Degradation Monitor
              </h2>
              <p className="text-xs text-muted mt-1">
                Backtest vs Live performance comparison
              </p>
            </div>
            <div className="text-right">
              <div className="text-sm">
                <span className="text-muted">Degrading:</span>
                <span className={`ml-2 font-bold ${degradation.degrading_count > 0 ? 'text-warning' : 'text-profit'}`}>
                  {degradation.degrading_count}/{degradation.total_live_strategies}
                </span>
              </div>
              <div className="text-xs text-muted">
                Avg: {(degradation.avg_degradation * 100).toFixed(1)}%
              </div>
            </div>
          </div>

          {/* Scatter Plot */}
          <div className="h-80">
            <ResponsiveContainer width="100%" height="100%">
              <ScatterChart margin={{ top: 20, right: 20, bottom: 20, left: 20 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#333" />
                <XAxis
                  type="number"
                  dataKey="score_backtest"
                  name="Backtest Score"
                  stroke="#888"
                  label={{ value: 'Backtest Score', position: 'insideBottom', offset: -10, fill: '#888' }}
                />
                <YAxis
                  type="number"
                  dataKey="score_live"
                  name="Live Score"
                  stroke="#888"
                  label={{ value: 'Live Score', angle: -90, position: 'insideLeft', fill: '#888' }}
                />
                <ZAxis range={[50, 200]} />
                <Tooltip
                  cursor={{ strokeDasharray: '3 3' }}
                  content={({ active, payload }) => {
                    if (active && payload && payload[0]) {
                      const data = payload[0].payload;
                      return (
                        <div className="bg-card border border-border p-3 rounded text-xs">
                          <div className="font-semibold mb-1">{data.name}</div>
                          <div className="space-y-1 text-muted">
                            <div>Backtest: {data.score_backtest?.toFixed(1)}</div>
                            <div>Live: {data.score_live?.toFixed(1)}</div>
                            <div className={data.degradation_pct && data.degradation_pct > 0.3 ? 'text-warning' : ''}>
                              Degradation: {((data.degradation_pct || 0) * 100).toFixed(1)}%
                            </div>
                            <div className={data.total_pnl >= 0 ? 'text-profit' : 'text-loss'}>
                              PnL: ${data.total_pnl?.toFixed(2)}
                            </div>
                          </div>
                        </div>
                      );
                    }
                    return null;
                  }}
                />
                {/* Perfect correlation line */}
                <ReferenceLine
                  segment={[{ x: 0, y: 0 }, { x: 100, y: 100 }]}
                  stroke="#888"
                  strokeDasharray="3 3"
                />
                <Scatter
                  name="Strategies"
                  data={degradation.all_points}
                  fill="#8884d8"
                >
                  {degradation.all_points.map((entry, index) => (
                    <Cell
                      key={`cell-${index}`}
                      fill={
                        entry.degradation_pct && entry.degradation_pct > 0.5 ? '#ef4444' :
                        entry.degradation_pct && entry.degradation_pct > 0.3 ? '#f59e0b' :
                        '#10b981'
                      }
                    />
                  ))}
                </Scatter>
              </ScatterChart>
            </ResponsiveContainer>
          </div>

          {/* Worst Degraders */}
          {degradation.worst_degraders.length > 0 && (
            <div className="mt-4 pt-4 border-t border-border">
              <h3 className="text-sm font-semibold mb-2 text-warning">⚠ Worst Degraders (Top 5)</h3>
              <div className="grid grid-cols-5 gap-2 text-xs">
                {degradation.worst_degraders.slice(0, 5).map(s => (
                  <div key={s.id} className="bg-white/5 p-2 rounded">
                    <div className="font-mono text-foreground truncate">{s.name}</div>
                    <div className="text-warning mt-1">-{((s.degradation_pct || 0) * 100).toFixed(0)}%</div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Live Ranking (Priority) */}
      <RankingTable
        title="Live Performance"
        subtitle="Active strategies ranked by live trading performance"
        data={liveData?.strategies || []}
        rankingType="live"
        isLoading={liveLoading}
        error={liveError}
        avgScore={liveData?.avg_score || 0}
        avgSharpe={liveData?.avg_sharpe}
        avgPnl={liveData?.avg_pnl}
      />

      {/* Backtest Ranking */}
      <RankingTable
        title="Backtest Rankings"
        subtitle="Tested strategies ranked by backtest score (Sharpe + Expectancy + Stability)"
        data={backtestData?.strategies || []}
        rankingType="backtest"
        isLoading={backtestLoading}
        error={backtestError}
        avgScore={backtestData?.avg_score || 0}
        avgSharpe={backtestData?.avg_sharpe}
      />
    </div>
  );
}
