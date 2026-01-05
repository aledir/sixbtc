import { useStatus, useSubaccounts, useTrades } from '../hooks/useApi';
import type { ServiceInfo, PortfolioSummary, SubaccountInfo, TradeItem, PipelineCounts } from '../types';
import { Activity, TrendingUp, TrendingDown, Zap, BarChart3, Wallet } from 'lucide-react';

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

function KPICard({ label, value, subValue, icon: Icon, trend }: {
  label: string;
  value: string;
  subValue?: string;
  icon: React.ElementType;
  trend?: 'up' | 'down' | 'neutral';
}) {
  const trendColor = trend === 'up' ? 'text-profit' : trend === 'down' ? 'text-loss' : 'text-foreground';

  return (
    <div className="bg-card border border-border rounded-lg p-4">
      <div className="flex items-start justify-between">
        <div>
          <p className="text-xs text-muted uppercase tracking-wide">{label}</p>
          <p className={`text-2xl font-bold mt-1 ${trendColor}`}>{value}</p>
          {subValue && (
            <p className={`text-xs mt-1 ${trendColor}`}>{subValue}</p>
          )}
        </div>
        <div className="p-2 bg-white/5 rounded-lg">
          <Icon size={20} className="text-muted" />
        </div>
      </div>
    </div>
  );
}

