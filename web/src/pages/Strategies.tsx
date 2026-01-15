import { useState } from 'react';
import { useStrategies, useStrategy } from '../hooks/useApi';
import type { StrategyListItem } from '../types';
import { X, Search, Code, BarChart2, Activity } from 'lucide-react';

// Status badge styles
const STATUS_STYLES: Record<string, string> = {
  GENERATED: 'badge-neutral',
  VALIDATED: 'badge-accent',
  ACTIVE: 'bg-violet-500/20 text-violet-500',
  LIVE: 'badge-profit',
  RETIRED: 'badge-neutral',
  FAILED: 'badge-loss',
};

// Format values
function formatNumber(value: number | null, decimals = 2): string {
  if (value === null || value === undefined) return '--';
  return value.toFixed(decimals);
}

function formatPct(value: number | null): string {
  if (value === null || value === undefined) return '--';
  return `${(value * 100).toFixed(1)}%`;
}

// Strategy Row Component
function StrategyRow({
  strategy,
  onClick,
}: {
  strategy: StrategyListItem;
  onClick: () => void;
}) {
  const pnlColor = (strategy.total_pnl || 0) >= 0 ? 'text-[var(--color-profit)]' : 'text-[var(--color-loss)]';

  return (
    <tr
      className="border-b border-[var(--color-border-primary)] hover:bg-[var(--color-bg-secondary)] cursor-pointer transition-colors"
      onClick={onClick}
    >
      <td className="px-4 py-3 font-mono text-sm text-[var(--color-text-primary)]">{strategy.name}</td>
      <td className="px-4 py-3 text-sm text-[var(--color-text-secondary)] hide-mobile">{strategy.strategy_type || '--'}</td>
      <td className="px-4 py-3 text-sm text-[var(--color-text-secondary)] hide-mobile">{strategy.timeframe || '--'}</td>
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

// Metric Card for Modal
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
      <div className={`text-lg font-mono ${negative ? 'text-[var(--color-loss)]' : 'text-[var(--color-text-primary)]'}`}>
        {value}
      </div>
    </div>
  );
}

// Strategy Detail Modal
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
            <h2 className="text-lg font-bold font-mono text-[var(--color-text-primary)]">{strategy.name}</h2>
            <div className="flex items-center gap-3 mt-1">
              <span className="text-sm text-[var(--color-text-secondary)]">
                {strategy.strategy_type} | {strategy.timeframe}
              </span>
              <span className={`badge ${STATUS_STYLES[strategy.status]}`}>
                {strategy.status}
              </span>
            </div>
          </div>
          <button
            onClick={onClose}
            className="btn btn-ghost p-2"
          >
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
                <MetricCard label="Sharpe Ratio" value={formatNumber(strategy.backtest.sharpe_ratio)} />
                <MetricCard label="Win Rate" value={formatPct(strategy.backtest.win_rate)} />
                <MetricCard label="Max Drawdown" value={formatPct(strategy.backtest.max_drawdown)} negative />
                <MetricCard label="Total Trades" value={strategy.backtest.total_trades?.toString() || '--'} />
                <MetricCard label="Expectancy" value={formatNumber(strategy.backtest.expectancy)} />
                <MetricCard label="Total Return" value={formatPct(strategy.backtest.total_return)} />
                <MetricCard label="Period Type" value={strategy.backtest.period_type || '--'} />
                <MetricCard label="Period Days" value={strategy.backtest.period_days?.toString() || '--'} />
              </div>

              {/* Pattern Coins */}
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

// Main Strategies Page
export default function Strategies() {
  const [statusFilter, setStatusFilter] = useState<string>('');
  const [typeFilter, setTypeFilter] = useState<string>('');
  const [search, setSearch] = useState('');
  const [selectedId, setSelectedId] = useState<string | null>(null);

  const { data, isLoading, error } = useStrategies({
    status: statusFilter || undefined,
    type: typeFilter || undefined,
    limit: 100,
  });

  // Filter by search term
  const filteredStrategies =
    data?.items.filter((s) =>
      s.name.toLowerCase().includes(search.toLowerCase())
    ) || [];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-[var(--color-text-primary)]">Strategies</h1>
        <p className="text-sm text-[var(--color-text-secondary)] mt-1">
          {data?.total || 0} strategies total
        </p>
      </div>

      {/* Filters - Stack on mobile */}
      <div className="flex flex-col sm:flex-row gap-3">
        {/* Search */}
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

        {/* Status Filter */}
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          className="input sm:w-auto"
        >
          <option value="">All Status</option>
          <option value="GENERATED">Generated</option>
          <option value="VALIDATED">Validated</option>
          <option value="ACTIVE">Active Pool</option>
          <option value="LIVE">Live</option>
          <option value="RETIRED">Retired</option>
          <option value="FAILED">Failed</option>
        </select>

        {/* Type Filter */}
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
                    <td colSpan={8} className="text-center py-8 text-[var(--color-text-tertiary)]">
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
        <StrategyModal
          strategyId={selectedId}
          onClose={() => setSelectedId(null)}
        />
      )}
    </div>
  );
}
