import { useState } from 'react';
import { useTrades, useSubaccounts, useTradesSummary, usePerformanceEquity } from '../hooks/useApi';
import type { TradeItem, SubaccountInfo } from '../types';
import { Activity, Wallet } from 'lucide-react';
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

// Subaccount Card
function SubaccountCard({ subaccount }: { subaccount: SubaccountInfo }) {
  const pnlColor = subaccount.pnl >= 0 ? 'text-[var(--color-profit)]' : 'text-[var(--color-loss)]';

  return (
    <div className="card">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-2">
          <Wallet className="w-4 h-4 text-[var(--color-text-tertiary)]" />
          <span className="font-semibold text-[var(--color-text-primary)]">Sub {subaccount.index}</span>
        </div>
        <span className={`badge ${subaccount.status === 'active' ? 'badge-profit' : 'badge-neutral'}`}>
          {subaccount.status}
        </span>
      </div>

      {subaccount.strategy_name ? (
        <div className="text-xs text-[var(--color-text-secondary)] mb-3 truncate font-mono">
          {subaccount.strategy_name}
        </div>
      ) : (
        <div className="text-xs text-[var(--color-text-tertiary)] mb-3">No strategy</div>
      )}

      <div className="grid grid-cols-2 gap-3 text-sm">
        <div>
          <div className="text-xs text-[var(--color-text-tertiary)]">Balance</div>
          <div className="font-mono text-[var(--color-text-primary)]">${subaccount.balance.toFixed(2)}</div>
        </div>
        <div>
          <div className="text-xs text-[var(--color-text-tertiary)]">PnL</div>
          <div className={`font-mono ${pnlColor}`}>{formatPnl(subaccount.pnl)}</div>
        </div>
        <div>
          <div className="text-xs text-[var(--color-text-tertiary)]">Return</div>
          <div className={`font-mono ${pnlColor}`}>{formatPct(subaccount.pnl_pct)}</div>
        </div>
        <div>
          <div className="text-xs text-[var(--color-text-tertiary)]">Positions</div>
          <div className="font-mono text-[var(--color-text-primary)]">{subaccount.open_positions}</div>
        </div>
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

  const { data: subaccounts, isLoading: subaccountsLoading } = useSubaccounts();
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

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-[var(--color-text-primary)]">Trading</h1>
        <p className="text-sm text-[var(--color-text-secondary)] mt-1">Live trading overview</p>
      </div>

      {/* Top Row: Equity + Summary - Stack on mobile */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Equity Curve */}
        <div className="lg:col-span-2 card">
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 mb-4">
            <h3 className="text-sm font-semibold text-[var(--color-text-tertiary)] uppercase">
              Equity Curve (24h)
            </h3>
            {performanceData && (
              <div className="flex gap-4 text-xs">
                <div>
                  <span className="text-[var(--color-text-tertiary)]">Return: </span>
                  <span className={`font-mono ${performanceData.total_return >= 0 ? 'text-[var(--color-profit)]' : 'text-[var(--color-loss)]'}`}>
                    {(performanceData.total_return * 100).toFixed(2)}%
                  </span>
                </div>
                <div>
                  <span className="text-[var(--color-text-tertiary)]">Drawdown: </span>
                  <span className="font-mono text-[var(--color-loss)]">
                    {(performanceData.max_drawdown * 100).toFixed(2)}%
                  </span>
                </div>
              </div>
            )}
          </div>
          <div className="h-48">
            <ResponsiveContainer width="100%" height={192}>
              <LineChart data={equityData}>
                <XAxis
                  dataKey="time"
                  stroke={chartColors.axis}
                  fontSize={11}
                  tickLine={false}
                  axisLine={false}
                />
                <YAxis
                  stroke={chartColors.axis}
                  fontSize={11}
                  tickLine={false}
                  axisLine={false}
                  tickFormatter={(value) => `$${value}`}
                  width={60}
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
                  stroke="var(--color-profit)"
                  strokeWidth={2}
                  dot={false}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Summary Stats */}
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
                <span className="font-mono text-[var(--color-profit)]">
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

      {/* Subaccounts Grid - 2 cols mobile, 5 cols desktop */}
      <div>
        <h2 className="text-lg font-semibold text-[var(--color-text-primary)] mb-4">Subaccounts</h2>
        {subaccountsLoading ? (
          <div className="flex items-center justify-center h-32">
            <Activity className="w-6 h-6 animate-spin text-[var(--color-text-tertiary)]" />
          </div>
        ) : (
          <div className="grid grid-cols-1 xs:grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-4">
            {subaccounts?.items.map((sub) => (
              <SubaccountCard key={sub.index} subaccount={sub} />
            ))}
          </div>
        )}
      </div>

      {/* Trades Table */}
      <div>
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-4">
          <h2 className="text-lg font-semibold text-[var(--color-text-primary)]">Trades</h2>
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