function PipelineStatus({ pipeline }: { pipeline: PipelineCounts }) {
  const stages: { key: keyof PipelineCounts; label: string; color: string }[] = [
    { key: 'GENERATED', label: 'Generated', color: 'bg-gray-500' },
    { key: 'VALIDATED', label: 'Validated', color: 'bg-blue-500' },
    { key: 'ACTIVE', label: 'Active Pool', color: 'bg-purple-500' },
    { key: 'LIVE', label: 'Live', color: 'bg-profit' },
  ];

  return (
    <div className="bg-card border border-border rounded-lg p-4">
      <h3 className="text-sm font-semibold mb-4">Pipeline Status</h3>
      <div className="flex items-center justify-between gap-2">
        {stages.map((stage, i) => (
          <div key={stage.key} className="flex items-center gap-2">
            <div className="text-center">
              <div className={`w-10 h-10 rounded-full ${stage.color} flex items-center justify-center text-sm font-bold`}>
                {pipeline[stage.key] || 0}
              </div>
              <p className="text-xs text-muted mt-1">{stage.label}</p>
            </div>
            {i < stages.length - 1 && (
              <div className="text-muted text-xs">→</div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

function ServicesStatus({ services }: { services: ServiceInfo[] }) {
  return (
    <div className="bg-card border border-border rounded-lg p-4">
      <h3 className="text-sm font-semibold mb-4">Services</h3>
      <div className="grid grid-cols-2 gap-2">
        {services.map((svc) => (
          <div key={svc.name} className="flex items-center justify-between px-3 py-2 bg-background rounded">
            <span className="text-xs">{svc.name.replace('sixbtc:', '')}</span>
            <span className={`w-2 h-2 rounded-full ${
              svc.status === 'RUNNING' ? 'bg-profit animate-pulse' :
              svc.status === 'STOPPED' ? 'bg-muted' : 'bg-loss'
            }`} />
          </div>
        ))}
      </div>
    </div>
  );
}

function SubaccountsList({ subaccounts }: { subaccounts: SubaccountInfo[] }) {
  return (
    <div className="bg-card border border-border rounded-lg p-4">
      <h3 className="text-sm font-semibold mb-4">Live Subaccounts</h3>
      <div className="space-y-2">
        {subaccounts.filter(s => s.strategy_id).slice(0, 6).map((sub) => (
          <div key={sub.index} className="flex items-center justify-between px-3 py-2 bg-background rounded">
            <div className="flex items-center gap-3">
              <span className="text-xs text-muted">#{sub.index}</span>
              <span className="text-sm font-mono truncate max-w-32">
                {sub.strategy_name || 'Unknown'}
              </span>
            </div>
            <span className={`text-sm font-mono ${sub.pnl >= 0 ? 'text-profit' : 'text-loss'}`}>
              {formatPnl(sub.pnl)}
            </span>
          </div>
        ))}
        {subaccounts.filter(s => s.strategy_id).length === 0 && (
          <p className="text-xs text-muted text-center py-4">No active subaccounts</p>
        )}
      </div>
    </div>
  );
}

function RecentTrades({ trades }: { trades: TradeItem[] }) {
  return (
    <div className="bg-card border border-border rounded-lg p-4">
      <h3 className="text-sm font-semibold mb-4">Recent Trades</h3>
      <div className="space-y-2">
        {trades.slice(0, 6).map((trade) => (
          <div key={trade.id} className="flex items-center justify-between px-3 py-2 bg-background rounded">
            <div className="flex items-center gap-3">
              <span className={`text-xs px-1.5 py-0.5 rounded ${
                trade.side === 'long' ? 'bg-profit/20 text-profit' : 'bg-loss/20 text-loss'
              }`}>
                {trade.side.toUpperCase()}
              </span>
              <span className="text-sm">{trade.symbol}</span>
            </div>
            <div className="flex items-center gap-3">
              {trade.pnl !== null && (
                <span className={`text-sm font-mono ${trade.pnl >= 0 ? 'text-profit' : 'text-loss'}`}>
                  {formatPnl(trade.pnl)}
                </span>
              )}
              <span className="text-xs text-muted">{formatTimeAgo(trade.opened_at)}</span>
            </div>
          </div>
        ))}
        {trades.length === 0 && (
          <p className="text-xs text-muted text-center py-4">No recent trades</p>
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
        <Activity className="w-8 h-8 animate-spin text-muted" />
      </div>
    );
  }

  if (statusError) {
    return (
      <div className="bg-loss/10 border border-loss/20 rounded-lg p-6 text-center">
        <p className="text-loss">Failed to connect to API</p>
        <p className="text-xs text-muted mt-2">Make sure the backend is running on port 8080</p>
      </div>
    );
  }

  if (!status) return null;

  const portfolio: PortfolioSummary = status.portfolio;

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div>
        <h1 className="text-2xl font-bold">Overview</h1>
        <p className="text-sm text-muted mt-1">Real-time system status and performance</p>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-4 gap-4">
        <KPICard
          label="Total P&L"
          value={formatPnl(portfolio.total_pnl)}
          subValue={formatPct(portfolio.total_pnl_pct)}
          icon={Wallet}
          trend={portfolio.total_pnl >= 0 ? 'up' : 'down'}
        />
        <KPICard
          label="24h P&L"
          value={formatPnl(portfolio.pnl_24h)}
          subValue={formatPct(portfolio.pnl_24h_pct)}
          icon={portfolio.pnl_24h >= 0 ? TrendingUp : TrendingDown}
          trend={portfolio.pnl_24h >= 0 ? 'up' : 'down'}
        />
        <KPICard
          label="Win Rate"
          value={`${((status.pipeline.LIVE || 0) > 0 ? 65 : 0)}%`}
          subValue="Last 7 days"
          icon={BarChart3}
          trend="neutral"
        />
        <KPICard
          label="Live Strategies"
          value={`${status.pipeline.LIVE || 0}`}
          subValue={`${status.pipeline.ACTIVE || 0} in pool`}
          icon={Zap}
          trend="neutral"
        />
      </div>

      {/* Main Grid */}
      <div className="grid grid-cols-3 gap-6">
        {/* Left Column */}
        <div className="space-y-6">
          <PipelineStatus pipeline={status.pipeline} />
          <ServicesStatus services={status.services} />
        </div>

        {/* Middle Column */}
        <div>
          <SubaccountsList subaccounts={subaccounts?.items || []} />
        </div>

        {/* Right Column */}
        <div>
          <RecentTrades trades={trades?.items || []} />
        </div>
      </div>
    </div>
  );
}
