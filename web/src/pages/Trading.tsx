import { useState } from 'react';
import { useTrades, useSubaccounts, useTradesSummary } from '../hooks/useApi';
import type { TradeItem, SubaccountInfo } from '../types';
import { Activity, Wallet } from 'lucide-react';
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
  const statusColor =
    subaccount.status === 'active'
      ? 'text-profit'
      : subaccount.status === 'error'
      ? 'text-loss'
      : 'text-muted';

  const pnlColor = subaccount.pnl >= 0 ? 'text-profit' : 'text-loss';

  return (
    <div className="bg-card border border-border rounded-lg p-4">
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <Wallet className="w-4 h-4 text-muted" />
          <span className="font-semibold">Subaccount {subaccount.index}</span>
        </div>
        <span className={`text-xs uppercase ${statusColor}`}>
          {subaccount.status}
        </span>
      </div>

      {subaccount.strategy_name ? (
        <div className="text-xs text-muted mb-3 truncate">
          {subaccount.strategy_name}
        </div>
      ) : (
        <div className="text-xs text-muted mb-3">No strategy</div>
      )}

      <div className="grid grid-cols-2 gap-2 text-sm">
        <div>
          <div className="text-xs text-muted">Balance</div>
          <div className="font-mono">${subaccount.balance.toFixed(2)}</div>
        </div>
        <div>
          <div className="text-xs text-muted">PnL</div>
          <div className={`font-mono ${pnlColor}`}>
            {formatPnl(subaccount.pnl)}
          </div>
        </div>
        <div>
          <div className="text-xs text-muted">Return</div>
          <div className={`font-mono ${pnlColor}`}>
            {formatPct(subaccount.pnl_pct)}
          </div>
        </div>
        <div>
          <div className="text-xs text-muted">Positions</div>
          <div className="font-mono">{subaccount.open_positions}</div>
        </div>
      </div>
    </div>
  );
}

// Trade Row
function TradeRow({ trade }: { trade: TradeItem }) {
  const pnlColor =
    trade.status === 'open'
      ? 'text-muted'
      : (trade.pnl || 0) >= 0
      ? 'text-profit'
      : 'text-loss';

  const sideColor = trade.side === 'long' ? 'text-profit' : 'text-loss';

  return (
    <tr className="border-b border-terminal hover:bg-white/5">
      <td className="px-4 py-2 text-sm font-mono">{trade.symbol}</td>
      <td className={`px-4 py-2 text-sm ${sideColor} uppercase`}>{trade.side}</td>
      <td className="px-4 py-2 text-sm font-mono">${trade.entry_price.toFixed(2)}</td>
      <td className="px-4 py-2 text-sm font-mono">
        {trade.exit_price ? `$${trade.exit_price.toFixed(2)}` : '--'}
      </td>
      <td className="px-4 py-2 text-sm font-mono">{trade.size.toFixed(4)}</td>
      <td className={`px-4 py-2 text-sm font-mono text-right ${pnlColor}`}>
        {formatPnl(trade.pnl)}
      </td>
      <td className="px-4 py-2 text-sm text-muted">
        {formatTime(trade.opened_at)}
      </td>
    </tr>
  );
}

// Summary Stats Card
function SummaryCard({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="bg-card border border-border rounded-lg p-4">
      <h3 className="text-sm font-semibold text-muted uppercase mb-4">{title}</h3>
      {children}
    </div>
  );
}

