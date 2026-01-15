import { useStatus, useMetricsSnapshot, usePerformanceEquity } from '../hooks/useApi';
import type { ServiceInfo, PipelineCounts, SnapshotSubaccount } from '../types';
import {
  Activity,
  TrendingUp,
  TrendingDown,
  Zap,
  BarChart3,
  Wallet,
  ArrowRight,
  AlertTriangle,
  CheckCircle,
} from 'lucide-react';
import { useTheme } from '../contexts/ThemeContext';
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

// === Components ===

function MetricCard({ label, value, subValue, icon: Icon, trend }: {
  label: string;
  value: string;
  subValue?: string;
  icon: React.ElementType;
  trend?: 'up' | 'down' | 'neutral';
}) {
  const valueColor = trend === 'up'
    ? 'text-[var(--color-profit)]'
    : trend === 'down'
      ? 'text-[var(--color-loss)]'
      : 'text-[var(--color-text-primary)]';

  return (
    <div className="card">
      <div className="flex items-start justify-between">
        <div className="flex-1 min-w-0">
          <p className="metric-label">{label}</p>
          <p className={`metric-value ${valueColor}`}>{value}</p>
          {subValue && (
            <p className={`text-sm mt-1 ${valueColor}`}>{subValue}</p>
          )}
        </div>
        <div className="p-2.5 bg-[var(--color-bg-secondary)] rounded-lg shrink-0">
          <Icon size={20} className="text-[var(--color-text-tertiary)]" />
        </div>
      </div>
    </div>
  );
}

function TradingModeIndicator({ mode, status }: { mode: string; status: string }) {
  const isLive = mode === 'LIVE';
  const isHealthy = status === 'HEALTHY';

  return (
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
      {isHealthy ? (
        <CheckCircle className="w-4 h-4 text-[var(--color-profit)]" />
      ) : (
        <AlertTriangle className="w-4 h-4 text-[var(--color-warning)]" />
      )}
    </div>
  );
}

function EquityCurve() {
  const { theme } = useTheme();
  const { data: performanceData, isLoading } = usePerformanceEquity({ period: '7d' });

  const chartColors = {
    axis: theme === 'dark' ? '#64748b' : '#94a3b8',
    tooltip: {
      bg: theme === 'dark' ? '#1e293b' : '#ffffff',
      border: theme === 'dark' ? '#334155' : '#e2e8f0',
    },
    grid: theme === 'dark' ? '#334155' : '#e2e8f0',
  };

  if (isLoading) {
    return (
      <div className="card">
        <h3 className="text-sm font-semibold text-[var(--color-text-tertiary)] uppercase mb-4">
          Portfolio Equity (7d)
        </h3>
        <div className="h-48 flex items-center justify-center">
          <Activity className="w-6 h-6 animate-spin text-[var(--color-text-tertiary)]" />
        </div>
      </div>
    );
  }

  const equityData = performanceData?.data_points.map((point) => ({
    time: new Date(point.timestamp).toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
    }),
    equity: point.equity,
    pnl: point.total_pnl,
  })) || [];

  const startEquity = performanceData?.start_equity || 0;
  const currentReturn = performanceData?.total_return || 0;
  const maxDrawdown = performanceData?.max_drawdown || 0;

  return (
    <div className="card">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 mb-4">
        <h3 className="text-sm font-semibold text-[var(--color-text-tertiary)] uppercase">
          Portfolio Equity (7d)
        </h3>
        {performanceData && (
          <div className="flex gap-4 text-xs">
            <div>
              <span className="text-[var(--color-text-tertiary)]">Return: </span>
              <span className={`font-mono ${currentReturn >= 0 ? 'text-[var(--color-profit)]' : 'text-[var(--color-loss)]'}`}>
                {formatPct(currentReturn * 100)}
              </span>
            </div>
            <div>
              <span className="text-[var(--color-text-tertiary)]">Max DD: </span>
              <span className="font-mono text-[var(--color-loss)]">
                {formatPct(maxDrawdown * 100)}
              </span>
            </div>
          </div>
        )}
      </div>
      <div className="h-48">
        {equityData.length > 0 ? (
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
          <div className="flex items-center justify-center h-full text-[var(--color-text-tertiary)]">
            No equity data available
          </div>
        )}
      </div>
    </div>
  );
}

