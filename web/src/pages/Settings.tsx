import { useState } from 'react';
import { useServices, useServiceControl, useConfig, useThresholds } from '../hooks/useApi';
import type { ServiceInfo } from '../types';
import {
  Activity,
  Play,
  Square,
  RotateCcw,
  Settings as SettingsIcon,
  AlertTriangle,
} from 'lucide-react';

// Service Card with Controls
function ServiceControl({ service }: { service: ServiceInfo }) {
  const { mutate: controlService, isPending } = useServiceControl();

  const statusColor =
    service.status === 'RUNNING'
      ? 'text-profit'
      : service.status === 'STOPPED'
      ? 'text-muted'
      : 'text-loss';

  const dotClass =
    service.status === 'RUNNING' ? 'bg-profit status-running' : 'bg-muted';

  const handleAction = (action: 'start' | 'stop' | 'restart') => {
    controlService({ name: service.name, action });
  };

  return (
    <div className="bg-card border border-terminal rounded-md p-4">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-3">
          <span className={`w-3 h-3 rounded-full ${dotClass}`} />
          <span className="font-semibold">{service.name}</span>
        </div>
        <span className={`text-sm ${statusColor}`}>{service.status}</span>
      </div>

      <div className="flex items-center gap-2">
        {service.status !== 'RUNNING' && (
          <button
            onClick={() => handleAction('start')}
            disabled={isPending}
            className="flex items-center gap-1 px-3 py-1.5 bg-profit/20 hover:bg-profit/30 text-profit rounded text-sm disabled:opacity-50"
          >
            <Play className="w-3 h-3" />
            Start
          </button>
        )}

        {service.status === 'RUNNING' && (
          <>
            <button
              onClick={() => handleAction('stop')}
              disabled={isPending}
              className="flex items-center gap-1 px-3 py-1.5 bg-loss/20 hover:bg-loss/30 text-loss rounded text-sm disabled:opacity-50"
            >
              <Square className="w-3 h-3" />
              Stop
            </button>
            <button
              onClick={() => handleAction('restart')}
              disabled={isPending}
              className="flex items-center gap-1 px-3 py-1.5 bg-card border border-terminal hover:bg-white/5 rounded text-sm disabled:opacity-50"
            >
              <RotateCcw className="w-3 h-3" />
              Restart
            </button>
          </>
        )}

        {isPending && (
          <Activity className="w-4 h-4 animate-spin text-muted ml-2" />
        )}
      </div>

      {service.pid && (
        <div className="text-xs text-muted mt-2">PID: {service.pid}</div>
      )}
    </div>
  );
}

