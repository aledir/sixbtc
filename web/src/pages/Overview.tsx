import { useStatus } from '../hooks/useApi';
import type { ServiceInfo, PipelineCounts, PortfolioSummary, Alert } from '../types';
import { AlertTriangle, Activity, Clock } from 'lucide-react';

// Pipeline stage colors
const PIPELINE_COLORS: Record<string, string> = {
  GENERATED: '#6b7280', // gray
  VALIDATED: '#3b82f6', // blue
  TESTED: '#8b5cf6',    // purple
  SELECTED: '#f59e0b',  // amber
  LIVE: '#10b981',      // green
};

// Pipeline order for display
const PIPELINE_ORDER = ['GENERATED', 'VALIDATED', 'TESTED', 'SELECTED', 'LIVE'];

function formatUptime(seconds: number | null): string {
  if (!seconds) return '--';
  const hours = Math.floor(seconds / 3600);
  const mins = Math.floor((seconds % 3600) / 60);
  if (hours > 0) return `${hours}h ${mins}m`;
  return `${mins}m`;
}

function formatPnl(value: number): string {
  const sign = value >= 0 ? '+' : '';
  return `${sign}$${Math.abs(value).toFixed(2)}`;
}

function formatPct(value: number): string {
  const sign = value >= 0 ? '+' : '';
  return `${sign}${value.toFixed(2)}%`;
}

// Service Status Card
function ServiceCard({ service }: { service: ServiceInfo }) {
  const statusColor =
    service.status === 'RUNNING'
      ? 'text-profit'
      : service.status === 'STOPPED'
      ? 'text-muted'
      : 'text-loss';

  const dotClass =
    service.status === 'RUNNING' ? 'bg-profit status-running' : 'bg-muted';

  return (
    <div className="bg-card border border-terminal rounded-md p-3">
      <div className="flex items-center justify-between mb-1">
        <span className="text-sm font-medium">{service.name}</span>
        <span className={`w-2 h-2 rounded-full ${dotClass}`} />
      </div>
      <div className={`text-xs ${statusColor}`}>{service.status}</div>
      {service.uptime_seconds && (
        <div className="text-xs text-muted mt-1">
          {formatUptime(service.uptime_seconds)}
        </div>
      )}
    </div>
  );
}

// Services Grid
function ServicesGrid({ services }: { services: ServiceInfo[] }) {
  return (
    <div className="bg-card border border-terminal rounded-md p-4">
      <h3 className="text-sm font-semibold mb-4 text-muted uppercase">Services</h3>
      <div className="grid grid-cols-4 gap-3">
        {services.map((service) => (
          <ServiceCard key={service.name} service={service} />
        ))}
      </div>
    </div>
  );
}