function CapitalBreakdown({ capital }: {
  capital: { total: number; main_account: number; subaccounts: number }
}) {
  const subPct = capital.total > 0 ? (capital.subaccounts / capital.total) * 100 : 0;

  return (
    <div className="card">
      <h3 className="text-sm font-semibold text-[var(--color-text-tertiary)] uppercase mb-4">
        Capital Allocation
      </h3>
      <div className="space-y-4">
        <div className="text-center">
          <p className="text-3xl font-bold text-[var(--color-text-primary)]">
            {formatUsd(capital.total)}
          </p>
          <p className="text-sm text-[var(--color-text-tertiary)]">Total Capital</p>
        </div>

        {/* Progress bar showing allocation */}
        <div className="h-3 bg-[var(--color-bg-secondary)] rounded-full overflow-hidden">
          <div
            className="h-full bg-[var(--color-accent)] rounded-full transition-all"
            style={{ width: `${subPct}%` }}
          />
        </div>

        <div className="grid grid-cols-2 gap-4 text-sm">
          <div className="text-center p-3 bg-[var(--color-bg-secondary)] rounded-lg">
            <p className="font-mono font-medium text-[var(--color-text-primary)]">
              {formatUsd(capital.main_account)}
            </p>
            <p className="text-xs text-[var(--color-text-tertiary)]">Main Account</p>
          </div>
          <div className="text-center p-3 bg-[var(--color-accent)]/10 rounded-lg">
            <p className="font-mono font-medium text-[var(--color-accent)]">
              {formatUsd(capital.subaccounts)}
            </p>
            <p className="text-xs text-[var(--color-text-tertiary)]">Deployed ({subPct.toFixed(0)}%)</p>
          </div>
        </div>
      </div>
    </div>
  );
}

