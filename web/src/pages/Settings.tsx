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
      ? 'text-[var(--color-profit)]'
      : service.status === 'STOPPED'
      ? 'text-[var(--color-text-tertiary)]'
      : 'text-[var(--color-loss)]';

  const dotClass =
    service.status === 'RUNNING' ? 'bg-[var(--color-profit)] animate-pulse-slow' : 'bg-[var(--color-text-tertiary)]';

  const handleAction = (action: 'start' | 'stop' | 'restart') => {
    controlService({ name: service.name, action });
  };

  return (
    <div className="card">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-3">
          <span className={`w-3 h-3 rounded-full ${dotClass}`} />
          <span className="font-semibold text-[var(--color-text-primary)]">{service.name}</span>
        </div>
        <span className={`text-sm ${statusColor}`}>{service.status}</span>
      </div>

      <div className="flex items-center gap-2 flex-wrap">
        {service.status !== 'RUNNING' && (
          <button
            onClick={() => handleAction('start')}
            disabled={isPending}
            className="btn btn-primary flex items-center gap-1"
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
              className="btn bg-[var(--color-loss)]/20 text-[var(--color-loss)] hover:bg-[var(--color-loss)]/30 flex items-center gap-1"
            >
              <Square className="w-3 h-3" />
              Stop
            </button>
            <button
              onClick={() => handleAction('restart')}
              disabled={isPending}
              className="btn btn-ghost flex items-center gap-1"
            >
              <RotateCcw className="w-3 h-3" />
              Restart
            </button>
          </>
        )}

        {isPending && (
          <Activity className="w-4 h-4 animate-spin text-[var(--color-text-tertiary)] ml-2" />
        )}
      </div>

      {service.pid && (
        <div className="text-xs text-[var(--color-text-tertiary)] mt-2">PID: {service.pid}</div>
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
        <Activity className="w-6 h-6 animate-spin text-[var(--color-text-tertiary)]" />
      </div>
    );
  }

  if (!thresholds) return null;

  return (
    <div className="card">
      <h3 className="text-sm font-semibold text-[var(--color-text-tertiary)] uppercase mb-4">
        System Thresholds
      </h3>

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-6">
        {/* Backtest */}
        <div>
          <h4 className="text-xs text-[var(--color-text-tertiary)] uppercase mb-3">Backtest</h4>
          <div className="space-y-2 text-sm">
            <div className="flex justify-between">
              <span className="text-[var(--color-text-secondary)]">Min Sharpe</span>
              <span className="font-mono text-[var(--color-text-primary)]">
                {String(thresholds.backtest?.min_sharpe ?? '--')}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-[var(--color-text-secondary)]">Min Win Rate</span>
              <span className="font-mono text-[var(--color-text-primary)]">
                {thresholds.backtest?.min_win_rate
                  ? `${(thresholds.backtest.min_win_rate as number * 100).toFixed(0)}%`
                  : '--'}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-[var(--color-text-secondary)]">Max Drawdown</span>
              <span className="font-mono text-[var(--color-text-primary)]">
                {thresholds.backtest?.max_drawdown
                  ? `${(thresholds.backtest.max_drawdown as number * 100).toFixed(0)}%`
                  : '--'}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-[var(--color-text-secondary)]">Min Trades</span>
              <span className="font-mono text-[var(--color-text-primary)]">
                {String(thresholds.backtest?.min_trades ?? '--')}
              </span>
            </div>
          </div>
        </div>

        {/* Risk */}
        <div>
          <h4 className="text-xs text-[var(--color-text-tertiary)] uppercase mb-3">Risk</h4>
          <div className="space-y-2 text-sm">
            <div className="flex justify-between">
              <span className="text-[var(--color-text-secondary)]">Risk/Trade</span>
              <span className="font-mono text-[var(--color-text-primary)]">
                {thresholds.risk?.risk_per_trade_pct
                  ? `${(thresholds.risk.risk_per_trade_pct as number * 100).toFixed(1)}%`
                  : '--'}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-[var(--color-text-secondary)]">Max Position</span>
              <span className="font-mono text-[var(--color-text-primary)]">
                {thresholds.risk?.max_position_size_pct
                  ? `${(thresholds.risk.max_position_size_pct as number * 100).toFixed(0)}%`
                  : '--'}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-[var(--color-text-secondary)]">Max Positions</span>
              <span className="font-mono text-[var(--color-text-primary)]">
                {String(thresholds.risk?.max_open_positions ?? '--')}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-[var(--color-text-secondary)]">Max Leverage</span>
              <span className="font-mono text-[var(--color-text-primary)]">
                {thresholds.risk?.max_leverage
                  ? `${thresholds.risk.max_leverage}x`
                  : 'Per-coin'}
              </span>
            </div>
          </div>
        </div>

        {/* Emergency */}
        <div>
          <h4 className="text-xs text-[var(--color-text-tertiary)] uppercase mb-3">Emergency</h4>
          <div className="space-y-2 text-sm">
            <div className="flex justify-between">
              <span className="text-[var(--color-text-secondary)]">Portfolio DD</span>
              <span className="font-mono text-[var(--color-loss)]">
                {thresholds.emergency?.max_portfolio_drawdown
                  ? `${(thresholds.emergency.max_portfolio_drawdown as number * 100).toFixed(0)}%`
                  : '--'}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-[var(--color-text-secondary)]">Subaccount DD</span>
              <span className="font-mono text-[var(--color-loss)]">
                {thresholds.emergency?.max_subaccount_drawdown
                  ? `${(thresholds.emergency.max_subaccount_drawdown as number * 100).toFixed(0)}%`
                  : '--'}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-[var(--color-text-secondary)]">Daily Loss</span>
              <span className="font-mono text-[var(--color-loss)]">
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
        <Activity className="w-6 h-6 animate-spin text-[var(--color-text-tertiary)]" />
      </div>
    );
  }

  return (
    <div className="card">
      <h3 className="text-sm font-semibold text-[var(--color-text-tertiary)] uppercase mb-4">
        Configuration (Read-Only)
      </h3>
      <div className="bg-[var(--color-bg-secondary)] rounded-lg p-4 max-h-96 overflow-auto">
        <pre className="text-xs font-mono whitespace-pre-wrap text-[var(--color-text-secondary)]">
          {JSON.stringify(data?.config || {}, null, 2)}
        </pre>
      </div>
    </div>
  );
}