// Pipeline Funnel
function PipelineFunnel({ pipeline }: { pipeline: PipelineCounts }) {
  const maxCount = Math.max(...PIPELINE_ORDER.map((k) => pipeline[k as keyof PipelineCounts] || 0), 1);

  return (
    <div className="bg-card border border-terminal rounded-md p-4">
      <h3 className="text-sm font-semibold mb-4 text-muted uppercase">Pipeline Status</h3>
      <div className="space-y-3">
        {PIPELINE_ORDER.map((stage, idx) => {
          const count = pipeline[stage as keyof PipelineCounts] || 0;
          const width = (count / maxCount) * 100;
          const color = PIPELINE_COLORS[stage];

          return (
            <div key={stage}>
              <div className="flex items-center justify-between text-xs mb-1">
                <span className="text-muted">{stage}</span>
                <span className="font-mono">{count}</span>
              </div>
              <div className="h-4 bg-background rounded overflow-hidden">
                <div
                  className="h-full rounded transition-all duration-500"
                  style={{ width: `${Math.max(width, 2)}%`, backgroundColor: color }}
                />
              </div>
              {idx < PIPELINE_ORDER.length - 1 && (
                <div className="text-center text-muted text-xs my-1">↓</div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

// PnL Card
function PnLCard({ portfolio }: { portfolio: PortfolioSummary }) {
  return (
    <div className="bg-card border border-terminal rounded-md p-4">
      <h3 className="text-sm font-semibold mb-4 text-muted uppercase">Portfolio Performance</h3>

      <div className="grid grid-cols-3 gap-4">
        {/* Total PnL */}
        <div>
          <div className="text-xs text-muted mb-1">Total PnL</div>
          <div
            className={`text-xl font-bold ${
              portfolio.total_pnl >= 0 ? 'text-profit' : 'text-loss'
            }`}
          >
            {formatPnl(portfolio.total_pnl)}
          </div>
          <div
            className={`text-xs ${
              portfolio.total_pnl_pct >= 0 ? 'text-profit' : 'text-loss'
            }`}
          >
            {formatPct(portfolio.total_pnl_pct)}
          </div>
        </div>

        {/* 24h PnL */}
        <div>
          <div className="text-xs text-muted mb-1">24h</div>
          <div
            className={`text-xl font-bold ${
              portfolio.pnl_24h >= 0 ? 'text-profit' : 'text-loss'
            }`}
          >
            {formatPnl(portfolio.pnl_24h)}
          </div>
          <div
            className={`text-xs ${
              portfolio.pnl_24h_pct >= 0 ? 'text-profit' : 'text-loss'
            }`}
          >
            {formatPct(portfolio.pnl_24h_pct)}
          </div>
        </div>

        {/* 7d PnL */}
        <div>
          <div className="text-xs text-muted mb-1">7d</div>
          <div
            className={`text-xl font-bold ${
              portfolio.pnl_7d >= 0 ? 'text-profit' : 'text-loss'
            }`}
          >
            {formatPnl(portfolio.pnl_7d)}
          </div>
          <div
            className={`text-xs ${portfolio.pnl_7d_pct >= 0 ? 'text-profit' : 'text-loss'}`}
          >
            {formatPct(portfolio.pnl_7d_pct)}
          </div>
        </div>
      </div>

      {/* Quick Stats */}
      <div className="mt-4 pt-4 border-t border-terminal grid grid-cols-3 gap-4 text-center">
        <div>
          <div className="text-lg font-bold">{portfolio.open_positions}</div>
          <div className="text-xs text-muted">Open Positions</div>
        </div>
        <div>
          <div className="text-lg font-bold">{portfolio.trades_today}</div>
          <div className="text-xs text-muted">Trades Today</div>
        </div>
        <div>
          <div className="text-lg font-bold text-loss">
            {(portfolio.max_drawdown * 100).toFixed(1)}%
          </div>
          <div className="text-xs text-muted">Max Drawdown</div>
        </div>
      </div>
    </div>
  );
}

// Alerts Banner
function AlertsBanner({ alerts }: { alerts: Alert[] }) {
  if (alerts.length === 0) return null;

  return (
    <div className="space-y-2">
      {alerts.map((alert, idx) => {
        const bgColor =
          alert.level === 'error'
            ? 'bg-loss/20 border-loss'
            : alert.level === 'warning'
            ? 'bg-warning/20 border-warning'
            : 'bg-blue-500/20 border-blue-500';
        const textColor =
          alert.level === 'error'
            ? 'text-loss'
            : alert.level === 'warning'
            ? 'text-warning'
            : 'text-blue-400';

        return (
          <div
            key={idx}
            className={`flex items-center gap-3 px-4 py-2 rounded-md border ${bgColor}`}
          >
            <AlertTriangle className={`w-4 h-4 ${textColor}`} />
            <span className={`text-sm ${textColor}`}>{alert.message}</span>
          </div>
        );
      })}
    </div>
  );
}

// Main Overview Page
export function Overview() {
  const { data: status, isLoading, error } = useStatus();

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Activity className="w-8 h-8 animate-spin text-muted" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-loss/20 border border-loss rounded-md p-4 text-loss">
        <div className="flex items-center gap-2">
          <AlertTriangle className="w-5 h-5" />
          <span>Failed to load status: {(error as Error).message}</span>
        </div>
      </div>
    );
  }

  if (!status) return null;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">System Overview</h1>
          <p className="text-sm text-muted flex items-center gap-2 mt-1">
            <Clock className="w-4 h-4" />
            Uptime: {formatUptime(status.uptime_seconds)}
          </p>
        </div>
      </div>

      {/* Alerts */}
      <AlertsBanner alerts={status.alerts} />

      {/* Main Grid */}
      <div className="grid grid-cols-2 gap-6">
        {/* Left Column */}
        <div className="space-y-6">
          <PipelineFunnel pipeline={status.pipeline} />
          <ServicesGrid services={status.services} />
        </div>

        {/* Right Column */}
        <div>
          <PnLCard portfolio={status.portfolio} />
        </div>
      </div>
    </div>
  );
}