// Thresholds Display
function ThresholdsSection() {
  const { data: thresholds, isLoading } = useThresholds();

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-32">
        <Activity className="w-6 h-6 animate-spin text-muted" />
      </div>
    );
  }

  if (!thresholds) return null;

  return (
    <div className="bg-card border border-terminal rounded-md p-4">
      <h3 className="text-sm font-semibold text-muted uppercase mb-4">
        System Thresholds
      </h3>

      <div className="grid grid-cols-3 gap-6">
        {/* Backtest */}
        <div>
          <h4 className="text-xs text-muted uppercase mb-2">Backtest</h4>
          <div className="space-y-2 text-sm">
            <div className="flex justify-between">
              <span className="text-muted">Min Sharpe</span>
              <span className="font-mono">
                {String(thresholds.backtest?.min_sharpe ?? '--')}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted">Min Win Rate</span>
              <span className="font-mono">
                {thresholds.backtest?.min_win_rate
                  ? `${(thresholds.backtest.min_win_rate as number * 100).toFixed(0)}%`
                  : '--'}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted">Max Drawdown</span>
              <span className="font-mono">
                {thresholds.backtest?.max_drawdown
                  ? `${(thresholds.backtest.max_drawdown as number * 100).toFixed(0)}%`
                  : '--'}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted">Min Trades</span>
              <span className="font-mono">
                {String(thresholds.backtest?.min_trades ?? '--')}
              </span>
            </div>
          </div>
        </div>

        {/* Risk */}
        <div>
          <h4 className="text-xs text-muted uppercase mb-2">Risk</h4>
          <div className="space-y-2 text-sm">
            <div className="flex justify-between">
              <span className="text-muted">Risk/Trade</span>
              <span className="font-mono">
                {thresholds.risk?.risk_per_trade_pct
                  ? `${(thresholds.risk.risk_per_trade_pct as number * 100).toFixed(1)}%`
                  : '--'}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted">Max Position</span>
              <span className="font-mono">
                {thresholds.risk?.max_position_size_pct
                  ? `${(thresholds.risk.max_position_size_pct as number * 100).toFixed(0)}%`
                  : '--'}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted">Max Positions</span>
              <span className="font-mono">
                {String(thresholds.risk?.max_open_positions ?? '--')}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted">Max Leverage</span>
              <span className="font-mono">
                {String(thresholds.risk?.max_leverage ?? '--')}x
              </span>
            </div>
          </div>
        </div>

        {/* Emergency */}
        <div>
          <h4 className="text-xs text-muted uppercase mb-2">Emergency</h4>
          <div className="space-y-2 text-sm">
            <div className="flex justify-between">
              <span className="text-muted">Portfolio DD</span>
              <span className="font-mono text-loss">
                {thresholds.emergency?.max_portfolio_drawdown
                  ? `${(thresholds.emergency.max_portfolio_drawdown as number * 100).toFixed(0)}%`
                  : '--'}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted">Subaccount DD</span>
              <span className="font-mono text-loss">
                {thresholds.emergency?.max_subaccount_drawdown
                  ? `${(thresholds.emergency.max_subaccount_drawdown as number * 100).toFixed(0)}%`
                  : '--'}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-muted">Daily Loss</span>
              <span className="font-mono text-loss">
                {thresholds.emergency?.max_daily_loss
                  ? `${(thresholds.emergency.max_daily_loss as number * 100).toFixed(0)}%`
                  : '--'}
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

// Config Viewer
function ConfigViewer() {
  const { data, isLoading } = useConfig();

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Activity className="w-6 h-6 animate-spin text-muted" />
      </div>
    );
  }

  return (
    <div className="bg-card border border-terminal rounded-md p-4">
      <h3 className="text-sm font-semibold text-muted uppercase mb-4">
        Configuration (Read-Only)
      </h3>
      <div className="bg-background rounded p-4 max-h-96 overflow-auto">
        <pre className="text-xs font-mono whitespace-pre-wrap">
          {JSON.stringify(data?.config || {}, null, 2)}
        </pre>
      </div>
    </div>
  );
}

// Main Settings Page
export function Settings() {
  const { data: services, isLoading: servicesLoading } = useServices();
  const [activeTab, setActiveTab] = useState<'services' | 'config'>('services');

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-3">
        <SettingsIcon className="w-6 h-6 text-muted" />
        <div>
          <h1 className="text-2xl font-bold">Settings</h1>
          <p className="text-sm text-muted mt-1">System configuration and controls</p>
        </div>
      </div>

      {/* Warning */}
      <div className="flex items-center gap-3 p-4 bg-warning/20 border border-warning rounded-md">
        <AlertTriangle className="w-5 h-5 text-warning flex-shrink-0" />
        <p className="text-sm text-warning">
          Service controls affect live trading. Use with caution.
        </p>
      </div>

      {/* Tabs */}
      <div className="flex gap-4 border-b border-terminal">
        <button
          onClick={() => setActiveTab('services')}
          className={`px-4 py-2 text-sm border-b-2 transition-colors ${
            activeTab === 'services'
              ? 'border-profit text-profit'
              : 'border-transparent text-muted hover:text-foreground'
          }`}
        >
          Services
        </button>
        <button
          onClick={() => setActiveTab('config')}
          className={`px-4 py-2 text-sm border-b-2 transition-colors ${
            activeTab === 'config'
              ? 'border-profit text-profit'
              : 'border-transparent text-muted hover:text-foreground'
          }`}
        >
          Configuration
        </button>
      </div>

      {/* Services Tab */}
      {activeTab === 'services' && (
        <div className="space-y-6">
          {/* Services Grid */}
          <div>
            <h2 className="text-lg font-semibold mb-4">Service Control</h2>
            {servicesLoading ? (
              <div className="flex items-center justify-center h-32">
                <Activity className="w-6 h-6 animate-spin text-muted" />
              </div>
            ) : (
              <div className="grid grid-cols-4 gap-4">
                {services?.map((service) => (
                  <ServiceControl key={service.name} service={service} />
                ))}
              </div>
            )}
          </div>

          {/* Thresholds */}
          <ThresholdsSection />
        </div>
      )}

      {/* Config Tab */}
      {activeTab === 'config' && <ConfigViewer />}
    </div>
  );
}