function PipelineStatus({ pipeline }: { pipeline: PipelineCounts }) {
  const stages = [
    { key: 'GENERATED' as const, label: 'Generated', color: 'bg-slate-400' },
    { key: 'VALIDATED' as const, label: 'Validated', color: 'bg-[var(--color-accent)]' },
  ];

  const liveStages = [
    { key: 'ACTIVE' as const, label: 'Active Pool', color: 'bg-violet-500' },
    { key: 'LIVE' as const, label: 'Live', color: 'bg-[var(--color-profit)]' },
  ];

  return (
    <div className="card">
      <h3 className="text-sm font-semibold text-[var(--color-text-primary)] mb-4">Pipeline Status</h3>
      <div className="flex items-center justify-between overflow-x-auto">
        {stages.map((stage, i) => (
          <div key={stage.key} className="flex items-center gap-3 shrink-0">
            <div className="text-center">
              <div className={`w-12 h-12 rounded-full ${stage.color} flex items-center justify-center text-white font-bold`}>
                {pipeline[stage.key] || 0}
              </div>
              <p className="text-xs text-[var(--color-text-tertiary)] mt-2">{stage.label}</p>
            </div>
            {i < stages.length - 1 && (
              <ArrowRight size={16} className="text-[var(--color-text-tertiary)]" />
            )}
          </div>
        ))}

        <ArrowRight size={16} className="text-[var(--color-text-tertiary)] shrink-0" />

        {liveStages.map((stage, i) => (
          <div key={stage.key} className="flex items-center gap-3 shrink-0">
            <div className="text-center">
              <div className={`w-12 h-12 rounded-full ${stage.color} flex items-center justify-center text-white font-bold`}>
                {pipeline[stage.key] || 0}
              </div>
              <p className="text-xs text-[var(--color-text-tertiary)] mt-2">{stage.label}</p>
            </div>
            {i < liveStages.length - 1 && (
              <ArrowRight size={16} className="text-[var(--color-text-tertiary)]" />
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

function ServicesGrid({ services }: { services: ServiceInfo[] }) {
  return (
    <div className="card">
      <h3 className="text-sm font-semibold text-[var(--color-text-primary)] mb-4">Services</h3>
      <div className="grid grid-cols-2 gap-2">
        {services.map((svc) => (
          <div
            key={svc.name}
            className="flex items-center justify-between px-3 py-2.5 bg-[var(--color-bg-secondary)] rounded-lg"
          >
            <span className="text-sm text-[var(--color-text-secondary)]">
              {svc.name.replace('sixbtc:', '')}
            </span>
            <span className={`w-2.5 h-2.5 rounded-full ${
              svc.status === 'RUNNING' ? 'bg-[var(--color-profit)] animate-pulse-slow' :
              svc.status === 'STOPPED' ? 'bg-[var(--color-text-tertiary)]' : 'bg-[var(--color-loss)]'
            }`} />
          </div>
        ))}
      </div>
    </div>
  );
}

function SubaccountsList({ subaccounts }: { subaccounts: SnapshotSubaccount[] }) {
  const active = subaccounts.filter(s => s.strategy_name);

  return (
    <div className="card">
      <h3 className="text-sm font-semibold text-[var(--color-text-primary)] mb-4">
        Live Subaccounts ({active.length})
      </h3>
      <div className="space-y-2">
        {active.map((sub) => (
          <div
            key={sub.id}
            className="px-3 py-2.5 bg-[var(--color-bg-secondary)] rounded-lg"
          >
            <div className="flex items-center justify-between mb-1">
              <div className="flex items-center gap-2 min-w-0">
                <span className="badge badge-neutral">#{sub.id}</span>
                <span className="text-sm font-mono text-[var(--color-text-secondary)] truncate">
                  {sub.strategy_name}
                </span>
              </div>
              <span className={`text-sm font-mono font-medium shrink-0 ${
                sub.rpnl >= 0 ? 'text-[var(--color-profit)]' : 'text-[var(--color-loss)]'
              }`}>
                {formatPnl(sub.rpnl)}
              </span>
            </div>
            <div className="flex items-center gap-4 text-xs text-[var(--color-text-tertiary)]">
              <span>{sub.timeframe}/{sub.direction?.[0] || '?'}</span>
              <span>DD: {sub.dd_pct.toFixed(0)}%</span>
              <span>WR: {sub.wr_pct.toFixed(0)}%</span>
              <span>Pos: {sub.positions}</span>
              <span className="ml-auto">{formatUsd(sub.balance)}</span>
            </div>
          </div>
        ))}
        {active.length === 0 && (
          <div className="text-center py-8">
            <p className="text-sm text-[var(--color-text-tertiary)]">No active subaccounts</p>
          </div>
        )}
      </div>
    </div>
  );
}

function PoolQuality({ pool }: {
  pool: {
    size: number;
    limit: number;
    quality: {
      sharpe_avg: number | null;
      winrate_avg: number | null;
      dd_avg: number | null;
    }
  }
}) {
  const utilization = pool.limit > 0 ? (pool.size / pool.limit) * 100 : 0;

  return (
    <div className="card">
      <h3 className="text-sm font-semibold text-[var(--color-text-tertiary)] uppercase mb-4">
        Active Pool Quality
      </h3>
      <div className="space-y-4">
        {/* Pool size with progress bar */}
        <div>
          <div className="flex justify-between text-sm mb-1">
            <span className="text-[var(--color-text-secondary)]">Pool Size</span>
            <span className="font-mono text-[var(--color-text-primary)]">{pool.size}/{pool.limit}</span>
          </div>
          <div className="h-2 bg-[var(--color-bg-secondary)] rounded-full overflow-hidden">
            <div
              className={`h-full rounded-full transition-all ${
                utilization > 90 ? 'bg-[var(--color-loss)]' :
                utilization > 70 ? 'bg-[var(--color-warning)]' :
                'bg-[var(--color-profit)]'
              }`}
              style={{ width: `${utilization}%` }}
            />
          </div>
        </div>

        {/* Quality metrics */}
        <div className="grid grid-cols-3 gap-3 text-center">
          <div className="p-2 bg-[var(--color-bg-secondary)] rounded-lg">
            <p className="text-lg font-mono font-medium text-[var(--color-text-primary)]">
              {pool.quality.sharpe_avg?.toFixed(1) || '--'}
            </p>
            <p className="text-xs text-[var(--color-text-tertiary)]">Avg Sharpe</p>
          </div>
          <div className="p-2 bg-[var(--color-bg-secondary)] rounded-lg">
            <p className="text-lg font-mono font-medium text-[var(--color-text-primary)]">
              {pool.quality.winrate_avg ? `${(pool.quality.winrate_avg * 100).toFixed(0)}%` : '--'}
            </p>
            <p className="text-xs text-[var(--color-text-tertiary)]">Avg Win Rate</p>
          </div>
          <div className="p-2 bg-[var(--color-bg-secondary)] rounded-lg">
            <p className="text-lg font-mono font-medium text-[var(--color-loss)]">
              {pool.quality.dd_avg ? `${(pool.quality.dd_avg * 100).toFixed(0)}%` : '--'}
            </p>
            <p className="text-xs text-[var(--color-text-tertiary)]">Avg DD</p>
          </div>
        </div>
      </div>
    </div>
  );
}

// === Main Page ===

export default function Overview() {
  const { data: status, isLoading: statusLoading, error: statusError } = useStatus();
  const { data: snapshot } = useMetricsSnapshot();

  if (statusLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Activity className="w-8 h-8 animate-spin text-[var(--color-text-tertiary)]" />
      </div>
    );
  }

  if (statusError) {
    return (
      <div className="card border-[var(--color-loss)]/20 bg-[var(--color-loss-bg)]">
        <div className="text-center py-8">
          <p className="text-[var(--color-loss)] font-medium">Failed to connect to API</p>
          <p className="text-sm text-[var(--color-text-tertiary)] mt-2">
            Make sure the backend is running on port 8080
          </p>
        </div>
      </div>
    );
  }

  if (!status) return null;

  // Calculate totals from snapshot subaccounts
  const totalRpnl = snapshot?.subaccounts.reduce((sum, s) => sum + s.rpnl, 0) || 0;
  const totalUpnl = snapshot?.subaccounts.reduce((sum, s) => sum + s.upnl, 0) || 0;
  const totalPnl = totalRpnl + totalUpnl;
  const capital = snapshot?.capital || { total: 0, main_account: 0, subaccounts: 0 };
  const pnlPct = capital.subaccounts > 0 ? (totalPnl / capital.subaccounts) * 100 : 0;

  // Pool quality metrics
  const poolQuality = snapshot?.pool.quality || { sharpe_avg: null, winrate_avg: null, dd_avg: null };
  const avgWinRate = poolQuality.winrate_avg;

  return (
    <div className="space-y-6">
      {/* Page Header with Trading Mode */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-[var(--color-text-primary)]">Overview</h1>
          <p className="text-sm text-[var(--color-text-secondary)] mt-1">
            Real-time system status and performance
          </p>
        </div>
        {snapshot && (
          <TradingModeIndicator
            mode={snapshot.trading_mode}
            status={snapshot.status}
          />
        )}
      </div>

      {/* KPI Cards - 2 cols mobile, 4 cols desktop */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <MetricCard
          label="Total P&L"
          value={formatPnl(totalPnl)}
          subValue={formatPct(pnlPct)}
          icon={Wallet}
          trend={totalPnl >= 0 ? 'up' : 'down'}
        />
        <MetricCard
          label="Unrealized P&L"
          value={formatPnl(totalUpnl)}
          subValue={`${snapshot?.subaccounts.filter(s => s.positions > 0).length || 0} positions`}
          icon={totalUpnl >= 0 ? TrendingUp : TrendingDown}
          trend={totalUpnl >= 0 ? 'up' : 'down'}
        />
        <MetricCard
          label="Pool Win Rate"
          value={avgWinRate ? `${(avgWinRate * 100).toFixed(0)}%` : '--'}
          subValue={`${snapshot?.pool.size || 0} strategies`}
          icon={BarChart3}
          trend={avgWinRate && avgWinRate >= 0.5 ? 'up' : 'neutral'}
        />
        <MetricCard
          label="Live Strategies"
          value={`${snapshot?.live.live || status.pipeline.LIVE || 0}`}
          subValue={`${snapshot?.pool.size || status.pipeline.ACTIVE || 0} in pool`}
          icon={Zap}
          trend="neutral"
        />
      </div>

      {/* Second Row: Equity Curve + Capital - 2 cols on desktop */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2">
          <EquityCurve />
        </div>
        {snapshot && (
          <CapitalBreakdown capital={snapshot.capital} />
        )}
      </div>

      {/* Pipeline Status - Full width */}
      <PipelineStatus pipeline={status.pipeline} />

      {/* Third Row: Services + Subaccounts + Pool Quality */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <ServicesGrid services={status.services} />
        <SubaccountsList subaccounts={snapshot?.subaccounts || []} />
        {snapshot && (
          <PoolQuality pool={snapshot.pool} />
        )}
      </div>
    </div>
  );
}
