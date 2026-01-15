import { useState } from 'react';
import { useTrades, useTradesSummary, usePerformanceEquity, useMetricsSnapshot } from '../hooks/useApi';
import type { TradeItem, SnapshotSubaccount } from '../types';
import {
  Activity,
  Wallet,
  Clock,
  Target,
  AlertTriangle,
} from 'lucide-react';
import { useTheme } from '../contexts/ThemeContext';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
} from 'recharts';

// Format helpers
function formatPnl(value: number | null): string {
  if (value === null || value === undefined) return '--';
  const sign = value >= 0 ? '+' : '';
  return `${sign}$${Math.abs(value).toFixed(2)}`;
}

function formatPct(value: number | null): string {
  if (value === null || value === undefined) return '--';
  const sign = value >= 0 ? '+' : '';
  return `${sign}${value.toFixed(2)}%`;
}

function formatTime(dateStr: string | null): string {
  if (!dateStr) return '--';
  const date = new Date(dateStr);
  return date.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' });
}

function formatUsd(value: number): string {
  return `$${value.toLocaleString('en-US', { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`;
}

function formatUptime(days: number | null): string {
  if (days === null) return '--';
  if (days < 1) return `${Math.round(days * 24)}h`;
  return `${days.toFixed(1)}d`;
}

// Live Summary Stats Card
function LiveSummaryCard({ subaccounts }: { subaccounts: SnapshotSubaccount[] }) {
  const totalRpnl = subaccounts.reduce((sum, s) => sum + s.rpnl, 0);
  const totalUpnl = subaccounts.reduce((sum, s) => sum + s.upnl, 0);
  const totalBalance = subaccounts.reduce((sum, s) => sum + s.balance, 0);
  const totalPositions = subaccounts.reduce((sum, s) => sum + s.positions, 0);
  const avgWr = subaccounts.length > 0
    ? subaccounts.reduce((sum, s) => sum + s.wr_pct, 0) / subaccounts.length
    : 0;
  const maxDd = subaccounts.length > 0
    ? Math.max(...subaccounts.map(s => s.dd_pct))
    : 0;

  return (
    <div className="card">
      <h3 className="text-sm font-semibold text-[var(--color-text-tertiary)] uppercase mb-4">
        Live Performance
      </h3>
      <div className="grid grid-cols-2 gap-4">
        <div>
          <div className="text-xs text-[var(--color-text-tertiary)]">Realized P&L</div>
          <div className={`text-xl font-mono font-medium ${totalRpnl >= 0 ? 'text-[var(--color-profit)]' : 'text-[var(--color-loss)]'}`}>
            {formatPnl(totalRpnl)}
          </div>
        </div>
        <div>
          <div className="text-xs text-[var(--color-text-tertiary)]">Unrealized P&L</div>
          <div className={`text-xl font-mono font-medium ${totalUpnl >= 0 ? 'text-[var(--color-profit)]' : 'text-[var(--color-loss)]'}`}>
            {formatPnl(totalUpnl)}
          </div>
        </div>
        <div>
          <div className="text-xs text-[var(--color-text-tertiary)]">Deployed Capital</div>
          <div className="text-lg font-mono text-[var(--color-text-primary)]">
            {formatUsd(totalBalance)}
          </div>
        </div>
        <div>
          <div className="text-xs text-[var(--color-text-tertiary)]">Open Positions</div>
          <div className="text-lg font-mono text-[var(--color-text-primary)]">
            {totalPositions}
          </div>
        </div>
        <div>
          <div className="text-xs text-[var(--color-text-tertiary)]">Avg Win Rate</div>
          <div className={`text-lg font-mono ${avgWr >= 50 ? 'text-[var(--color-profit)]' : 'text-[var(--color-loss)]'}`}>
            {avgWr.toFixed(0)}%
          </div>
        </div>
        <div>
          <div className="text-xs text-[var(--color-text-tertiary)]">Max Drawdown</div>
          <div className={`text-lg font-mono ${maxDd > 15 ? 'text-[var(--color-loss)]' : 'text-[var(--color-warning)]'}`}>
            {maxDd.toFixed(0)}%
          </div>
        </div>
      </div>
    </div>
  );
}