// Main Trading Page
export default function Trading() {
  const [tradeStatus, setTradeStatus] = useState<'open' | 'closed'>('open');

  const { data: trades, isLoading: tradesLoading } = useTrades({
    status: tradeStatus,
    limit: 50,
  });

  const { data: subaccounts, isLoading: subaccountsLoading } = useSubaccounts();
  const { data: summary } = useTradesSummary({ days: 30 });

  // Mock equity data for chart (would come from API in production)
  const equityData = [
    { time: '00:00', equity: 10000 },
    { time: '04:00', equity: 10050 },
    { time: '08:00', equity: 10120 },
    { time: '12:00', equity: 10080 },
    { time: '16:00', equity: 10200 },
    { time: '20:00', equity: 10180 },
    { time: 'Now', equity: 10250 },
  ];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold">Trading</h1>
        <p className="text-sm text-muted mt-1">Live trading overview</p>
      </div>

      {/* Top Row: Equity + Summary */}
      <div className="grid grid-cols-3 gap-6">
        {/* Equity Curve */}
        <div className="col-span-2 bg-card border border-border rounded-lg p-4">
          <h3 className="text-sm font-semibold text-muted uppercase mb-4">
            Equity Curve (24h)
          </h3>
          <div className="h-48">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={equityData}>
                <XAxis
                  dataKey="time"
                  stroke="#888888"
                  fontSize={12}
                  tickLine={false}
                  axisLine={false}
                />
                <YAxis
                  stroke="#888888"
                  fontSize={12}
                  tickLine={false}
                  axisLine={false}
                  tickFormatter={(value) => `$${value}`}
                />
                <Tooltip
                  contentStyle={{
                    backgroundColor: '#111111',
                    border: '1px solid #1f1f1f',
                    borderRadius: '4px',
                  }}
                  labelStyle={{ color: '#888888' }}
                />
                <Line
                  type="monotone"
                  dataKey="equity"
                  stroke="#10b981"
                  strokeWidth={2}
                  dot={false}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Summary Stats */}
        <SummaryCard title="30 Day Summary">
          {summary ? (
            <div className="space-y-3">
              <div className="flex justify-between">
                <span className="text-muted">Total Trades</span>
                <span className="font-mono">{summary.total_trades}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted">Win Rate</span>
                <span className="font-mono text-profit">
                  {(summary.win_rate * 100).toFixed(1)}%
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted">Total PnL</span>
                <span
                  className={`font-mono ${
                    summary.total_pnl >= 0 ? 'text-profit' : 'text-loss'
                  }`}
                >
                  {formatPnl(summary.total_pnl)}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted">Avg PnL</span>
                <span
                  className={`font-mono ${
                    summary.avg_pnl >= 0 ? 'text-profit' : 'text-loss'
                  }`}
                >
                  {formatPnl(summary.avg_pnl)}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted">Best Trade</span>
                <span className="font-mono text-profit">
                  {formatPnl(summary.best_trade)}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted">Worst Trade</span>
                <span className="font-mono text-loss">
                  {formatPnl(summary.worst_trade)}
                </span>
              </div>
            </div>
          ) : (
            <div className="text-muted text-center py-4">Loading...</div>
          )}
        </SummaryCard>
      </div>

      {/* Subaccounts Grid */}
      <div>
        <h2 className="text-lg font-semibold mb-4">Subaccounts</h2>
        {subaccountsLoading ? (
          <div className="flex items-center justify-center h-32">
            <Activity className="w-6 h-6 animate-spin text-muted" />
          </div>
        ) : (
          <div className="grid grid-cols-5 gap-4">
            {subaccounts?.items.map((sub) => (
              <SubaccountCard key={sub.index} subaccount={sub} />
            ))}
          </div>
        )}
      </div>

      {/* Trades Table */}
      <div>
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold">Trades</h2>
          <div className="flex gap-2">
            <button
              onClick={() => setTradeStatus('open')}
              className={`px-3 py-1 rounded text-sm ${
                tradeStatus === 'open'
                  ? 'bg-profit/20 text-profit'
                  : 'text-muted hover:text-foreground'
              }`}
            >
              Open ({trades?.items.filter((t) => t.status === 'open').length || 0})
            </button>
            <button
              onClick={() => setTradeStatus('closed')}
              className={`px-3 py-1 rounded text-sm ${
                tradeStatus === 'closed'
                  ? 'bg-profit/20 text-profit'
                  : 'text-muted hover:text-foreground'
              }`}
            >
              Closed
            </button>
          </div>
        </div>

        <div className="bg-card border border-border rounded-lg overflow-hidden">
          {tradesLoading ? (
            <div className="flex items-center justify-center h-32">
              <Activity className="w-6 h-6 animate-spin text-muted" />
            </div>
          ) : (
            <table className="w-full">
              <thead>
                <tr className="border-b border-terminal bg-background">
                  <th className="px-4 py-2 text-left text-xs font-semibold text-muted uppercase">
                    Symbol
                  </th>
                  <th className="px-4 py-2 text-left text-xs font-semibold text-muted uppercase">
                    Side
                  </th>
                  <th className="px-4 py-2 text-left text-xs font-semibold text-muted uppercase">
                    Entry
                  </th>
                  <th className="px-4 py-2 text-left text-xs font-semibold text-muted uppercase">
                    Exit
                  </th>
                  <th className="px-4 py-2 text-left text-xs font-semibold text-muted uppercase">
                    Size
                  </th>
                  <th className="px-4 py-2 text-right text-xs font-semibold text-muted uppercase">
                    PnL
                  </th>
                  <th className="px-4 py-2 text-left text-xs font-semibold text-muted uppercase">
                    Time
                  </th>
                </tr>
              </thead>
              <tbody>
                {trades?.items.map((trade) => (
                  <TradeRow key={trade.id} trade={trade} />
                ))}
                {(!trades?.items || trades.items.length === 0) && (
                  <tr>
                    <td colSpan={7} className="px-4 py-8 text-center text-muted">
                      No {tradeStatus} trades
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </div>
  );
}
