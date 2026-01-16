import { useState, useEffect, useRef } from 'react';
import {
  useTaskExecutions,
  useCoinRegistryStats,
  usePairsUpdateHistory,
  useSchedulerHealth,
  useTriggerTask,
  useLogs,
  useServices,
  useServiceControl,
  useConfig,
  useThresholds,
  usePreflight,
  useApplyPreflightFixes,
} from '../hooks/useApi';
import type { ServiceInfo, LogLine, PreflightCheck, SubaccountPreflightStatus } from '../types';
import {
  AlertCircle,
  CheckCircle,
  Clock,
  Play,
  Activity,
  Download,
  Search,
  RefreshCw,
  Square,
  RotateCcw,
  Settings as SettingsIcon,
  AlertTriangle,
  Rocket,
  XCircle,
  Database,
  Zap,
} from 'lucide-react';

// === Types ===

type TabType = 'tasks' | 'logs' | 'settings' | 'golive';

const TABS: { id: TabType; label: string }[] = [
  { id: 'golive', label: 'Go Live' },
  { id: 'tasks', label: 'Tasks' },
  { id: 'logs', label: 'Logs' },
  { id: 'settings', label: 'Settings' },
];

// === Tasks Tab Components ===

function TaskStatusBadge({ status }: { status: string }) {
  const colors: Record<string, string> = {
    SUCCESS: 'badge-profit',
    FAILED: 'badge-loss',
    RUNNING: 'badge-warning',
  };

  const icons: Record<string, React.ReactNode> = {
    SUCCESS: <CheckCircle className="w-3 h-3" />,
    FAILED: <AlertCircle className="w-3 h-3" />,
    RUNNING: <Clock className="w-3 h-3" />,
  };

  return (
    <span
      className={`badge ${colors[status] || 'badge-neutral'} inline-flex items-center gap-1`}
    >
      {icons[status]}
      {status}
    </span>
  );
}