// Enhanced Subaccount Card with snapshot data
function SubaccountCard({ subaccount }: { subaccount: SnapshotSubaccount }) {
  const pnlColor = subaccount.rpnl >= 0 ? 'text-[var(--color-profit)]' : 'text-[var(--color-loss)]';
  const hasPosition = subaccount.positions > 0;
  const ddWarning = subaccount.dd_pct > 15;

  return (
    <div className={`card ${ddWarning ? 'border border-[var(--color-warning)]/30' : ''}`}>
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <Wallet className="w-4 h-4 text-[var(--color-text-tertiary)]" />
          <span className="font-semibold text-[var(--color-text-primary)]">Sub {subaccount.id}</span>
        </div>
        <div className="flex items-center gap-1">
          {hasPosition && (
            <span className="badge badge-profit text-[10px]">{subaccount.positions} pos</span>
          )}
          {ddWarning && (
            <AlertTriangle className="w-4 h-4 text-[var(--color-warning)]" />
          )}
        </div>
      </div>

      {subaccount.strategy_name ? (
        <div className="text-xs text-[var(--color-text-secondary)] mb-2 truncate font-mono">
          {subaccount.strategy_name}
        </div>
      ) : (
        <div className="text-xs text-[var(--color-text-tertiary)] mb-2">No strategy</div>
      )}

      {/* Strategy info row */}
      {subaccount.strategy_name && (
        <div className="flex items-center gap-2 mb-3 text-xs text-[var(--color-text-tertiary)]">
          <span className="px-1.5 py-0.5 bg-[var(--color-bg-secondary)] rounded">
            {subaccount.timeframe || '?'}
          </span>
          <span className="px-1.5 py-0.5 bg-[var(--color-bg-secondary)] rounded">
            {subaccount.direction?.[0] || '?'}
          </span>
          <span className="flex items-center gap-1">
            <Clock className="w-3 h-3" />
            {formatUptime(subaccount.uptime_days)}
          </span>
        </div>
      )}

      <div className="grid grid-cols-2 gap-3 text-sm">
        <div>
          <div className="text-xs text-[var(--color-text-tertiary)]">Balance</div>
          <div className="font-mono text-[var(--color-text-primary)]">{formatUsd(subaccount.balance)}</div>
        </div>
        <div>
          <div className="text-xs text-[var(--color-text-tertiary)]">Realized</div>
          <div className={`font-mono ${pnlColor}`}>{formatPnl(subaccount.rpnl)}</div>
        </div>
        <div>
          <div className="text-xs text-[var(--color-text-tertiary)]">Unrealized</div>
          <div className={`font-mono ${subaccount.upnl >= 0 ? 'text-[var(--color-profit)]' : 'text-[var(--color-loss)]'}`}>
            {formatPnl(subaccount.upnl)}
          </div>
        </div>
        <div>
          <div className="text-xs text-[var(--color-text-tertiary)]">Return</div>
          <div className={`font-mono ${pnlColor}`}>{formatPct(subaccount.rpnl_pct)}</div>
        </div>
      </div>

      {/* Bottom stats row */}
      <div className="flex items-center justify-between mt-3 pt-3 border-t border-[var(--color-border-primary)] text-xs">
        <div className="flex items-center gap-1">
          <Target className="w-3 h-3 text-[var(--color-text-tertiary)]" />
          <span className={`font-mono ${subaccount.wr_pct >= 50 ? 'text-[var(--color-profit)]' : 'text-[var(--color-loss)]'}`}>
            {subaccount.wr_pct.toFixed(0)}% WR
          </span>
        </div>
        <div className={`font-mono ${subaccount.dd_pct > 15 ? 'text-[var(--color-loss)]' : 'text-[var(--color-text-tertiary)]'}`}>
          DD: {subaccount.dd_pct.toFixed(0)}%
        </div>
      </div>
    </div>
  );
}

