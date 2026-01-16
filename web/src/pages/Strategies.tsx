import { useState } from 'react';
import {
  useStrategies,
  useStrategy,
  useBacktestRanking,
  useLiveRanking,
  useDegradationAnalysis,
} from '../hooks/useApi';
import type { StrategyListItem, RankedStrategy } from '../types';
import {
  X,
  Search,
  Code,
  BarChart2,
  Activity,
  Trophy,
  TrendingUp,
  AlertTriangle,
  AlertCircle,
} from 'lucide-react';
import type { ReactElement } from 'react';
import {
  ScatterChart,
  Scatter,
  XAxis,
  YAxis,
  ZAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
  ReferenceLine,
  Cell,
} from 'recharts';
import { useTheme } from '../contexts/ThemeContext';

// === Constants ===

type TabType = 'pool' | 'live' | 'rankings' | 'history';

const TABS: { id: TabType; label: string }[] = [
  { id: 'pool', label: 'Pool' },
  { id: 'live', label: 'Live' },
  { id: 'rankings', label: 'Rankings' },
  { id: 'history', label: 'History' },
];

const STATUS_STYLES: Record<string, string> = {
  GENERATED: 'badge-neutral',
  VALIDATED: 'badge-accent',
  ACTIVE: 'bg-violet-500/20 text-violet-500',
  LIVE: 'badge-profit',
  RETIRED: 'badge-neutral',
  FAILED: 'badge-loss',
};

// === Utility Functions ===

function formatNumber(value: number | null | undefined, decimals = 2): string {
  if (value === null || value === undefined) return '--';
  return value.toFixed(decimals);
}

function formatPct(value: number | null | undefined): string {
  if (value === null || value === undefined) return '--';
  return `${(value * 100).toFixed(1)}%`;
}

function getScoreColor(score: number | null): string {
  if (score === null) return 'text-[var(--color-text-tertiary)]';
  if (score >= 70) return 'text-[var(--color-profit)]';
  if (score >= 50) return 'text-[var(--color-warning)]';
  return 'text-[var(--color-loss)]';
}

function getRankBadge(rank: number): ReactElement {
  const colors: Record<number, string> = {
    1: 'bg-yellow-500/20 text-yellow-500 border-yellow-500/50',
    2: 'bg-gray-400/20 text-gray-400 border-gray-400/50',
    3: 'bg-orange-600/20 text-orange-600 border-orange-600/50',
  };
  const color =
    colors[rank] ||
    'bg-[var(--color-bg-tertiary)] text-[var(--color-text-tertiary)] border-[var(--color-border-primary)]';
  return (
    <div
      className={`w-8 h-8 rounded flex items-center justify-center text-xs font-bold border ${color}`}
    >
      #{rank}
    </div>
  );
}

// === Strategy Table Components ===

function StrategyRow({
  strategy,
  onClick,
}: {
  strategy: StrategyListItem;
  onClick: () => void;
}) {
  const pnlColor =
    (strategy.total_pnl || 0) >= 0
      ? 'text-[var(--color-profit)]'
      : 'text-[var(--color-loss)]';

  return (
    <tr
      className="border-b border-[var(--color-border-primary)] hover:bg-[var(--color-bg-secondary)] cursor-pointer transition-colors"
      onClick={onClick}
    >
      <td className="px-4 py-3 font-mono text-sm text-[var(--color-text-primary)]">
        {strategy.name}
      </td>
      <td className="px-4 py-3 text-sm text-[var(--color-text-secondary)] hide-mobile">
        {strategy.strategy_type || '--'}
      </td>
      <td className="px-4 py-3 text-sm text-[var(--color-text-secondary)] hide-mobile">
        {strategy.timeframe || '--'}
      </td>
      <td className="px-4 py-3">
        <span className={`badge ${STATUS_STYLES[strategy.status] || 'badge-neutral'}`}>
          {strategy.status}
        </span>
      </td>
      <td className="px-4 py-3 text-sm text-right font-mono text-[var(--color-text-secondary)]">
        {formatNumber(strategy.sharpe_ratio)}
      </td>
      <td className="px-4 py-3 text-sm text-right font-mono text-[var(--color-text-secondary)] hide-mobile">
        {formatPct(strategy.win_rate)}
      </td>
      <td className="px-4 py-3 text-sm text-right font-mono text-[var(--color-text-secondary)] hide-mobile">
        {strategy.total_trades ?? '--'}
      </td>
      <td className={`px-4 py-3 text-sm text-right font-mono ${pnlColor}`}>
        {strategy.total_pnl ? `$${strategy.total_pnl.toFixed(2)}` : '--'}
      </td>
    </tr>
  );
}