// Main Settings Page
export default function Settings() {
  const { data: services, isLoading: servicesLoading } = useServices();
  const [activeTab, setActiveTab] = useState<'services' | 'config'>('services');

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-3">
        <SettingsIcon className="w-6 h-6 text-[var(--color-text-tertiary)]" />
        <div>
          <h1 className="text-2xl font-bold text-[var(--color-text-primary)]">Settings</h1>
          <p className="text-sm text-[var(--color-text-secondary)] mt-1">System configuration and controls</p>
        </div>
      </div>

      {/* Warning */}
      <div className="flex items-center gap-3 p-4 bg-[var(--color-warning)]/10 border border-[var(--color-warning)]/30 rounded-lg">
        <AlertTriangle className="w-5 h-5 text-[var(--color-warning)] flex-shrink-0" />
        <p className="text-sm text-[var(--color-warning)]">
          Service controls affect live trading. Use with caution.
        </p>
      </div>

      {/* Tabs */}
      <div className="flex gap-4 border-b border-[var(--color-border-primary)]">
        <button
          onClick={() => setActiveTab('services')}
          className={`px-4 py-2 text-sm border-b-2 transition-colors ${
            activeTab === 'services'
              ? 'border-[var(--color-accent)] text-[var(--color-accent)]'
              : 'border-transparent text-[var(--color-text-tertiary)] hover:text-[var(--color-text-primary)]'
          }`}
        >
          Services
        </button>
        <button
          onClick={() => setActiveTab('config')}
          className={`px-4 py-2 text-sm border-b-2 transition-colors ${
            activeTab === 'config'
              ? 'border-[var(--color-accent)] text-[var(--color-accent)]'
              : 'border-transparent text-[var(--color-text-tertiary)] hover:text-[var(--color-text-primary)]'
          }`}
        >
          Configuration
        </button>
      </div>

      {/* Services Tab */}
      {activeTab === 'services' && (
        <div className="space-y-6">
          {/* Services Grid - 1 col mobile, 2 cols tablet, 4 cols desktop */}
          <div>
            <h2 className="text-lg font-semibold text-[var(--color-text-primary)] mb-4">Service Control</h2>
            {servicesLoading ? (
              <div className="flex items-center justify-center h-32">
                <Activity className="w-6 h-6 animate-spin text-[var(--color-text-tertiary)]" />
              </div>
            ) : (
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
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