// Open Positions Table
function OpenPositionsTable({ subaccounts }: { subaccounts: SnapshotSubaccount[] }) {
  const withPositions = subaccounts.filter(s => s.positions > 0);

  if (withPositions.length === 0) {
    return (
      <div className="card">
        <h3 className="text-sm font-semibold text-[var(--color-text-tertiary)] uppercase mb-4">
          Open Positions
        </h3>
        <div className="text-center py-8 text-[var(--color-text-tertiary)]">
          No open positions
        </div>
      </div>
    );
  }

  return (
    <div className="card p-0 overflow-hidden">
      <div className="px-4 py-3 border-b border-[var(--color-border-primary)]">
        <h3 className="text-sm font-semibold text-[var(--color-text-tertiary)] uppercase">
          Open Positions ({withPositions.reduce((sum, s) => sum + s.positions, 0)})
        </h3>
      </div>
      <div className="table-responsive">
        <table className="table">
          <thead>
            <tr>
              <th>Sub</th>
              <th>Strategy</th>
              <th>TF</th>
              <th className="hide-mobile">Dir</th>
              <th className="text-right">Positions</th>
              <th className="text-right">Unrealized</th>
            </tr>
          </thead>
          <tbody>
            {withPositions.map((sub) => (
              <tr key={sub.id} className="border-b border-[var(--color-border-primary)] hover:bg-[var(--color-bg-secondary)]">
                <td className="px-4 py-3 text-sm font-mono text-[var(--color-text-primary)]">#{sub.id}</td>
                <td className="px-4 py-3 text-sm font-mono text-[var(--color-text-secondary)] truncate max-w-[200px]">
                  {sub.strategy_name || '--'}
                </td>
                <td className="px-4 py-3 text-sm text-[var(--color-text-secondary)]">{sub.timeframe || '--'}</td>
                <td className="px-4 py-3 hide-mobile">
                  <span className={`badge ${sub.direction === 'LONG' ? 'badge-profit' : sub.direction === 'SHORT' ? 'badge-loss' : 'badge-neutral'}`}>
                    {sub.direction?.[0] || '?'}
                  </span>
                </td>
                <td className="px-4 py-3 text-sm font-mono text-right text-[var(--color-text-primary)]">{sub.positions}</td>
                <td className={`px-4 py-3 text-sm font-mono text-right ${sub.upnl >= 0 ? 'text-[var(--color-profit)]' : 'text-[var(--color-loss)]'}`}>
                  {formatPnl(sub.upnl)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// Trade Row Component
function TradeRow({ trade }: { trade: TradeItem }) {
  const pnlColor =
    trade.status === 'open'
      ? 'text-[var(--color-text-tertiary)]'
      : (trade.pnl || 0) >= 0
        ? 'text-[var(--color-profit)]'
        : 'text-[var(--color-loss)]';

  return (
    <tr className="border-b border-[var(--color-border-primary)] hover:bg-[var(--color-bg-secondary)]">
      <td className="px-4 py-3 text-sm font-mono text-[var(--color-text-primary)]">{trade.symbol}</td>
      <td className="px-4 py-3">
        <span className={`badge ${trade.side === 'long' ? 'badge-profit' : 'badge-loss'}`}>
          {trade.side.toUpperCase()}
        </span>
      </td>
      <td className="px-4 py-3 text-sm font-mono text-[var(--color-text-secondary)]">${trade.entry_price.toFixed(2)}</td>
      <td className="px-4 py-3 text-sm font-mono text-[var(--color-text-secondary)]">
        {trade.exit_price ? `$${trade.exit_price.toFixed(2)}` : '--'}
      </td>
      <td className="px-4 py-3 text-sm font-mono text-[var(--color-text-secondary)] hide-mobile">{trade.size.toFixed(4)}</td>
      <td className={`px-4 py-3 text-sm font-mono text-right ${pnlColor}`}>{formatPnl(trade.pnl)}</td>
      <td className="px-4 py-3 text-sm text-[var(--color-text-tertiary)] hide-mobile">{formatTime(trade.opened_at)}</td>
    </tr>
  );
}

// Main Trading Page
export default function Trading() {
  const [tradeStatus, setTradeStatus] = useState<'open' | 'closed'>('open');
  const { theme } = useTheme();

  const { data: trades, isLoading: tradesLoading } = useTrades({
    status: tradeStatus,
    limit: 50,
  });

  const { data: snapshot, isLoading: snapshotLoading } = useMetricsSnapshot();
  const { data: summary } = useTradesSummary({ days: 30 });
  const { data: performanceData } = usePerformanceEquity({ period: '24h' });

  // Transform equity data for chart
  const equityData =
    performanceData?.data_points.map((point) => ({
      time: new Date(point.timestamp).toLocaleTimeString('en-US', {
        hour: '2-digit',
        minute: '2-digit',
      }),
      equity: point.equity,
    })) || [];

  // Chart colors based on theme
  const chartColors = {
    axis: theme === 'dark' ? '#64748b' : '#94a3b8',
    tooltip: {
      bg: theme === 'dark' ? '#1e293b' : '#ffffff',
      border: theme === 'dark' ? '#334155' : '#e2e8f0',
    },
  };

  // Get subaccounts from snapshot
  const subaccounts = snapshot?.subaccounts || [];
  const activeSubaccounts = subaccounts.filter(s => s.strategy_name);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
        <div>
          <h1 className="text-2xl font-bold text-[var(--color-text-primary)]">Trading</h1>
          <p className="text-sm text-[var(--color-text-secondary)] mt-1">Live trading overview</p>
        </div>
        {snapshot && (
          <div className="flex items-center gap-2 text-sm">
            <span className={`px-2 py-1 rounded ${
              snapshot.trading_mode === 'LIVE'
                ? 'bg-[var(--color-profit)]/10 text-[var(--color-profit)]'
                : 'bg-[var(--color-warning)]/10 text-[var(--color-warning)]'
            }`}>
              {snapshot.trading_mode}
            </span>
            <span className="text-[var(--color-text-tertiary)]">
              {activeSubaccounts.length} active subaccounts
            </span>
          </div>
        )}
      </div>

      {/* Top Row: Equity + Live Summary + 30d Summary */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Equity Curve */}
        <div className="lg:col-span-1 card">
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 mb-4">
            <h3 className="text-sm font-semibold text-[var(--color-text-tertiary)] uppercase">
              Equity (24h)
            </h3>
            {performanceData && (
              <div className="flex gap-3 text-xs">
                <span className={`font-mono ${performanceData.total_return >= 0 ? 'text-[var(--color-profit)]' : 'text-[var(--color-loss)]'}`}>
                  {performanceData.total_return >= 0 ? '+' : ''}{(performanceData.total_return * 100).toFixed(2)}%
                </span>
              </div>
            )}
          </div>
          <div className="h-40">
            <ResponsiveContainer width="100%" height={160}>
              <LineChart data={equityData}>
                <XAxis
                  dataKey="time"
                  stroke={chartColors.axis}
                  fontSize={10}
                  tickLine={false}
                  axisLine={false}
                />
                <YAxis
                  stroke={chartColors.axis}
                  fontSize={10}
                  tickLine={false}
                  axisLine={false}
                  tickFormatter={(value) => `$${value}`}
                  width={50}
                />
                <Tooltip
                  contentStyle={{
                    backgroundColor: chartColors.tooltip.bg,
                    border: `1px solid ${chartColors.tooltip.border}`,
                    borderRadius: '8px',
                    fontSize: '12px',
                  }}
                  labelStyle={{ color: chartColors.axis }}
                />
                <Line
                  type="monotone"
                  dataKey="equity"
                  stroke="var(--color-accent)"
                  strokeWidth={2}
                  dot={false}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Live Performance Summary */}
        {snapshotLoading ? (
          <div className="card flex items-center justify-center h-48">
            <Activity className="w-6 h-6 animate-spin text-[var(--color-text-tertiary)]" />
          </div>
        ) : (
          <LiveSummaryCard subaccounts={subaccounts} />
        )}

        {/* 30 Day Summary Stats */}
        <div className="card">
          <h3 className="text-sm font-semibold text-[var(--color-text-tertiary)] uppercase mb-4">
            30 Day Summary
          </h3>
          {summary ? (
            <div className="space-y-3">
              <div className="flex justify-between">
                <span className="text-[var(--color-text-secondary)]">Total Trades</span>
                <span className="font-mono text-[var(--color-text-primary)]">{summary.total_trades}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-[var(--color-text-secondary)]">Win Rate</span>
                <span className={`font-mono ${summary.win_rate >= 0.5 ? 'text-[var(--color-profit)]' : 'text-[var(--color-loss)]'}`}>
                  {(summary.win_rate * 100).toFixed(1)}%
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-[var(--color-text-secondary)]">Total PnL</span>
                <span className={`font-mono ${summary.total_pnl >= 0 ? 'text-[var(--color-profit)]' : 'text-[var(--color-loss)]'}`}>
                  {formatPnl(summary.total_pnl)}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-[var(--color-text-secondary)]">Avg PnL</span>
                <span className={`font-mono ${summary.avg_pnl >= 0 ? 'text-[var(--color-profit)]' : 'text-[var(--color-loss)]'}`}>
                  {formatPnl(summary.avg_pnl)}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-[var(--color-text-secondary)]">Best Trade</span>
                <span className="font-mono text-[var(--color-profit)]">{formatPnl(summary.best_trade)}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-[var(--color-text-secondary)]">Worst Trade</span>
                <span className="font-mono text-[var(--color-loss)]">{formatPnl(summary.worst_trade)}</span>
              </div>
            </div>
          ) : (
            <div className="flex items-center justify-center py-8">
              <Activity className="w-5 h-5 animate-spin text-[var(--color-text-tertiary)]" />
            </div>
          )}
        </div>
      </div>

      {/* Open Positions Section */}
      <OpenPositionsTable subaccounts={subaccounts} />

      {/* Subaccounts Grid */}
      <div>
        <h2 className="text-lg font-semibold text-[var(--color-text-primary)] mb-4">
          Subaccounts ({activeSubaccounts.length} active)
        </h2>
        {snapshotLoading ? (
          <div className="flex items-center justify-center h-32">
            <Activity className="w-6 h-6 animate-spin text-[var(--color-text-tertiary)]" />
          </div>
        ) : (
          <div className="grid grid-cols-1 xs:grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-4">
            {subaccounts.map((sub) => (
              <SubaccountCard key={sub.id} subaccount={sub} />
            ))}
          </div>
        )}
      </div>

      {/* Trades Table */}
      <div>
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-4">
          <h2 className="text-lg font-semibold text-[var(--color-text-primary)]">Trade History</h2>
          <div className="flex gap-2">
            <button
              onClick={() => setTradeStatus('open')}
              className={`btn ${tradeStatus === 'open' ? 'btn-primary' : 'btn-ghost'}`}
            >
              Open ({trades?.items.filter((t) => t.status === 'open').length || 0})
            </button>
            <button
              onClick={() => setTradeStatus('closed')}
              className={`btn ${tradeStatus === 'closed' ? 'btn-primary' : 'btn-ghost'}`}
            >
              Closed
            </button>
          </div>
        </div>

        <div className="card p-0 overflow-hidden">
          {tradesLoading ? (
            <div className="flex items-center justify-center h-32">
              <Activity className="w-6 h-6 animate-spin text-[var(--color-text-tertiary)]" />
            </div>
          ) : (
            <div className="table-responsive">
              <table className="table">
                <thead>
                  <tr>
                    <th>Symbol</th>
                    <th>Side</th>
                    <th>Entry</th>
                    <th>Exit</th>
                    <th className="hide-mobile">Size</th>
                    <th className="text-right">PnL</th>
                    <th className="hide-mobile">Time</th>
                  </tr>
                </thead>
                <tbody>
                  {trades?.items.map((trade) => (
                    <TradeRow key={trade.id} trade={trade} />
                  ))}
                  {(!trades?.items || trades.items.length === 0) && (
                    <tr>
                      <td colSpan={7} className="text-center py-8 text-[var(--color-text-tertiary)]">
                        No {tradeStatus} trades
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
