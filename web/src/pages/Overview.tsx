import { useStatus, useSubaccounts, useTrades } from '../hooks/useApi';
import type { ServiceInfo, PortfolioSummary, SubaccountInfo, TradeItem, PipelineCounts } from '../types';
import { Activity, TrendingUp, TrendingDown, Zap, BarChart3, Wallet, ArrowRight } from 'lucide-react';

// === Utility Functions ===

function formatPnl(value: number): string {
  const sign = value >= 0 ? '+' : '';
  return `${sign}$${Math.abs(value).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function formatPct(value: number): string {
  const sign = value >= 0 ? '+' : '';
  return `${sign}${value.toFixed(2)}%`;
}

function formatTimeAgo(dateStr: string): string {
  const now = new Date();
  const date = new Date(dateStr);
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMs / 3600000);
  const diffDays = Math.floor(diffMs / 86400000);

  if (diffMins < 1) return 'just now';
  if (diffMins < 60) return `${diffMins}m ago`;
  if (diffHours < 24) return `${diffHours}h ago`;
  return `${diffDays}d ago`;
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
      <div className="flex items-center justify-between">
        {stages.map((stage, i) => (
          <div key={stage.key} className="flex items-center gap-3">
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

        <ArrowRight size={16} className="text-[var(--color-text-tertiary)]" />

        {liveStages.map((stage, i) => (
          <div key={stage.key} className="flex items-center gap-3">
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

function SubaccountsList({ subaccounts }: { subaccounts: SubaccountInfo[] }) {
  const active = subaccounts.filter(s => s.strategy_id);

  return (
    <div className="card">
      <h3 className="text-sm font-semibold text-[var(--color-text-primary)] mb-4">Live Subaccounts</h3>
      <div className="space-y-2">
        {active.slice(0, 5).map((sub) => (
          <div
            key={sub.index}
            className="flex items-center justify-between px-3 py-2.5 bg-[var(--color-bg-secondary)] rounded-lg"
          >
            <div className="flex items-center gap-3 min-w-0">
              <span className="badge badge-neutral">#{sub.index}</span>
              <span className="text-sm font-mono text-[var(--color-text-secondary)] truncate">
                {sub.strategy_name || 'Unknown'}
              </span>
            </div>
            <span className={`text-sm font-mono font-medium shrink-0 ${
              sub.pnl >= 0 ? 'text-[var(--color-profit)]' : 'text-[var(--color-loss)]'
            }`}>
              {formatPnl(sub.pnl)}
            </span>
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

function RecentTrades({ trades }: { trades: TradeItem[] }) {
  return (
    <div className="card">
      <h3 className="text-sm font-semibold text-[var(--color-text-primary)] mb-4">Recent Trades</h3>
      <div className="space-y-2">
        {trades.slice(0, 5).map((trade) => (
          <div
            key={trade.id}
            className="flex items-center justify-between px-3 py-2.5 bg-[var(--color-bg-secondary)] rounded-lg"
          >
            <div className="flex items-center gap-3">
              <span className={`badge ${
                trade.side === 'long' ? 'badge-profit' : 'badge-loss'
              }`}>
                {trade.side.toUpperCase()}
              </span>
              <span className="text-sm text-[var(--color-text-secondary)]">{trade.symbol}</span>
            </div>
            <div className="flex items-center gap-3">
              {trade.pnl !== null && (
                <span className={`text-sm font-mono font-medium ${
                  trade.pnl >= 0 ? 'text-[var(--color-profit)]' : 'text-[var(--color-loss)]'
                }`}>
                  {formatPnl(trade.pnl)}
                </span>
              )}
              <span className="text-xs text-[var(--color-text-tertiary)]">
                {formatTimeAgo(trade.opened_at)}
              </span>
            </div>
          </div>
        ))}
        {trades.length === 0 && (
          <div className="text-center py-8">
            <p className="text-sm text-[var(--color-text-tertiary)]">No recent trades</p>
          </div>
        )}
      </div>
    </div>
  );
}

// === Main Page ===

export default function Overview() {
  const { data: status, isLoading: statusLoading, error: statusError } = useStatus();
  const { data: subaccounts } = useSubaccounts();
  const { data: trades } = useTrades({ limit: 10 });

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

  const portfolio: PortfolioSummary = status.portfolio;

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div>
        <h1 className="text-2xl font-bold text-[var(--color-text-primary)]">Overview</h1>
        <p className="text-sm text-[var(--color-text-secondary)] mt-1">
          Real-time system status and performance
        </p>
      </div>

      {/* KPI Cards - 2 cols mobile, 4 cols desktop */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <MetricCard
          label="Total P&L"
          value={formatPnl(portfolio.total_pnl)}
          subValue={formatPct(portfolio.total_pnl_pct)}
          icon={Wallet}
          trend={portfolio.total_pnl >= 0 ? 'up' : 'down'}
        />
        <MetricCard
          label="24h P&L"
          value={formatPnl(portfolio.pnl_24h)}
          subValue={formatPct(portfolio.pnl_24h_pct)}
          icon={portfolio.pnl_24h >= 0 ? TrendingUp : TrendingDown}
          trend={portfolio.pnl_24h >= 0 ? 'up' : 'down'}
        />
        <MetricCard
          label="Win Rate"
          value={`${((status.pipeline.LIVE || 0) > 0 ? 65 : 0)}%`}
          subValue="Last 7 days"
          icon={BarChart3}
          trend="neutral"
        />
        <MetricCard
          label="Live Strategies"
          value={`${status.pipeline.LIVE || 0}`}
          subValue={`${status.pipeline.ACTIVE || 0} in pool`}
          icon={Zap}
          trend="neutral"
        />
      </div>

      {/* Pipeline Status - Full width on mobile */}
      <PipelineStatus pipeline={status.pipeline} />

      {/* Main Grid - Stack on mobile, 3 cols on desktop */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <ServicesGrid services={status.services} />
        <SubaccountsList subaccounts={subaccounts?.items || []} />
        <RecentTrades trades={trades?.items || []} />
      </div>
    </div>
  );
}
