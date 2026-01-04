import { useState } from 'react';
import { useStrategies, useStrategy } from '../hooks/useApi';
import type { StrategyListItem } from '../types';
import { X, Search, Code, BarChart2, Activity } from 'lucide-react';

// Status badge colors
const STATUS_COLORS: Record<string, string> = {
  GENERATED: 'bg-gray-500/20 text-gray-400',
  VALIDATED: 'bg-blue-500/20 text-blue-400',
  TESTED: 'bg-purple-500/20 text-purple-400',
  SELECTED: 'bg-amber-500/20 text-amber-400',
  LIVE: 'bg-profit/20 text-profit',
  RETIRED: 'bg-gray-500/20 text-gray-500',
  FAILED: 'bg-loss/20 text-loss',
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

// Strategy Row
function StrategyRow({
  strategy,
  onClick,
}: {
  strategy: StrategyListItem;
  onClick: () => void;
}) {
  const pnlColor = (strategy.total_pnl || 0) >= 0 ? 'text-profit' : 'text-loss';

  return (
    <tr
      className="border-b border-terminal hover:bg-white/5 cursor-pointer transition-colors"
      onClick={onClick}
    >
      <td className="px-4 py-3 font-mono text-sm">{strategy.name}</td>
      <td className="px-4 py-3 text-sm">{strategy.strategy_type || '--'}</td>
      <td className="px-4 py-3 text-sm">{strategy.timeframe || '--'}</td>
      <td className="px-4 py-3">
        <span
          className={`px-2 py-0.5 rounded text-xs font-medium ${
            STATUS_COLORS[strategy.status] || 'bg-gray-500/20 text-gray-400'
          }`}
        >
          {strategy.status}
        </span>
      </td>
      <td className="px-4 py-3 text-sm text-right font-mono">
        {formatNumber(strategy.sharpe_ratio)}
      </td>
      <td className="px-4 py-3 text-sm text-right font-mono">
        {formatPct(strategy.win_rate)}
      </td>
      <td className="px-4 py-3 text-sm text-right font-mono">
        {strategy.total_trades ?? '--'}
      </td>
      <td className={`px-4 py-3 text-sm text-right font-mono ${pnlColor}`}>
        {strategy.total_pnl ? `$${strategy.total_pnl.toFixed(2)}` : '--'}
      </td>
    </tr>
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
      <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
        <div className="bg-card border border-terminal rounded-lg p-8">
          <Activity className="w-8 h-8 animate-spin text-muted" />
        </div>
      </div>
    );
  }

  if (!strategy) return null;

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-8">
      <div className="bg-card border border-terminal rounded-lg w-full max-w-4xl max-h-[90vh] flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-terminal">
          <div>
            <h2 className="text-lg font-bold font-mono">{strategy.name}</h2>
            <div className="flex items-center gap-3 mt-1">
              <span className="text-sm text-muted">
                {strategy.strategy_type} | {strategy.timeframe}
              </span>
              <span
                className={`px-2 py-0.5 rounded text-xs font-medium ${
                  STATUS_COLORS[strategy.status]
                }`}
              >
                {strategy.status}
              </span>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-2 hover:bg-white/10 rounded transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Tabs */}
        <div className="flex border-b border-terminal">
          <button
            onClick={() => setActiveTab('code')}
            className={`flex items-center gap-2 px-4 py-2 text-sm border-b-2 transition-colors ${
              activeTab === 'code'
                ? 'border-profit text-profit'
                : 'border-transparent text-muted hover:text-foreground'
            }`}
          >
            <Code className="w-4 h-4" />
            Code
          </button>
          <button
            onClick={() => setActiveTab('backtest')}
            className={`flex items-center gap-2 px-4 py-2 text-sm border-b-2 transition-colors ${
              activeTab === 'backtest'
                ? 'border-profit text-profit'
                : 'border-transparent text-muted hover:text-foreground'
            }`}
          >
            <BarChart2 className="w-4 h-4" />
            Backtest
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-auto p-4">
          {activeTab === 'code' && (
            <div className="bg-background rounded p-4 overflow-auto">
              <pre className="text-sm font-mono whitespace-pre-wrap">
                {strategy.code || 'No code available'}
              </pre>
            </div>
          )}

          {activeTab === 'backtest' && strategy.backtest && (
            <div className="space-y-4">
              <h3 className="text-sm font-semibold text-muted uppercase">
                Backtest Metrics
              </h3>
              <div className="grid grid-cols-4 gap-4">
                <MetricCard
                  label="Sharpe Ratio"
                  value={formatNumber(strategy.backtest.sharpe_ratio)}
                />
                <MetricCard
                  label="Win Rate"
                  value={formatPct(strategy.backtest.win_rate)}
                />
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

              {/* Pattern Coins */}
              {strategy.pattern_coins && strategy.pattern_coins.length > 0 && (
                <div className="mt-4">
                  <h4 className="text-sm font-semibold text-muted uppercase mb-2">
                    Pattern Coins
                  </h4>
                  <div className="flex flex-wrap gap-2">
                    {strategy.pattern_coins.map((coin) => (
                      <span
                        key={coin}
                        className="px-2 py-1 bg-profit/20 text-profit rounded text-xs"
                      >
                        {coin}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

          {activeTab === 'backtest' && !strategy.backtest && (
            <div className="text-center text-muted py-8">
              No backtest results available
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// Metric Card
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
    <div className="bg-background rounded p-3">
      <div className="text-xs text-muted mb-1">{label}</div>
      <div className={`text-lg font-mono ${negative ? 'text-loss' : ''}`}>
        {value}
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
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Strategies</h1>
          <p className="text-sm text-muted mt-1">
            {data?.total || 0} strategies total
          </p>
        </div>
      </div>

      {/* Filters */}
      <div className="flex items-center gap-4">
        {/* Search */}
        <div className="relative flex-1 max-w-xs">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted" />
          <input
            type="text"
            placeholder="Search strategies..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-10 pr-4 py-2 bg-card border border-border rounded text-sm focus:outline-none focus:border-profit"
          />
        </div>

        {/* Status Filter */}
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          className="px-3 py-2 bg-card border border-border rounded text-sm focus:outline-none focus:border-profit"
        >
          <option value="">All Status</option>
          <option value="GENERATED">Generated</option>
          <option value="VALIDATED">Validated</option>
          <option value="TESTED">Tested</option>
          <option value="SELECTED">Selected</option>
          <option value="LIVE">Live</option>
          <option value="RETIRED">Retired</option>
          <option value="FAILED">Failed</option>
        </select>

        {/* Type Filter */}
        <select
          value={typeFilter}
          onChange={(e) => setTypeFilter(e.target.value)}
          className="px-3 py-2 bg-card border border-border rounded text-sm focus:outline-none focus:border-profit"
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
      <div className="bg-card border border-border rounded-lg overflow-hidden">
        {isLoading ? (
          <div className="flex items-center justify-center h-64">
            <Activity className="w-8 h-8 animate-spin text-muted" />
          </div>
        ) : error ? (
          <div className="p-4 text-loss">Error loading strategies</div>
        ) : (
          <table className="w-full">
            <thead>
              <tr className="border-b border-terminal bg-background">
                <th className="px-4 py-3 text-left text-xs font-semibold text-muted uppercase">
                  Name
                </th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-muted uppercase">
                  Type
                </th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-muted uppercase">
                  TF
                </th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-muted uppercase">
                  Status
                </th>
                <th className="px-4 py-3 text-right text-xs font-semibold text-muted uppercase">
                  Sharpe
                </th>
                <th className="px-4 py-3 text-right text-xs font-semibold text-muted uppercase">
                  Win %
                </th>
                <th className="px-4 py-3 text-right text-xs font-semibold text-muted uppercase">
                  Trades
                </th>
                <th className="px-4 py-3 text-right text-xs font-semibold text-muted uppercase">
                  PnL
                </th>
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
                  <td colSpan={8} className="px-4 py-8 text-center text-muted">
                    No strategies found
                  </td>
                </tr>
              )}
            </tbody>
          </table>
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