function TasksTab() {
  const [selectedTaskType, setSelectedTaskType] = useState<string | null>(null);

  const { data: health } = useSchedulerHealth();
  const { data: executions } = useTaskExecutions({
    task_type: selectedTaskType || undefined,
  });
  const { data: registryStats } = useCoinRegistryStats();
  const { data: pairsHistory } = usePairsUpdateHistory(10);

  const { mutate: triggerTask, isPending: isTriggering } = useTriggerTask();

  const handleTriggerTask = (taskName: string) => {
    if (confirm(`Are you sure you want to manually trigger '${taskName}'?`)) {
      triggerTask({
        taskName,
        triggeredBy: 'user:web-dashboard',
      });
    }
  };

  return (
    <div className="space-y-6">
      {/* Top Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="card">
          <p className="text-xs text-[var(--color-text-tertiary)] uppercase mb-1">Status</p>
          <p className="text-xl font-bold text-[var(--color-text-primary)]">
            {health?.status === 'healthy' ? 'Healthy' : 'Unhealthy'}
          </p>
        </div>
        <div className="card">
          <p className="text-xs text-[var(--color-text-tertiary)] uppercase mb-1">
            Executions (1h)
          </p>
          <p className="text-xl font-bold text-[var(--color-text-primary)]">
            {health?.recent_executions_1h || 0}
          </p>
        </div>
        <div className="card">
          <p className="text-xs text-[var(--color-text-tertiary)] uppercase mb-1">
            Failures (1h)
          </p>
          <p className="text-xl font-bold text-[var(--color-loss)]">
            {health?.recent_failures_1h || 0}
          </p>
        </div>
        <div className="card">
          <p className="text-xs text-[var(--color-text-tertiary)] uppercase mb-1">Running</p>
          <p className="text-xl font-bold text-[var(--color-text-primary)]">
            {health?.currently_running || 0}
          </p>
        </div>
      </div>

      {/* Coin Registry Stats */}
      <div className="card">
        <h2 className="text-sm font-semibold text-[var(--color-text-tertiary)] uppercase mb-4">
          Coin Registry
        </h2>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <div>
            <p className="text-xs text-[var(--color-text-tertiary)] uppercase mb-1">
              Active Coins
            </p>
            <p className="text-xl font-bold text-[var(--color-text-primary)]">
              {registryStats?.active_coins || 0}
            </p>
            <p className="text-xs text-[var(--color-text-tertiary)] mt-1">
              of {registryStats?.total_coins || 0} total
            </p>
          </div>
          <div>
            <p className="text-xs text-[var(--color-text-tertiary)] uppercase mb-1">
              Cache Age
            </p>
            <p className="text-xl font-bold text-[var(--color-text-primary)]">
              {registryStats?.cache_age_seconds
                ? `${Math.floor(registryStats.cache_age_seconds)}s`
                : 'N/A'}
            </p>
          </div>
          <div>
            <p className="text-xs text-[var(--color-text-tertiary)] uppercase mb-1">
              Last Update
            </p>
            <p className="text-sm text-[var(--color-text-primary)] mt-1">
              {registryStats?.db_updated_at
                ? new Date(registryStats.db_updated_at).toLocaleString()
                : 'Never'}
            </p>
          </div>
        </div>
      </div>

      {/* Task Execution History */}
      <div className="card">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-4">
          <h2 className="text-sm font-semibold text-[var(--color-text-tertiary)] uppercase">
            Recent Executions
          </h2>
          <div className="flex gap-2 overflow-x-auto">
            <button
              className={`btn ${selectedTaskType === null ? 'btn-primary' : 'btn-ghost'}`}
              onClick={() => setSelectedTaskType(null)}
            >
              All
            </button>
            <button
              className={`btn ${selectedTaskType === 'scheduler' ? 'btn-primary' : 'btn-ghost'}`}
              onClick={() => setSelectedTaskType('scheduler')}
            >
              Scheduler
            </button>
            <button
              className={`btn ${selectedTaskType === 'data_update' ? 'btn-primary' : 'btn-ghost'}`}
              onClick={() => setSelectedTaskType('data_update')}
            >
              Data
            </button>
          </div>
        </div>

        <div className="space-y-2">
          {executions?.executions.map((exec) => (
            <div
              key={exec.id}
              className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 p-3 bg-[var(--color-bg-secondary)] rounded-lg"
            >
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <p className="font-medium text-[var(--color-text-primary)]">
                    {exec.task_name}
                  </p>
                  <TaskStatusBadge status={exec.status} />
                  <span className="text-xs text-[var(--color-text-tertiary)] hide-mobile">
                    {exec.task_type}
                  </span>
                </div>
                <p className="text-xs text-[var(--color-text-tertiary)] mt-1">
                  Started: {new Date(exec.started_at).toLocaleString()}
                  {exec.duration_seconds &&
                    ` | Duration: ${exec.duration_seconds.toFixed(2)}s`}
                </p>
                {exec.error_message && (
                  <p className="text-xs text-[var(--color-loss)] mt-1 truncate">
                    Error: {exec.error_message}
                  </p>
                )}
              </div>
              <div className="text-xs text-[var(--color-text-tertiary)] self-start sm:self-center">
                {exec.triggered_by}
              </div>
            </div>
          ))}
          {(!executions?.executions || executions.executions.length === 0) && (
            <div className="text-center py-8 text-[var(--color-text-tertiary)]">
              No recent executions
            </div>
          )}
        </div>
      </div>

      {/* Pairs Update History */}
      <div className="card">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-4">
          <h2 className="text-sm font-semibold text-[var(--color-text-tertiary)] uppercase">
            Pairs Update History
          </h2>
          <button
            className="btn btn-primary flex items-center gap-2"
            onClick={() => handleTriggerTask('update_pairs')}
            disabled={isTriggering}
          >
            {isTriggering ? (
              <Activity className="w-4 h-4 animate-spin" />
            ) : (
              <Play className="w-4 h-4" />
            )}
            Trigger Update
          </button>
        </div>

        <div className="space-y-3">
          {pairsHistory?.updates.map((update) => (
            <div
              key={update.execution_id}
              className="p-3 bg-[var(--color-bg-secondary)] rounded-lg"
            >
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 mb-3">
                <div className="flex items-center gap-2">
                  <TaskStatusBadge status={update.status} />
                  <span className="text-sm text-[var(--color-text-primary)]">
                    {new Date(update.started_at).toLocaleString()}
                  </span>
                </div>
                {update.duration_seconds && (
                  <span className="text-xs text-[var(--color-text-tertiary)]">
                    {update.duration_seconds.toFixed(2)}s
                  </span>
                )}
              </div>

              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-sm">
                <div>
                  <p className="text-xs text-[var(--color-text-tertiary)]">Total</p>
                  <p className="font-medium text-[var(--color-text-primary)]">
                    {update.total_pairs}
                  </p>
                </div>
                <div>
                  <p className="text-xs text-[var(--color-text-tertiary)]">New</p>
                  <p className="font-medium text-[var(--color-profit)]">
                    +{update.new_pairs}
                  </p>
                </div>
                <div>
                  <p className="text-xs text-[var(--color-text-tertiary)]">Updated</p>
                  <p className="font-medium text-[var(--color-text-primary)]">
                    {update.updated_pairs}
                  </p>
                </div>
                <div>
                  <p className="text-xs text-[var(--color-text-tertiary)]">Deactivated</p>
                  <p className="font-medium text-[var(--color-loss)]">
                    -{update.deactivated_pairs}
                  </p>
                </div>
              </div>

              {update.top_10_symbols.length > 0 && (
                <div className="mt-3 pt-3 border-t border-[var(--color-border-primary)]">
                  <p className="text-xs text-[var(--color-text-tertiary)] mb-1">Top 10:</p>
                  <p className="text-xs font-mono text-[var(--color-text-secondary)] break-all">
                    {update.top_10_symbols.join(', ')}
                  </p>
                </div>
              )}
            </div>
          ))}
          {(!pairsHistory?.updates || pairsHistory.updates.length === 0) && (
            <div className="text-center py-8 text-[var(--color-text-tertiary)]">
              No update history
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// === Logs Tab Components ===

const SERVICES = [
  'generator',
  'backtester',
  'validator',
  'executor',
  'monitor',
  'scheduler',
  'data',
  'api',
];

const LOG_LEVELS = ['DEBUG', 'INFO', 'WARNING', 'ERROR'];

const LEVEL_COLORS: Record<string, string> = {
  DEBUG: 'text-[var(--color-text-tertiary)]',
  INFO: 'text-[var(--color-profit)]',
  WARNING: 'text-[var(--color-warning)]',
  ERROR: 'text-[var(--color-loss)]',
  CRITICAL: 'text-[var(--color-loss)]',
};

function formatTimestamp(dateStr: string): string {
  const date = new Date(dateStr);
  return date.toLocaleTimeString('en-US', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  });
}

function LogLineRow({ line }: { line: LogLine }) {
  const levelColor = LEVEL_COLORS[line.level] || 'text-[var(--color-text-tertiary)]';

  return (
    <div className="flex gap-3 py-1 hover:bg-[var(--color-bg-secondary)] font-mono text-xs">
      <span className="text-[var(--color-text-tertiary)] w-16 sm:w-20 flex-shrink-0">
        {formatTimestamp(line.timestamp)}
      </span>
      <span className={`w-14 sm:w-16 flex-shrink-0 ${levelColor}`}>{line.level}</span>
      <span className="text-[var(--color-text-tertiary)] flex-shrink-0 w-24 sm:w-32 truncate hide-mobile">
        {line.logger}
      </span>
      <span className="flex-1 break-all text-[var(--color-text-secondary)]">
        {line.message}
      </span>
    </div>
  );
}

function LogsTab() {
  const [selectedService, setSelectedService] = useState('executor');
  const [logLevel, setLogLevel] = useState('');
  const [search, setSearch] = useState('');
  const [autoScroll, setAutoScroll] = useState(true);
  const scrollRef = useRef<HTMLDivElement>(null);

  const { data, isLoading, error, refetch } = useLogs(selectedService, {
    lines: 500,
    level: logLevel || undefined,
    search: search || undefined,
  });

  useEffect(() => {
    if (autoScroll && scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [data?.lines, autoScroll]);

  const handleScroll = () => {
    if (scrollRef.current) {
      const { scrollTop, scrollHeight, clientHeight } = scrollRef.current;
      const isAtBottom = scrollHeight - scrollTop - clientHeight < 50;
      setAutoScroll(isAtBottom);
    }
  };

  const handleDownload = () => {
    if (!data?.lines) return;

    const content = data.lines
      .map((l) => `${l.timestamp} ${l.level} ${l.logger}: ${l.message}`)
      .join('\n');

    const blob = new Blob([content], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${selectedService}-logs.txt`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="space-y-4">
      {/* Service Tabs */}
      <div className="flex items-center gap-2 border-b border-[var(--color-border-primary)] pb-3 overflow-x-auto">
        {SERVICES.map((service) => (
          <button
            key={service}
            onClick={() => setSelectedService(service)}
            className={`px-3 py-1.5 rounded text-sm transition-colors whitespace-nowrap ${
              selectedService === service
                ? 'bg-[var(--color-accent)]/20 text-[var(--color-accent)]'
                : 'text-[var(--color-text-tertiary)] hover:text-[var(--color-text-primary)] hover:bg-[var(--color-bg-secondary)]'
            }`}
          >
            {service}
          </button>
        ))}
      </div>

      {/* Filters */}
      <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-3">
        <div className="flex gap-3">
          <select
            value={logLevel}
            onChange={(e) => setLogLevel(e.target.value)}
            className="input flex-1 sm:flex-none sm:w-auto"
          >
            <option value="">All Levels</option>
            {LOG_LEVELS.map((level) => (
              <option key={level} value={level}>
                {level}
              </option>
            ))}
          </select>

          <div className="relative flex-1 sm:max-w-xs">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[var(--color-text-tertiary)]" />
            <input
              type="text"
              placeholder="Search logs..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="input pl-10"
            />
          </div>
        </div>

        <div className="flex-1 hide-mobile" />

        <div className="flex gap-2">
          <button
            onClick={() => setAutoScroll(!autoScroll)}
            className={`btn ${autoScroll ? 'btn-primary' : 'btn-ghost'} flex items-center gap-2`}
          >
            <RefreshCw className={`w-4 h-4 ${autoScroll ? 'animate-spin' : ''}`} />
            <span className="hide-mobile">Auto-scroll</span>
          </button>

          <button
            onClick={handleDownload}
            className="btn btn-ghost flex items-center gap-2"
          >
            <Download className="w-4 h-4" />
            <span className="hide-mobile">Export</span>
          </button>

          <button onClick={() => refetch()} className="btn btn-ghost">
            <RefreshCw className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Log Viewer */}
      <div
        ref={scrollRef}
        onScroll={handleScroll}
        className="h-[400px] sm:h-[500px] card p-4 overflow-auto"
      >
        {isLoading ? (
          <div className="flex items-center justify-center h-full">
            <Activity className="w-6 h-6 animate-spin text-[var(--color-text-tertiary)]" />
          </div>
        ) : error ? (
          <div className="text-[var(--color-loss)] text-center py-4">
            Error loading logs: {(error as Error).message}
          </div>
        ) : data?.lines && data.lines.length > 0 ? (
          <div className="space-y-0">
            {data.lines.map((line, idx) => (
              <LogLineRow key={idx} line={line} />
            ))}
          </div>
        ) : (
          <div className="text-[var(--color-text-tertiary)] text-center py-4">
            No logs available for {selectedService}
          </div>
        )}
      </div>

      <div className="text-xs text-[var(--color-text-tertiary)]">
        Showing {data?.total_lines || 0} log lines from {selectedService}
      </div>
    </div>
  );
}

// === Settings Tab Components ===

function ServiceControl({ service }: { service: ServiceInfo }) {
  const { mutate: controlService, isPending } = useServiceControl();

  const statusColor =
    service.status === 'RUNNING'
      ? 'text-[var(--color-profit)]'
      : service.status === 'STOPPED'
        ? 'text-[var(--color-text-tertiary)]'
        : 'text-[var(--color-loss)]';

  const dotClass =
    service.status === 'RUNNING'
      ? 'bg-[var(--color-profit)] animate-pulse-slow'
      : 'bg-[var(--color-text-tertiary)]';

  const handleAction = (action: 'start' | 'stop' | 'restart') => {
    controlService({ name: service.name, action });
  };

  return (
    <div className="card">
      <div className="flex items-center justify-between mb-3">
        <div className="flex items-center gap-3">
          <span className={`w-3 h-3 rounded-full ${dotClass}`} />
          <span className="font-semibold text-[var(--color-text-primary)]">
            {service.name}
          </span>
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
        <div className="text-xs text-[var(--color-text-tertiary)] mt-2">
          PID: {service.pid}
        </div>
      )}
    </div>
  );
}

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
          <h4 className="text-xs text-[var(--color-text-tertiary)] uppercase mb-3">
            Backtest
          </h4>
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
                  ? `${((thresholds.backtest.min_win_rate as number) * 100).toFixed(0)}%`
                  : '--'}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-[var(--color-text-secondary)]">Max Drawdown</span>
              <span className="font-mono text-[var(--color-text-primary)]">
                {thresholds.backtest?.max_drawdown
                  ? `${((thresholds.backtest.max_drawdown as number) * 100).toFixed(0)}%`
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
                  ? `${((thresholds.risk.risk_per_trade_pct as number) * 100).toFixed(1)}%`
                  : '--'}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-[var(--color-text-secondary)]">Max Position</span>
              <span className="font-mono text-[var(--color-text-primary)]">
                {thresholds.risk?.max_position_size_pct
                  ? `${((thresholds.risk.max_position_size_pct as number) * 100).toFixed(0)}%`
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
          <h4 className="text-xs text-[var(--color-text-tertiary)] uppercase mb-3">
            Emergency
          </h4>
          <div className="space-y-2 text-sm">
            <div className="flex justify-between">
              <span className="text-[var(--color-text-secondary)]">Portfolio DD</span>
              <span className="font-mono text-[var(--color-loss)]">
                {thresholds.emergency?.max_portfolio_drawdown
                  ? `${((thresholds.emergency.max_portfolio_drawdown as number) * 100).toFixed(0)}%`
                  : '--'}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-[var(--color-text-secondary)]">Subaccount DD</span>
              <span className="font-mono text-[var(--color-loss)]">
                {thresholds.emergency?.max_subaccount_drawdown
                  ? `${((thresholds.emergency.max_subaccount_drawdown as number) * 100).toFixed(0)}%`
                  : '--'}
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-[var(--color-text-secondary)]">Daily Loss</span>
              <span className="font-mono text-[var(--color-loss)]">
                {thresholds.emergency?.max_daily_loss
                  ? `${((thresholds.emergency.max_daily_loss as number) * 100).toFixed(0)}%`
                  : '--'}
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

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

function SettingsTab() {
  const { data: services, isLoading: servicesLoading } = useServices();
  const [activeSubTab, setActiveSubTab] = useState<'services' | 'config'>('services');

  return (
    <div className="space-y-6">
      {/* Warning */}
      <div className="flex items-center gap-3 p-4 bg-[var(--color-warning)]/10 border border-[var(--color-warning)]/30 rounded-lg">
        <AlertTriangle className="w-5 h-5 text-[var(--color-warning)] flex-shrink-0" />
        <p className="text-sm text-[var(--color-warning)]">
          Service controls affect live trading. Use with caution.
        </p>
      </div>

      {/* Sub-Tabs */}
      <div className="flex gap-4 border-b border-[var(--color-border-primary)]">
        <button
          onClick={() => setActiveSubTab('services')}
          className={`px-4 py-2 text-sm border-b-2 transition-colors ${
            activeSubTab === 'services'
              ? 'border-[var(--color-accent)] text-[var(--color-accent)]'
              : 'border-transparent text-[var(--color-text-tertiary)] hover:text-[var(--color-text-primary)]'
          }`}
        >
          Services
        </button>
        <button
          onClick={() => setActiveSubTab('config')}
          className={`px-4 py-2 text-sm border-b-2 transition-colors ${
            activeSubTab === 'config'
              ? 'border-[var(--color-accent)] text-[var(--color-accent)]'
              : 'border-transparent text-[var(--color-text-tertiary)] hover:text-[var(--color-text-primary)]'
          }`}
        >
          Configuration
        </button>
      </div>

      {/* Services Sub-Tab */}
      {activeSubTab === 'services' && (
        <div className="space-y-6">
          <div>
            <h2 className="text-lg font-semibold text-[var(--color-text-primary)] mb-4">
              Service Control
            </h2>
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

          <ThresholdsSection />
        </div>
      )}

      {/* Config Sub-Tab */}
      {activeSubTab === 'config' && <ConfigViewer />}
    </div>
  );
}

// === Go Live Tab Components ===

function CheckStatusIcon({ status }: { status: 'pass' | 'fail' | 'warn' }) {
  if (status === 'pass') {
    return <CheckCircle className="w-5 h-5 text-[var(--color-profit)]" />;
  }
  if (status === 'fail') {
    return <XCircle className="w-5 h-5 text-[var(--color-loss)]" />;
  }
  return <AlertTriangle className="w-5 h-5 text-[var(--color-warning)]" />;
}

function PreflightCheckCard({ check }: { check: PreflightCheck }) {
  return (
    <div className="flex items-start gap-3 p-4 bg-[var(--color-bg-secondary)] rounded-lg">
      <CheckStatusIcon status={check.status} />
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className="font-medium text-[var(--color-text-primary)]">{check.name}</span>
          {check.can_fix && (
            <span className="text-xs px-2 py-0.5 rounded bg-[var(--color-accent)]/20 text-[var(--color-accent)]">
              Fixable
            </span>
          )}
        </div>
        <p className="text-sm text-[var(--color-text-secondary)] mt-1">{check.message}</p>
      </div>
    </div>
  );
}

function SubaccountStatusRow({ sa }: { sa: SubaccountPreflightStatus }) {
  const statusColors: Record<string, string> = {
    funded: 'text-[var(--color-profit)]',
    underfunded: 'text-[var(--color-loss)]',
    unknown: 'text-[var(--color-warning)]',
    missing: 'text-[var(--color-text-tertiary)]',
  };

  const statusIcons: Record<string, React.ReactNode> = {
    funded: <CheckCircle className="w-4 h-4" />,
    underfunded: <AlertTriangle className="w-4 h-4" />,
    unknown: <AlertCircle className="w-4 h-4" />,
    missing: <XCircle className="w-4 h-4" />,
  };

  return (
    <div className="flex items-center justify-between p-3 bg-[var(--color-bg-secondary)] rounded-lg">
      <div className="flex items-center gap-3">
        <Database className="w-4 h-4 text-[var(--color-text-tertiary)]" />
        <span className="font-medium text-[var(--color-text-primary)]">Subaccount {sa.id}</span>
      </div>
      <div className="flex items-center gap-3">
        {sa.balance !== null && (
          <span className="text-sm text-[var(--color-text-secondary)]">
            ${sa.balance.toFixed(2)}
          </span>
        )}
        <span className={`flex items-center gap-1 text-sm ${statusColors[sa.status]}`}>
          {statusIcons[sa.status]}
          {sa.status}
        </span>
      </div>
    </div>
  );
}

function GoLiveTab() {
  const { data, isLoading, error, refetch } = usePreflight();
  const { mutate: applyFixes, isPending: isApplying } = useApplyPreflightFixes();
  const [showDetails, setShowDetails] = useState(false);

  const handleApplyFixes = () => {
    if (!data) return;

    const needsSubaccounts = data.subaccounts.some((sa) => !sa.exists);
    const hasEmergencyStops = data.emergency_stops.length > 0;

    if (!needsSubaccounts && !hasEmergencyStops) {
      alert('No fixable issues found');
      return;
    }

    if (confirm('Apply fixes? This will create missing subaccounts and clear emergency stops.')) {
      applyFixes({
        create_subaccounts: needsSubaccounts,
        clear_emergency_stops: hasEmergencyStops,
      });
    }
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Activity className="w-6 h-6 animate-spin text-[var(--color-text-tertiary)]" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="card p-6 text-center">
        <AlertCircle className="w-8 h-8 text-[var(--color-loss)] mx-auto mb-3" />
        <p className="text-[var(--color-loss)]">Failed to load preflight status</p>
        <p className="text-sm text-[var(--color-text-tertiary)] mt-1">
          {(error as Error).message}
        </p>
        <button onClick={() => refetch()} className="btn btn-primary mt-4">
          Retry
        </button>
      </div>
    );
  }

  if (!data) return null;

  const failedChecks = data.checks.filter((c) => c.status === 'fail');
  const warnChecks = data.checks.filter((c) => c.status === 'warn');
  const canApplyFixes =
    data.subaccounts.some((sa) => !sa.exists) || data.emergency_stops.length > 0;

  return (
    <div className="space-y-6">
      {/* Overall Status */}
      <div
        className={`card p-6 border-2 ${
          data.ready
            ? 'border-[var(--color-profit)]/50 bg-[var(--color-profit)]/5'
            : 'border-[var(--color-loss)]/50 bg-[var(--color-loss)]/5'
        }`}
      >
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <div
              className={`w-16 h-16 rounded-full flex items-center justify-center ${
                data.ready ? 'bg-[var(--color-profit)]/20' : 'bg-[var(--color-loss)]/20'
              }`}
            >
              {data.ready ? (
                <Rocket className="w-8 h-8 text-[var(--color-profit)]" />
              ) : (
                <AlertTriangle className="w-8 h-8 text-[var(--color-loss)]" />
              )}
            </div>
            <div>
              <h2 className="text-2xl font-bold text-[var(--color-text-primary)]">
                {data.ready ? 'Ready for Live Trading' : 'Not Ready'}
              </h2>
              <p className="text-[var(--color-text-secondary)] mt-1">
                {failedChecks.length > 0
                  ? `${failedChecks.length} check(s) failed`
                  : warnChecks.length > 0
                    ? `${warnChecks.length} warning(s)`
                    : 'All checks passed'}
              </p>
            </div>
          </div>

          <div className="flex gap-3">
            <button onClick={() => refetch()} className="btn btn-ghost">
              <RefreshCw className="w-4 h-4" />
            </button>
            {canApplyFixes && (
              <button
                onClick={handleApplyFixes}
                disabled={isApplying}
                className="btn btn-primary flex items-center gap-2"
              >
                {isApplying ? (
                  <Activity className="w-4 h-4 animate-spin" />
                ) : (
                  <Zap className="w-4 h-4" />
                )}
                Apply Fixes
              </button>
            )}
          </div>
        </div>
      </div>

      {/* Checks */}
      <div className="card">
        <h3 className="text-sm font-semibold text-[var(--color-text-tertiary)] uppercase mb-4">
          Preflight Checks
        </h3>
        <div className="space-y-3">
          {data.checks.map((check) => (
            <PreflightCheckCard key={check.name} check={check} />
          ))}
        </div>
      </div>

      {/* Config Mismatches */}
      {data.config_mismatches.length > 0 && (
        <div className="card">
          <h3 className="text-sm font-semibold text-[var(--color-text-tertiary)] uppercase mb-4">
            Config Mismatches (Manual Fix Required)
          </h3>
          <p className="text-sm text-[var(--color-text-secondary)] mb-4">
            Edit <code className="px-1.5 py-0.5 bg-[var(--color-bg-secondary)] rounded">config/config.yaml</code> to match these values:
          </p>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="text-left text-[var(--color-text-tertiary)]">
                  <th className="pb-2">Key</th>
                  <th className="pb-2">Current</th>
                  <th className="pb-2">Target</th>
                </tr>
              </thead>
              <tbody>
                {data.config_mismatches.map((m) => (
                  <tr key={m.key} className="border-t border-[var(--color-border-primary)]">
                    <td className="py-2 font-mono text-[var(--color-text-primary)]">{m.key}</td>
                    <td className="py-2 text-[var(--color-loss)]">{m.current}</td>
                    <td className="py-2 text-[var(--color-profit)]">{m.target}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Pool Stats */}
      <div className="card">
        <h3 className="text-sm font-semibold text-[var(--color-text-tertiary)] uppercase mb-4">
          Strategy Pool
        </h3>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
          <div>
            <p className="text-xs text-[var(--color-text-tertiary)] uppercase mb-1">Active</p>
            <p className="text-xl font-bold text-[var(--color-text-primary)]">
              {data.pool_stats.active}
            </p>
          </div>
          <div>
            <p className="text-xs text-[var(--color-text-tertiary)] uppercase mb-1">Live</p>
            <p className="text-xl font-bold text-[var(--color-text-primary)]">
              {data.pool_stats.live}
            </p>
          </div>
          <div>
            <p className="text-xs text-[var(--color-text-tertiary)] uppercase mb-1">Total Ready</p>
            <p
              className={`text-xl font-bold ${
                data.pool_stats.total >= data.pool_stats.required
                  ? 'text-[var(--color-profit)]'
                  : 'text-[var(--color-loss)]'
              }`}
            >
              {data.pool_stats.total}
            </p>
          </div>
          <div>
            <p className="text-xs text-[var(--color-text-tertiary)] uppercase mb-1">Required</p>
            <p className="text-xl font-bold text-[var(--color-text-primary)]">
              {data.pool_stats.required}
            </p>
          </div>
        </div>
      </div>

      {/* Subaccounts */}
      <div className="card">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-sm font-semibold text-[var(--color-text-tertiary)] uppercase">
            Subaccounts ({data.subaccounts.length})
          </h3>
          <button
            onClick={() => setShowDetails(!showDetails)}
            className="btn btn-ghost text-sm"
          >
            {showDetails ? 'Hide Details' : 'Show Details'}
          </button>
        </div>

        {showDetails && (
          <div className="space-y-2">
            {data.subaccounts.map((sa) => (
              <SubaccountStatusRow key={sa.id} sa={sa} />
            ))}
          </div>
        )}

        {!showDetails && (
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
            <div>
              <p className="text-xs text-[var(--color-text-tertiary)] uppercase mb-1">Funded</p>
              <p className="text-xl font-bold text-[var(--color-profit)]">
                {data.subaccounts.filter((sa) => sa.status === 'funded').length}
              </p>
            </div>
            <div>
              <p className="text-xs text-[var(--color-text-tertiary)] uppercase mb-1">Underfunded</p>
              <p className="text-xl font-bold text-[var(--color-loss)]">
                {data.subaccounts.filter((sa) => sa.status === 'underfunded').length}
              </p>
            </div>
            <div>
              <p className="text-xs text-[var(--color-text-tertiary)] uppercase mb-1">Missing</p>
              <p className="text-xl font-bold text-[var(--color-text-tertiary)]">
                {data.subaccounts.filter((sa) => !sa.exists).length}
              </p>
            </div>
            <div>
              <p className="text-xs text-[var(--color-text-tertiary)] uppercase mb-1">
                Min Balance
              </p>
              <p className="text-xl font-bold text-[var(--color-text-primary)]">
                ${data.target_config.min_operational}
              </p>
            </div>
          </div>
        )}
      </div>

      {/* Emergency Stops */}
      {data.emergency_stops.length > 0 && (
        <div className="card border border-[var(--color-loss)]/50">
          <h3 className="text-sm font-semibold text-[var(--color-loss)] uppercase mb-4">
            Active Emergency Stops ({data.emergency_stops.length})
          </h3>
          <div className="space-y-2">
            {data.emergency_stops.map((stop, idx) => (
              <div
                key={idx}
                className="flex items-center justify-between p-3 bg-[var(--color-loss)]/10 rounded-lg"
              >
                <div className="flex items-center gap-3">
                  <AlertCircle className="w-4 h-4 text-[var(--color-loss)]" />
                  <span className="font-medium text-[var(--color-text-primary)]">
                    [{stop.scope}:{stop.scope_id}]
                  </span>
                </div>
                <span className="text-sm text-[var(--color-text-secondary)]">
                  {stop.reason || 'No reason specified'}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Target Config */}
      <div className="card">
        <h3 className="text-sm font-semibold text-[var(--color-text-tertiary)] uppercase mb-4">
          Target Configuration (from prepare_live.yaml)
        </h3>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 text-sm">
          <div>
            <p className="text-[var(--color-text-tertiary)]">Subaccounts</p>
            <p className="font-medium text-[var(--color-text-primary)]">
              {data.target_config.num_subaccounts}
            </p>
          </div>
          <div>
            <p className="text-[var(--color-text-tertiary)]">Capital/Sub</p>
            <p className="font-medium text-[var(--color-text-primary)]">
              ${data.target_config.capital_per_subaccount}
            </p>
          </div>
          <div>
            <p className="text-[var(--color-text-tertiary)]">Max Live</p>
            <p className="font-medium text-[var(--color-text-primary)]">
              {data.target_config.max_live_strategies}
            </p>
          </div>
          <div>
            <p className="text-[var(--color-text-tertiary)]">Mode</p>
            <p
              className={`font-medium ${
                data.target_config.dry_run
                  ? 'text-[var(--color-warning)]'
                  : 'text-[var(--color-profit)]'
              }`}
            >
              {data.target_config.dry_run ? 'DRY RUN' : 'LIVE'}
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}

// === Main Page ===

export default function System() {
  const [activeTab, setActiveTab] = useState<TabType>('golive');

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-3">
        <SettingsIcon className="w-6 h-6 text-[var(--color-text-tertiary)]" />
        <div>
          <h1 className="text-2xl font-bold text-[var(--color-text-primary)]">System</h1>
          <p className="text-sm text-[var(--color-text-secondary)] mt-1">
            Go live setup, tasks, logs, and configuration
          </p>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 border-b border-[var(--color-border-primary)]">
        {TABS.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`px-4 py-2.5 text-sm font-medium border-b-2 transition-colors ${
              activeTab === tab.id
                ? 'border-[var(--color-accent)] text-[var(--color-accent)]'
                : 'border-transparent text-[var(--color-text-tertiary)] hover:text-[var(--color-text-primary)]'
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Tab Content */}
      {activeTab === 'golive' && <GoLiveTab />}
      {activeTab === 'tasks' && <TasksTab />}
      {activeTab === 'logs' && <LogsTab />}
      {activeTab === 'settings' && <SettingsTab />}
    </div>
  );
}