function MetricCard({
  label,
  value,
  negative,
}: {
  label: string;
  value: string;
  negative?: boolean;
}) {
  return (
    <div className="bg-[var(--color-bg-secondary)] rounded-lg p-3">
      <div className="text-xs text-[var(--color-text-tertiary)] mb-1">{label}</div>
      <div
        className={`text-lg font-mono ${negative ? 'text-[var(--color-loss)]' : 'text-[var(--color-text-primary)]'}`}
      >
        {value}
      </div>
    </div>
  );
}

function StrategyModal({
  strategyId,
  onClose,
}: {
  strategyId: string;
  onClose: () => void;
}) {
  const { data: strategy, isLoading } = useStrategy(strategyId);
  const [activeTab, setActiveTab] = useState<'code' | 'backtest'>('code');

  if (isLoading) {
    return (
      <div className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-50">
        <div className="card p-8">
          <Activity className="w-8 h-8 animate-spin text-[var(--color-text-tertiary)]" />
        </div>
      </div>
    );
  }

  if (!strategy) return null;

  return (
    <div className="fixed inset-0 bg-black/50 backdrop-blur-sm flex items-center justify-center z-50 p-4 md:p-8">
      <div className="card w-full max-w-4xl max-h-[90vh] flex flex-col p-0 overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-[var(--color-border-primary)]">
          <div>
            <h2 className="text-lg font-bold font-mono text-[var(--color-text-primary)]">
              {strategy.name}
            </h2>
            <div className="flex items-center gap-3 mt-1">
              <span className="text-sm text-[var(--color-text-secondary)]">
                {strategy.strategy_type} | {strategy.timeframe}
              </span>
              <span className={`badge ${STATUS_STYLES[strategy.status]}`}>
                {strategy.status}
              </span>
            </div>
          </div>
          <button onClick={onClose} className="btn btn-ghost p-2">
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Tabs */}
        <div className="flex border-b border-[var(--color-border-primary)]">
          <button
            onClick={() => setActiveTab('code')}
            className={`flex items-center gap-2 px-4 py-3 text-sm border-b-2 transition-colors ${
              activeTab === 'code'
                ? 'border-[var(--color-accent)] text-[var(--color-accent)]'
                : 'border-transparent text-[var(--color-text-tertiary)] hover:text-[var(--color-text-primary)]'
            }`}
          >
            <Code className="w-4 h-4" />
            Code
          </button>
          <button
            onClick={() => setActiveTab('backtest')}
            className={`flex items-center gap-2 px-4 py-3 text-sm border-b-2 transition-colors ${
              activeTab === 'backtest'
                ? 'border-[var(--color-accent)] text-[var(--color-accent)]'
                : 'border-transparent text-[var(--color-text-tertiary)] hover:text-[var(--color-text-primary)]'
            }`}
          >
            <BarChart2 className="w-4 h-4" />
            Backtest
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-auto p-4">
          {activeTab === 'code' && (
            <div className="bg-[var(--color-bg-secondary)] rounded-lg p-4 overflow-auto">
              <pre className="text-sm font-mono whitespace-pre-wrap text-[var(--color-text-secondary)]">
                {strategy.code || 'No code available'}
              </pre>
            </div>
          )}

          {activeTab === 'backtest' && strategy.backtest && (
            <div className="space-y-4">
              <h3 className="text-sm font-semibold text-[var(--color-text-tertiary)] uppercase">
                Backtest Metrics
              </h3>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                <MetricCard
                  label="Sharpe Ratio"
                  value={formatNumber(strategy.backtest.sharpe_ratio)}
                />
                <MetricCard label="Win Rate" value={formatPct(strategy.backtest.win_rate)} />
                <MetricCard
                  label="Max Drawdown"
                  value={formatPct(strategy.backtest.max_drawdown)}
                  negative
                />
                <MetricCard
                  label="Total Trades"
                  value={strategy.backtest.total_trades?.toString() || '--'}
                />
                <MetricCard
                  label="Expectancy"
                  value={formatNumber(strategy.backtest.expectancy)}
                />
                <MetricCard
                  label="Total Return"
                  value={formatPct(strategy.backtest.total_return)}
                />
                <MetricCard
                  label="Period Type"
                  value={strategy.backtest.period_type || '--'}
                />
                <MetricCard
                  label="Period Days"
                  value={strategy.backtest.period_days?.toString() || '--'}
                />
              </div>

              {strategy.pattern_coins && strategy.pattern_coins.length > 0 && (
                <div className="mt-4">
                  <h4 className="text-sm font-semibold text-[var(--color-text-tertiary)] uppercase mb-2">
                    Pattern Coins
                  </h4>
                  <div className="flex flex-wrap gap-2">
                    {strategy.pattern_coins.map((coin) => (
                      <span key={coin} className="badge badge-profit">
                        {coin}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

          {activeTab === 'backtest' && !strategy.backtest && (
            <div className="text-center text-[var(--color-text-tertiary)] py-8">
              No backtest results available
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// === Strategy List Tab ===

function StrategyListTab({
  statusFilter,
  showSearch = true,
}: {
  statusFilter: string | string[];
  showSearch?: boolean;
}) {
  const [typeFilter, setTypeFilter] = useState<string>('');
  const [search, setSearch] = useState('');
  const [selectedId, setSelectedId] = useState<string | null>(null);

  // Convert status filter to API format
  const apiStatus = Array.isArray(statusFilter) ? statusFilter[0] : statusFilter;

  const { data, isLoading, error } = useStrategies({
    status: apiStatus || undefined,
    type: typeFilter || undefined,
    limit: 100,
  });

  // For "history" we filter RETIRED + FAILED client-side
  const filteredByStatus = Array.isArray(statusFilter)
    ? data?.items.filter((s) => statusFilter.includes(s.status)) || []
    : data?.items || [];

  // Filter by search term
  const filteredStrategies = filteredByStatus.filter((s) =>
    s.name.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div className="space-y-4">
      {/* Filters */}
      {showSearch && (
        <div className="flex flex-col sm:flex-row gap-3">
          <div className="relative flex-1 sm:max-w-xs">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[var(--color-text-tertiary)]" />
            <input
              type="text"
              placeholder="Search strategies..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="input pl-10"
            />
          </div>
          <select
            value={typeFilter}
            onChange={(e) => setTypeFilter(e.target.value)}
            className="input sm:w-auto"
          >
            <option value="">All Types</option>
            <option value="MOM">Momentum</option>
            <option value="REV">Reversal</option>
            <option value="TRN">Trend</option>
            <option value="BRE">Breakout</option>
            <option value="VOL">Volatility</option>
            <option value="SCA">Scalping</option>
          </select>
        </div>
      )}

      {/* Table */}
      <div className="card p-0 overflow-hidden">
        {isLoading ? (
          <div className="flex items-center justify-center h-64">
            <Activity className="w-8 h-8 animate-spin text-[var(--color-text-tertiary)]" />
          </div>
        ) : error ? (
          <div className="p-4 text-[var(--color-loss)]">Error loading strategies</div>
        ) : (
          <div className="table-responsive">
            <table className="table">
              <thead>
                <tr>
                  <th>Name</th>
                  <th className="hide-mobile">Type</th>
                  <th className="hide-mobile">TF</th>
                  <th>Status</th>
                  <th className="text-right">Sharpe</th>
                  <th className="text-right hide-mobile">Win %</th>
                  <th className="text-right hide-mobile">Trades</th>
                  <th className="text-right">PnL</th>
                </tr>
              </thead>
              <tbody>
                {filteredStrategies.map((strategy) => (
                  <StrategyRow
                    key={strategy.id}
                    strategy={strategy}
                    onClick={() => setSelectedId(strategy.id)}
                  />
                ))}
                {filteredStrategies.length === 0 && (
                  <tr>
                    <td
                      colSpan={8}
                      className="text-center py-8 text-[var(--color-text-tertiary)]"
                    >
                      No strategies found
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Detail Modal */}
      {selectedId && (
        <StrategyModal strategyId={selectedId} onClose={() => setSelectedId(null)} />
      )}
    </div>
  );
}

// === Rankings Tab Components ===

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

function RankingTable({
  title,
  subtitle,
  data,
  rankingType,
  isLoading,
  error,
  avgScore,
  avgSharpe,
  avgPnl,
}: RankingTableProps) {
  if (isLoading) {
    return (
      <div className="card">
        <div className="flex items-center justify-center py-12">
          <Activity className="w-8 h-8 animate-spin text-[var(--color-text-tertiary)]" />
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="card">
        <div className="flex items-center gap-2 text-[var(--color-loss)]">
          <AlertCircle size={20} />
          <span className="text-sm">
            Error loading {title}: {error.message}
          </span>
        </div>
      </div>
    );
  }

  return (
    <div className="card p-0 overflow-hidden">
      <div className="p-4 border-b border-[var(--color-border-primary)]">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-lg font-semibold flex items-center gap-2 text-[var(--color-text-primary)]">
              {rankingType === 'backtest' ? <TrendingUp size={20} /> : <Trophy size={20} />}
              {title}
            </h2>
            <p className="text-xs text-[var(--color-text-tertiary)] mt-1">{subtitle}</p>
          </div>
          <div className="text-right">
            <div className="text-2xl font-bold text-[var(--color-profit)]">{data.length}</div>
            <div className="text-xs text-[var(--color-text-tertiary)]">strategies</div>
          </div>
        </div>

        <div className="flex flex-wrap gap-4 mt-4 text-sm">
          <div>
            <span className="text-[var(--color-text-tertiary)]">Avg Score:</span>
            <span className={`ml-2 font-semibold ${getScoreColor(avgScore)}`}>
              {avgScore.toFixed(1)}
            </span>
          </div>
          {avgSharpe !== null && avgSharpe !== undefined && (
            <div className="hide-mobile">
              <span className="text-[var(--color-text-tertiary)]">Avg Sharpe:</span>
              <span className="ml-2 font-semibold text-[var(--color-text-primary)]">
                {avgSharpe.toFixed(2)}
              </span>
            </div>
          )}
          {avgPnl !== null && avgPnl !== undefined && (
            <div>
              <span className="text-[var(--color-text-tertiary)]">Avg PnL:</span>
              <span
                className={`ml-2 font-semibold ${avgPnl >= 0 ? 'text-[var(--color-profit)]' : 'text-[var(--color-loss)]'}`}
              >
                ${avgPnl.toFixed(2)}
              </span>
            </div>
          )}
        </div>
      </div>

      {data.length === 0 ? (
        <div className="p-12 text-center text-[var(--color-text-tertiary)]">
          No strategies found
        </div>
      ) : (
        <div className="table-responsive">
          <table className="table">
            <thead>
              <tr>
                <th>Rank</th>
                <th>Strategy</th>
                <th className="hide-mobile">Type</th>
                <th className="hide-mobile">TF</th>
                <th className="text-right">Score</th>
                <th className="text-right hide-mobile">Sharpe</th>
                <th className="text-right hide-mobile">Win%</th>
                <th className="text-right hide-mobile">DD</th>
                {rankingType === 'live' && <th className="text-right">PnL</th>}
              </tr>
            </thead>
            <tbody>
              {data.map((strategy, index) => (
                <tr
                  key={strategy.id}
                  className="border-b border-[var(--color-border-primary)] hover:bg-[var(--color-bg-secondary)]"
                >
                  <td className="px-4 py-3">{getRankBadge(index + 1)}</td>
                  <td className="px-4 py-3">
                    <div className="font-medium font-mono text-sm text-[var(--color-text-primary)]">
                      {strategy.name}
                    </div>
                  </td>
                  <td className="px-4 py-3 hide-mobile">
                    <span className="badge badge-neutral">{strategy.strategy_type}</span>
                  </td>
                  <td className="px-4 py-3 hide-mobile">
                    <span className="text-xs font-mono text-[var(--color-text-tertiary)]">
                      {strategy.timeframe}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-right">
                    <span className={`font-bold ${getScoreColor(strategy.score)}`}>
                      {formatNumber(strategy.score, 1)}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-right font-mono text-sm text-[var(--color-text-secondary)] hide-mobile">
                    {formatNumber(strategy.sharpe)}
                  </td>
                  <td className="px-4 py-3 text-right font-mono text-sm text-[var(--color-text-secondary)] hide-mobile">
                    {formatPct(strategy.win_rate)}
                  </td>
                  <td className="px-4 py-3 text-right font-mono text-sm hide-mobile">
                    <span
                      className={
                        strategy.max_drawdown && strategy.max_drawdown > 0.25
                          ? 'text-[var(--color-loss)]'
                          : 'text-[var(--color-text-secondary)]'
                      }
                    >
                      {formatPct(strategy.max_drawdown)}
                    </span>
                  </td>
                  {rankingType === 'live' && (
                    <td className="px-4 py-3 text-right font-mono text-sm font-semibold">
                      <span
                        className={
                          strategy.total_pnl && strategy.total_pnl >= 0
                            ? 'text-[var(--color-profit)]'
                            : 'text-[var(--color-loss)]'
                        }
                      >
                        ${formatNumber(strategy.total_pnl)}
                      </span>
                    </td>
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

function RankingsTab() {
  const { theme } = useTheme();
  const {
    data: backtestData,
    isLoading: backtestLoading,
    error: backtestError,
  } = useBacktestRanking({ limit: 50 });
  const { data: liveData, isLoading: liveLoading, error: liveError } = useLiveRanking({
    limit: 20,
  });
  const { data: degradation } = useDegradationAnalysis({ threshold: 0.3 });

  const chartColors = {
    grid: theme === 'dark' ? '#334155' : '#e2e8f0',
    axis: theme === 'dark' ? '#64748b' : '#94a3b8',
    tooltip: {
      bg: theme === 'dark' ? '#1e293b' : '#ffffff',
      border: theme === 'dark' ? '#334155' : '#e2e8f0',
    },
  };

  return (
    <div className="space-y-6">
      {/* Degradation Analysis */}
      {degradation && degradation.total_live_strategies > 0 && (
        <div className="card">
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-4">
            <div>
              <h2 className="text-lg font-semibold flex items-center gap-2 text-[var(--color-text-primary)]">
                <AlertTriangle size={20} className="text-[var(--color-warning)]" />
                Degradation Monitor
              </h2>
              <p className="text-xs text-[var(--color-text-tertiary)] mt-1">
                Backtest vs Live performance comparison
              </p>
            </div>
            <div className="text-right">
              <div className="text-sm">
                <span className="text-[var(--color-text-tertiary)]">Degrading:</span>
                <span
                  className={`ml-2 font-bold ${degradation.degrading_count > 0 ? 'text-[var(--color-warning)]' : 'text-[var(--color-profit)]'}`}
                >
                  {degradation.degrading_count}/{degradation.total_live_strategies}
                </span>
              </div>
              <div className="text-xs text-[var(--color-text-tertiary)]">
                Avg: {(degradation.avg_degradation * 100).toFixed(1)}%
              </div>
            </div>
          </div>

          {/* Scatter Plot */}
          <div className="h-64 sm:h-80 hide-mobile">
            <ResponsiveContainer width="100%" height="100%">
              <ScatterChart margin={{ top: 20, right: 20, bottom: 20, left: 20 }}>
                <CartesianGrid strokeDasharray="3 3" stroke={chartColors.grid} />
                <XAxis
                  type="number"
                  dataKey="score_backtest"
                  name="Backtest Score"
                  stroke={chartColors.axis}
                  fontSize={11}
                  tickLine={false}
                  axisLine={false}
                  label={{
                    value: 'Backtest Score',
                    position: 'insideBottom',
                    offset: -10,
                    fill: chartColors.axis,
                    fontSize: 11,
                  }}
                />
                <YAxis
                  type="number"
                  dataKey="score_live"
                  name="Live Score"
                  stroke={chartColors.axis}
                  fontSize={11}
                  tickLine={false}
                  axisLine={false}
                  label={{
                    value: 'Live Score',
                    angle: -90,
                    position: 'insideLeft',
                    fill: chartColors.axis,
                    fontSize: 11,
                  }}
                />
                <ZAxis range={[50, 200]} />
                <Tooltip
                  cursor={{ strokeDasharray: '3 3' }}
                  content={({ active, payload }) => {
                    if (active && payload && payload[0]) {
                      const data = payload[0].payload;
                      return (
                        <div
                          className="p-3 rounded-lg text-xs"
                          style={{
                            backgroundColor: chartColors.tooltip.bg,
                            border: `1px solid ${chartColors.tooltip.border}`,
                          }}
                        >
                          <div className="font-semibold mb-1 text-[var(--color-text-primary)]">
                            {data.name}
                          </div>
                          <div className="space-y-1 text-[var(--color-text-secondary)]">
                            <div>Backtest: {data.score_backtest?.toFixed(1)}</div>
                            <div>Live: {data.score_live?.toFixed(1)}</div>
                            <div
                              className={
                                data.degradation_pct && data.degradation_pct > 0.3
                                  ? 'text-[var(--color-warning)]'
                                  : ''
                              }
                            >
                              Degradation: {((data.degradation_pct || 0) * 100).toFixed(1)}%
                            </div>
                            <div
                              className={
                                data.total_pnl >= 0
                                  ? 'text-[var(--color-profit)]'
                                  : 'text-[var(--color-loss)]'
                              }
                            >
                              PnL: ${data.total_pnl?.toFixed(2)}
                            </div>
                          </div>
                        </div>
                      );
                    }
                    return null;
                  }}
                />
                <ReferenceLine
                  segment={[
                    { x: 0, y: 0 },
                    { x: 100, y: 100 },
                  ]}
                  stroke={chartColors.axis}
                  strokeDasharray="3 3"
                />
                <Scatter name="Strategies" data={degradation.all_points} fill="#8884d8">
                  {degradation.all_points.map((entry, index) => (
                    <Cell
                      key={`cell-${index}`}
                      fill={
                        entry.degradation_pct && entry.degradation_pct > 0.5
                          ? '#ef4444'
                          : entry.degradation_pct && entry.degradation_pct > 0.3
                            ? '#f59e0b'
                            : '#10b981'
                      }
                    />
                  ))}
                </Scatter>
              </ScatterChart>
            </ResponsiveContainer>
          </div>

          {/* Mobile Summary */}
          <div className="md:hidden grid grid-cols-2 gap-3 mt-4">
            {degradation.all_points.slice(0, 4).map((point, idx) => (
              <div key={idx} className="bg-[var(--color-bg-secondary)] rounded-lg p-3">
                <div className="text-xs font-mono truncate text-[var(--color-text-primary)]">
                  {point.name}
                </div>
                <div
                  className={`text-sm font-bold mt-1 ${
                    point.degradation_pct && point.degradation_pct > 0.3
                      ? 'text-[var(--color-warning)]'
                      : 'text-[var(--color-profit)]'
                  }`}
                >
                  {((point.degradation_pct || 0) * 100).toFixed(0)}% deg
                </div>
              </div>
            ))}
          </div>

          {/* Worst Degraders */}
          {degradation.worst_degraders.length > 0 && (
            <div className="mt-4 pt-4 border-t border-[var(--color-border-primary)]">
              <h3 className="text-sm font-semibold mb-2 text-[var(--color-warning)]">
                Worst Degraders
              </h3>
              <div className="grid grid-cols-2 sm:grid-cols-5 gap-2 text-xs">
                {degradation.worst_degraders.slice(0, 5).map((s) => (
                  <div key={s.id} className="bg-[var(--color-bg-secondary)] p-2 rounded-lg">
                    <div className="font-mono text-[var(--color-text-primary)] truncate">
                      {s.name}
                    </div>
                    <div className="text-[var(--color-warning)] mt-1">
                      -{((s.degradation_pct || 0) * 100).toFixed(0)}%
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Live Ranking */}
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
        subtitle="Tested strategies ranked by backtest score"
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

// === Main Page ===

export default function Strategies() {
  const [activeTab, setActiveTab] = useState<TabType>('pool');

  // Get counts for tabs
  const { data: poolData } = useStrategies({ status: 'ACTIVE', limit: 1 });
  const { data: liveData } = useStrategies({ status: 'LIVE', limit: 1 });

  const tabCounts: Record<TabType, number | undefined> = {
    pool: poolData?.total,
    live: liveData?.total,
    rankings: undefined,
    history: undefined,
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-[var(--color-text-primary)]">Strategies</h1>
        <p className="text-sm text-[var(--color-text-secondary)] mt-1">
          Strategy pool, live performance, and rankings
        </p>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 border-b border-[var(--color-border-primary)]">
        {TABS.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`px-4 py-2.5 text-sm font-medium border-b-2 transition-colors ${
              activeTab === tab.id
                ? 'border-[var(--color-accent)] text-[var(--color-accent)]'
                : 'border-transparent text-[var(--color-text-tertiary)] hover:text-[var(--color-text-primary)]'
            }`}
          >
            {tab.label}
            {tabCounts[tab.id] !== undefined && (
              <span className="ml-1.5 text-xs opacity-60">({tabCounts[tab.id]})</span>
            )}
          </button>
        ))}
      </div>

      {/* Tab Content */}
      {activeTab === 'pool' && <StrategyListTab statusFilter="ACTIVE" />}
      {activeTab === 'live' && <StrategyListTab statusFilter="LIVE" />}
      {activeTab === 'rankings' && <RankingsTab />}
      {activeTab === 'history' && (
        <StrategyListTab statusFilter={['RETIRED', 'FAILED']} />
      )}
    </div>
  );
}
