import { useState } from 'react';
import { useStatus, useMetricsSnapshot, usePerformanceEquity } from '../hooks/useApi';
import type { ServiceInfo, SnapshotSubaccount, MetricsSnapshotResponse } from '../types';
import {
  Activity,
  AlertTriangle,
  CheckCircle,
  ChevronRight,
  ArrowUpRight,
  ArrowDownRight,
} from 'lucide-react';
import { useTheme } from '../contexts/ThemeContext';
import { Link } from 'react-router-dom';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
} from 'recharts';

// === Utility Functions ===

function formatPnl(value: number): string {
  const sign = value >= 0 ? '+' : '';
  return `${sign}$${Math.abs(value).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function formatPct(value: number): string {
  const sign = value >= 0 ? '+' : '';
  return `${sign}${value.toFixed(2)}%`;
}

function formatUsd(value: number): string {
  return `$${value.toLocaleString('en-US', { minimumFractionDigits: 0, maximumFractionDigits: 0 })}`;
}

function formatCompact(value: number): string {
  if (value >= 1000000) return `${(value / 1000000).toFixed(1)}M`;
  if (value >= 1000) return `${(value / 1000).toFixed(1)}k`;
  return value.toString();
}

// === Components ===

function StatusBadge({ mode, status }: { mode: string; status: string }) {
  const isLive = mode === 'LIVE';
  const isHealthy = status === 'HEALTHY';

  return (
    <div className="flex items-center gap-3">
      <div className={`flex items-center gap-2 px-3 py-1.5 rounded-lg ${
        isLive
          ? 'bg-[var(--color-profit)]/10 border border-[var(--color-profit)]/30'
          : 'bg-[var(--color-warning)]/10 border border-[var(--color-warning)]/30'
      }`}>
        <span className={`w-2 h-2 rounded-full ${
          isLive ? 'bg-[var(--color-profit)] animate-pulse' : 'bg-[var(--color-warning)]'
        }`} />
        <span className={`text-sm font-medium ${
          isLive ? 'text-[var(--color-profit)]' : 'text-[var(--color-warning)]'
        }`}>
          {mode}
        </span>
      </div>
      <div className={`flex items-center gap-1.5 px-2 py-1 rounded ${
        isHealthy ? 'text-[var(--color-profit)]' : 'text-[var(--color-warning)]'
      }`}>
        {isHealthy ? <CheckCircle size={16} /> : <AlertTriangle size={16} />}
        <span className="text-xs font-medium">{status}</span>
      </div>
    </div>
  );
}

// Hero P&L Section - The most important info
function PnlHero({ snapshot }: { snapshot: MetricsSnapshotResponse }) {
  const totalRpnl = snapshot.subaccounts.reduce((sum, s) => sum + s.rpnl, 0);
  const totalUpnl = snapshot.subaccounts.reduce((sum, s) => sum + s.upnl, 0);
  const totalPnl = totalRpnl + totalUpnl;
  const capital = snapshot.capital;
  const pnlPct = capital.subaccounts > 0 ? (totalPnl / capital.subaccounts) * 100 : 0;
  const isProfit = totalPnl >= 0;

  // Calculate max drawdown from subaccounts
  const maxDd = Math.max(...snapshot.subaccounts.map(s => s.dd_pct), 0);
  const maxAllowedDd = 30; // From config

  return (
    <div className="card bg-gradient-to-br from-[var(--color-bg-elevated)] to-[var(--color-bg-secondary)]">
      <div className="flex flex-col lg:flex-row lg:items-center lg:justify-between gap-6">
        {/* Main P&L Display */}
        <div className="flex-1">
          <p className="text-sm text-[var(--color-text-tertiary)] uppercase tracking-wide mb-2">
            Total P&L
          </p>
          <div className="flex items-baseline gap-3">
            <span className={`text-4xl md:text-5xl font-bold ${
              isProfit ? 'text-[var(--color-profit)]' : 'text-[var(--color-loss)]'
            }`}>
              {formatPnl(totalPnl)}
            </span>
            <span className={`text-xl font-medium flex items-center gap-1 ${
              isProfit ? 'text-[var(--color-profit)]' : 'text-[var(--color-loss)]'
            }`}>
              {isProfit ? <ArrowUpRight size={20} /> : <ArrowDownRight size={20} />}
              {formatPct(pnlPct)}
            </span>
          </div>
          <p className="text-sm text-[var(--color-text-tertiary)] mt-2">
            on {formatUsd(capital.subaccounts)} deployed
          </p>
        </div>

        {/* Secondary Metrics */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 lg:gap-6">
          <div className="text-center lg:text-right">
            <p className="text-xs text-[var(--color-text-tertiary)] uppercase">Realized</p>
            <p className={`text-lg font-mono font-medium ${
              totalRpnl >= 0 ? 'text-[var(--color-profit)]' : 'text-[var(--color-loss)]'
            }`}>
              {formatPnl(totalRpnl)}
            </p>
          </div>
          <div className="text-center lg:text-right">
            <p className="text-xs text-[var(--color-text-tertiary)] uppercase">Unrealized</p>
            <p className={`text-lg font-mono font-medium ${
              totalUpnl >= 0 ? 'text-[var(--color-profit)]' : 'text-[var(--color-loss)]'
            }`}>
              {formatPnl(totalUpnl)}
            </p>
          </div>
          <div className="text-center lg:text-right">
            <p className="text-xs text-[var(--color-text-tertiary)] uppercase">Positions</p>
            <p className="text-lg font-mono font-medium text-[var(--color-text-primary)]">
              {snapshot.subaccounts.reduce((sum, s) => sum + s.positions, 0)}
            </p>
          </div>
          <div className="text-center lg:text-right">
            <p className="text-xs text-[var(--color-text-tertiary)] uppercase">Drawdown</p>
            <div className="flex items-center justify-center lg:justify-end gap-2">
              <div className="w-16 h-2 bg-[var(--color-bg-tertiary)] rounded-full overflow-hidden">
                <div
                  className={`h-full rounded-full ${
                    maxDd > 20 ? 'bg-[var(--color-loss)]' :
                    maxDd > 10 ? 'bg-[var(--color-warning)]' :
                    'bg-[var(--color-profit)]'
                  }`}
                  style={{ width: `${(maxDd / maxAllowedDd) * 100}%` }}
                />
              </div>
              <span className={`text-sm font-mono ${
                maxDd > 20 ? 'text-[var(--color-loss)]' :
                maxDd > 10 ? 'text-[var(--color-warning)]' :
                'text-[var(--color-text-secondary)]'
              }`}>
                {maxDd.toFixed(0)}%
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

// Equity Curve with period selector
function EquityCurve() {
  const { theme } = useTheme();
  const [period, setPeriod] = useState<'24h' | '7d' | '30d'>('24h');
  const { data: performanceData, isLoading } = usePerformanceEquity({ period });

  const chartColors = {
    axis: theme === 'dark' ? '#64748b' : '#94a3b8',
    tooltip: {
      bg: theme === 'dark' ? '#1e293b' : '#ffffff',
      border: theme === 'dark' ? '#334155' : '#e2e8f0',
    },
  };

  const equityData = performanceData?.data_points.map((point) => ({
    time: new Date(point.timestamp).toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      hour: period === '24h' ? '2-digit' : undefined,
    }),
    equity: point.equity,
  })) || [];

  const startEquity = performanceData?.start_equity || 0;
  const currentReturn = performanceData?.total_return || 0;
  const maxDrawdown = performanceData?.max_drawdown || 0;

  return (
    <div className="card">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h3 className="text-sm font-semibold text-[var(--color-text-tertiary)] uppercase">
            Portfolio Equity
          </h3>
          {performanceData && (
            <div className="flex gap-4 text-xs mt-1">
              <span className={`font-mono ${currentReturn >= 0 ? 'text-[var(--color-profit)]' : 'text-[var(--color-loss)]'}`}>
                Return: {formatPct(currentReturn * 100)}
              </span>
              <span className="font-mono text-[var(--color-loss)]">
                Max DD: {formatPct(maxDrawdown * 100)}
              </span>
            </div>
          )}
        </div>
        <div className="flex gap-1">
          {(['24h', '7d', '30d'] as const).map((p) => (
            <button
              key={p}
              onClick={() => setPeriod(p)}
              className={`px-2 py-1 text-xs rounded transition-colors ${
                period === p
                  ? 'bg-[var(--color-accent)] text-white'
                  : 'text-[var(--color-text-tertiary)] hover:bg-[var(--color-bg-secondary)]'
              }`}
            >
              {p}
            </button>
          ))}
        </div>
      </div>
      <div className="h-40">
        {isLoading ? (
          <div className="flex items-center justify-center h-full">
            <Activity className="w-5 h-5 animate-spin text-[var(--color-text-tertiary)]" />
          </div>
        ) : equityData.length > 0 ? (
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={equityData}>
              <XAxis
                dataKey="time"
                stroke={chartColors.axis}
                fontSize={10}
                tickLine={false}
                axisLine={false}
                interval="preserveStartEnd"
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
                  borderRadius: '6px',
                  fontSize: '11px',
                }}
              />
              <ReferenceLine y={startEquity} stroke={chartColors.axis} strokeDasharray="3 3" />
              <Line
                type="monotone"
                dataKey="equity"
                stroke="var(--color-accent)"
                strokeWidth={2}
                dot={false}
              />
            </LineChart>
          </ResponsiveContainer>
        ) : (
          <div className="flex items-center justify-center h-full text-sm text-[var(--color-text-tertiary)]">
            No data
          </div>
        )}
      </div>
    </div>
  );
}

// Mini Pipeline Funnel - 10 steps
function MiniPipeline({ snapshot }: { snapshot: MetricsSnapshotResponse }) {
  const f = snapshot.funnel;
  const fail = snapshot.failures;

  const stages = [
    { label: 'Gen', value: f.generated, failed: 0 },
    { label: 'Val', value: f.validated, failed: fail.validation },
    { label: 'Param', value: snapshot.parametric?.total_combos || 0, failed: fail.parametric_fail },
    { label: 'IS', value: snapshot.is_backtest?.passed || 0, failed: snapshot.is_backtest?.failed || 0 },
    { label: 'OOS', value: snapshot.oos_backtest?.passed || 0, failed: snapshot.oos_backtest?.failed || 0 },
    { label: 'Score', value: f.score_passed || 0, failed: fail.score_reject },
    { label: 'Shuf', value: f.shuffle_passed || 0, failed: fail.shuffle_fail },
    { label: 'WFA', value: f.multi_window_passed || 0, failed: fail.mw_fail },
    { label: 'Rob', value: f.robustness_passed || 0, failed: 0 },
    { label: 'Pool', value: f.pool_added || 0, failed: fail.pool_reject },
    { label: 'Live', value: snapshot.live.live, failed: 0, highlight: true },
  ];

  return (
    <div className="card">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-semibold text-[var(--color-text-tertiary)] uppercase">
          Pipeline (24h)
        </h3>
        <Link to="/pipeline" className="text-xs text-[var(--color-accent)] hover:underline flex items-center gap-1">
          Details <ChevronRight size={14} />
        </Link>
      </div>
      <div className="flex items-end gap-1 overflow-x-auto pb-2">
        {stages.map((stage, i) => {
          const prevValue = i > 0 ? stages[i - 1].value : stage.value;
          const convRate = prevValue > 0 && i > 0 ? (stage.value / prevValue * 100) : 100;

          return (
            <div key={stage.label} className="flex flex-col items-center min-w-[42px]">
              <span className={`text-xs font-mono font-medium ${
                stage.highlight ? 'text-[var(--color-profit)]' : 'text-[var(--color-text-primary)]'
              }`}>
                {formatCompact(stage.value)}
              </span>
              {stage.failed > 0 && (
                <span className="text-[10px] text-[var(--color-loss)]">
                  -{formatCompact(stage.failed)}
                </span>
              )}
              <div className={`w-8 rounded-t transition-all ${
                stage.highlight ? 'bg-[var(--color-profit)]' : 'bg-[var(--color-accent)]'
              }`} style={{
                height: `${Math.max(4, Math.min(40, Math.log10(stage.value + 1) * 15))}px`
              }} />
              <span className="text-[10px] text-[var(--color-text-tertiary)] mt-1">
                {stage.label}
              </span>
              {i > 0 && convRate < 100 && (
                <span className={`text-[9px] ${convRate < 50 ? 'text-[var(--color-loss)]' : 'text-[var(--color-text-tertiary)]'}`}>
                  {convRate.toFixed(0)}%
                </span>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

// Quick Stats Row
function QuickStats({ snapshot, services }: { snapshot: MetricsSnapshotResponse; services: ServiceInfo[] }) {
  const pool = snapshot.pool;
  const poolUtilization = pool.limit > 0 ? (pool.size / pool.limit) * 100 : 0;
  const servicesOk = services.filter(s => s.status === 'RUNNING').length;

  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
      <div className="card py-3">
        <p className="text-xs text-[var(--color-text-tertiary)]">Pool</p>
        <p className="text-lg font-mono font-medium text-[var(--color-text-primary)]">
          {pool.size}/{pool.limit}
        </p>
        <div className="w-full h-1.5 bg-[var(--color-bg-tertiary)] rounded-full mt-1">
          <div className="h-full bg-[var(--color-accent)] rounded-full" style={{ width: `${poolUtilization}%` }} />
        </div>
      </div>
      <div className="card py-3">
        <p className="text-xs text-[var(--color-text-tertiary)]">Avg Sharpe</p>
        <p className="text-lg font-mono font-medium text-[var(--color-text-primary)]">
          {pool.quality.sharpe_avg?.toFixed(1) || '--'}
        </p>
      </div>
      <div className="card py-3">
        <p className="text-xs text-[var(--color-text-tertiary)]">Win Rate</p>
        <p className="text-lg font-mono font-medium text-[var(--color-text-primary)]">
          {pool.quality.winrate_avg ? `${(pool.quality.winrate_avg * 100).toFixed(0)}%` : '--'}
        </p>
      </div>
      <div className="card py-3">
        <p className="text-xs text-[var(--color-text-tertiary)]">Services</p>
        <p className={`text-lg font-mono font-medium ${
          servicesOk === services.length ? 'text-[var(--color-profit)]' : 'text-[var(--color-warning)]'
        }`}>
          {servicesOk}/{services.length}
        </p>
      </div>
    </div>
  );
}

// Subaccounts Summary - Compact
function SubaccountsSummary({ subaccounts }: { subaccounts: SnapshotSubaccount[] }) {
  const active = subaccounts.filter(s => s.strategy_name);

  if (active.length === 0) {
    return (
      <div className="card">
        <h3 className="text-sm font-semibold text-[var(--color-text-tertiary)] uppercase mb-3">
          Live Subaccounts
        </h3>
        <p className="text-sm text-[var(--color-text-tertiary)] text-center py-4">
          No active subaccounts
        </p>
      </div>
    );
  }

  return (
    <div className="card">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-semibold text-[var(--color-text-tertiary)] uppercase">
          Live Subaccounts ({active.length})
        </h3>
        <Link to="/trading" className="text-xs text-[var(--color-accent)] hover:underline flex items-center gap-1">
          View all <ChevronRight size={14} />
        </Link>
      </div>
      <div className="space-y-2">
        {active.map((sub) => (
          <div
            key={sub.id}
            className="flex items-center justify-between px-3 py-2 bg-[var(--color-bg-secondary)] rounded-lg"
          >
            <div className="flex items-center gap-2 min-w-0">
              <span className="text-xs font-mono text-[var(--color-text-tertiary)]">#{sub.id}</span>
              <span className="text-sm font-mono text-[var(--color-text-secondary)] truncate max-w-[120px]">
                {sub.strategy_name?.split('_').slice(-1)[0]}
              </span>
              <span className="text-xs text-[var(--color-text-tertiary)]">
                {sub.timeframe}/{sub.direction?.[0]}
              </span>
            </div>
            <div className="flex items-center gap-3">
              {sub.positions > 0 && (
                <span className="text-xs px-1.5 py-0.5 bg-[var(--color-accent)]/10 text-[var(--color-accent)] rounded">
                  {sub.positions} pos
                </span>
              )}
              <span className={`text-sm font-mono font-medium ${
                sub.rpnl + sub.upnl >= 0 ? 'text-[var(--color-profit)]' : 'text-[var(--color-loss)]'
              }`}>
                {formatPnl(sub.rpnl + sub.upnl)}
              </span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// Capital Card
function CapitalCard({ capital }: { capital: { total: number; main_account: number; subaccounts: number } }) {
  const deployedPct = capital.total > 0 ? (capital.subaccounts / capital.total) * 100 : 0;

  return (
    <div className="card">
      <h3 className="text-sm font-semibold text-[var(--color-text-tertiary)] uppercase mb-3">
        Capital
      </h3>
      <div className="text-center mb-3">
        <p className="text-2xl font-bold text-[var(--color-text-primary)]">{formatUsd(capital.total)}</p>
        <p className="text-xs text-[var(--color-text-tertiary)]">Total</p>
      </div>
      <div className="h-2 bg-[var(--color-bg-tertiary)] rounded-full overflow-hidden mb-3">
        <div className="h-full bg-[var(--color-accent)] rounded-full" style={{ width: `${deployedPct}%` }} />
      </div>
      <div className="grid grid-cols-2 gap-2 text-center text-sm">
        <div className="p-2 bg-[var(--color-bg-secondary)] rounded">
          <p className="font-mono text-[var(--color-text-primary)]">{formatUsd(capital.main_account)}</p>
          <p className="text-xs text-[var(--color-text-tertiary)]">Reserve</p>
        </div>
        <div className="p-2 bg-[var(--color-accent)]/10 rounded">
          <p className="font-mono text-[var(--color-accent)]">{formatUsd(capital.subaccounts)}</p>
          <p className="text-xs text-[var(--color-text-tertiary)]">Deployed</p>
        </div>
      </div>
    </div>
  );
}

// === Main Page ===

export default function Overview() {
  const { data: status, isLoading: statusLoading, error: statusError } = useStatus();
  const { data: snapshot, isLoading: snapshotLoading } = useMetricsSnapshot();

  if (statusLoading || snapshotLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Activity className="w-8 h-8 animate-spin text-[var(--color-text-tertiary)]" />
      </div>
    );
  }

  if (statusError) {
    return (
      <div className="card border-[var(--color-loss)]/20">
        <div className="text-center py-8">
          <p className="text-[var(--color-loss)] font-medium">Failed to connect to API</p>
          <p className="text-sm text-[var(--color-text-tertiary)] mt-2">
            Make sure the backend is running on port 8080
          </p>
        </div>
      </div>
    );
  }

  if (!status || !snapshot) return null;

  return (
    <div className="space-y-4">
      {/* Header with Status */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
        <h1 className="text-2xl font-bold text-[var(--color-text-primary)]">Overview</h1>
        <StatusBadge mode={snapshot.trading_mode} status={snapshot.status} />
      </div>

      {/* P&L Hero - The most important section */}
      <PnlHero snapshot={snapshot} />

      {/* Quick Stats Row */}
      <QuickStats snapshot={snapshot} services={status.services} />

      {/* Two Column Layout */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        {/* Left: Equity + Pipeline */}
        <div className="lg:col-span-2 space-y-4">
          <EquityCurve />
          <MiniPipeline snapshot={snapshot} />
        </div>

        {/* Right: Capital + Subaccounts */}
        <div className="space-y-4">
          <CapitalCard capital={snapshot.capital} />
          <SubaccountsSummary subaccounts={snapshot.subaccounts} />
        </div>
      </div>
    </div>
  );
}
