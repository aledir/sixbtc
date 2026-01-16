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
  useThresholds,
  usePreflight,
  useApplyPreflightFixes,
  useConfigYaml,
} from '../hooks/useApi';
import type { ServiceInfo, LogLine, SubaccountPreflightStatus } from '../types';
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
  Edit2,
  ChevronUp,
  ChevronDown,
  X,
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
  'executor',
  'generator',
  'backtester',
  'validator',
  'rotator',
  'monitor',
  'metrics',
  'scheduler',
  'api',
  'frontend',
  'subaccount',
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
  const prevLinesCount = useRef(0);

  const { data, isLoading, error, refetch } = useLogs(selectedService, {
    lines: 500,
    level: logLevel || undefined,
    search: search || undefined,
  });

  // Auto-scroll only when NEW lines are added, not on every re-render
  useEffect(() => {
    const currentCount = data?.lines?.length || 0;
    if (autoScroll && scrollRef.current && currentCount > prevLinesCount.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
    prevLinesCount.current = currentCount;
  }, [data?.lines?.length, autoScroll]);

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
  const { data, isLoading, error, refetch } = useConfigYaml();
  const [yamlContent, setYamlContent] = useState('');
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedSection, setSelectedSection] = useState<string | null>(null);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [currentMatchIndex, setCurrentMatchIndex] = useState(0);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const contentRef = useRef<HTMLDivElement>(null);

  const handleRefresh = async () => {
    setIsRefreshing(true);
    try {
      await refetch();
    } finally {
      setIsRefreshing(false);
    }
  };

  // Initialize content when data loads
  useEffect(() => {
    if (data?.yaml_content && !yamlContent) {
      setYamlContent(data.yaml_content);
    }
  }, [data, yamlContent]);

  // Reset current match when search changes
  useEffect(() => {
    setCurrentMatchIndex(0);
  }, [searchTerm]);

  // Get filtered content based on section and search
  const getFilteredContent = () => {
    let content = yamlContent || data?.yaml_content || '';

    // Filter by section if selected
    if (selectedSection && data?.sections) {
      // Find the section header (# ==== / # NAME / # ====)
      const sectionIndex = content.indexOf(`# ${selectedSection}`);
      if (sectionIndex !== -1) {
        // Find start of section (the ==== line before the name)
        const beforeSection = content.substring(0, sectionIndex);
        const headerStart = beforeSection.lastIndexOf('# ==');

        // Find the next section header (full 3-line pattern: ====, NAME, ====)
        // Pattern matches: \n# ====...\n# SECTION_NAME\n# ====...
        const nextSectionPattern = /\n# ={5,}\n# [A-Z][^\n]+\n# ={5,}/g;
        nextSectionPattern.lastIndex = sectionIndex + selectedSection.length;
        const nextMatch = nextSectionPattern.exec(content);

        if (nextMatch) {
          content = content.substring(headerStart >= 0 ? headerStart : sectionIndex, nextMatch.index);
        } else {
          content = content.substring(headerStart >= 0 ? headerStart : sectionIndex);
        }
      }
    }

    return content;
  };

  // Get line numbers for display
  const getLineNumbers = (content: string) => {
    const lines = content.split('\n');
    return lines.map((_, i) => i + 1).join('\n');
  };

  const handleJumpToSection = (section: string) => {
    setSelectedSection(section);
    if (textareaRef.current && data?.yaml_content) {
      const sectionIndex = data.yaml_content.indexOf(`# ${section}`);
      if (sectionIndex !== -1) {
        // Count lines to this position
        const linesBeforeSection = data.yaml_content.substring(0, sectionIndex).split('\n').length - 1;
        // Scroll textarea to approximately that position
        textareaRef.current.scrollTop = linesBeforeSection * 16; // ~16px per line
      }
    }
  };

  // Count search matches
  const getMatchCount = () => {
    if (!searchTerm) return 0;
    const content = getFilteredContent();
    const matches = content.toLowerCase().split(searchTerm.toLowerCase()).length - 1;
    return matches;
  };

  const matchCount = getMatchCount();

  // Navigate to next/previous match
  const handleNextMatch = () => {
    if (matchCount > 0) {
      setCurrentMatchIndex((prev) => (prev + 1) % matchCount);
      scrollToMatch((currentMatchIndex + 1) % matchCount);
    }
  };

  const handlePrevMatch = () => {
    if (matchCount > 0) {
      setCurrentMatchIndex((prev) => (prev - 1 + matchCount) % matchCount);
      scrollToMatch((currentMatchIndex - 1 + matchCount) % matchCount);
    }
  };

  const scrollToMatch = (index: number) => {
    if (!contentRef.current || !searchTerm) return;
    const highlights = contentRef.current.querySelectorAll('[data-match="true"]');
    if (highlights[index]) {
      highlights[index].scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
  };

  const clearSearch = () => {
    setSearchTerm('');
    setCurrentMatchIndex(0);
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
      <div className="card">
        <p className="text-[var(--color-loss)]">Error loading config: {(error as Error).message}</p>
        <button onClick={() => refetch()} className="btn btn-primary mt-4">
          Retry
        </button>
      </div>
    );
  }

  const displayContent = getFilteredContent();

  return (
    <div className="space-y-4">
      {/* Header with controls */}
      <div className="card">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-4">
          <div>
            <h3 className="text-sm font-semibold text-[var(--color-text-tertiary)] uppercase">
              Configuration (config.yaml)
            </h3>
            <p className="text-xs text-[var(--color-text-tertiary)] mt-1">
              {data?.line_count} lines • {data?.sections?.length || 0} sections
            </p>
          </div>
          <button
            onClick={handleRefresh}
            disabled={isRefreshing}
            className="btn btn-ghost text-sm"
            title="Refresh configuration"
          >
            <RefreshCw className={`w-4 h-4 ${isRefreshing ? 'animate-spin' : ''}`} />
          </button>
        </div>

        {/* Info message - edit via file */}
        <div className="flex items-center gap-3 p-3 bg-[var(--color-text-tertiary)]/10 border border-[var(--color-text-tertiary)]/30 rounded-lg mb-4">
          <AlertCircle className="w-4 h-4 text-[var(--color-text-secondary)] flex-shrink-0" />
          <p className="text-xs text-[var(--color-text-secondary)]">
            Read-only view. To edit, modify <code className="bg-[var(--color-bg-tertiary)] px-1 rounded">config/config.yaml</code> directly and restart services.
          </p>
        </div>

        {/* Filters row */}
        <div className="flex flex-col sm:flex-row gap-3 mb-4">
          {/* Section filter */}
          <select
            value={selectedSection || ''}
            onChange={(e) => setSelectedSection(e.target.value || null)}
            className="input sm:w-64"
          >
            <option value="">All Sections</option>
            {data?.sections?.map((section) => (
              <option key={section} value={section}>
                {section}
              </option>
            ))}
          </select>

          {/* Search with navigation */}
          <div className="flex items-center gap-1 flex-1 sm:flex-initial">
            <div className="relative flex-1 sm:w-64">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[var(--color-text-tertiary)] pointer-events-none" />
              <input
                type="text"
                placeholder="Search..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="input pl-9 pr-16 w-full"
              />
              {searchTerm && (
                <div className="absolute right-2 top-1/2 -translate-y-1/2 flex items-center gap-1 text-xs text-[var(--color-text-tertiary)]">
                  <span>{matchCount > 0 ? `${currentMatchIndex + 1}/${matchCount}` : '0/0'}</span>
                  <button onClick={clearSearch} className="p-0.5 hover:text-[var(--color-text-primary)]">
                    <X className="w-3 h-3" />
                  </button>
                </div>
              )}
            </div>
            {searchTerm && matchCount > 0 && (
              <>
                <button
                  onClick={handlePrevMatch}
                  className="btn btn-ghost p-1.5"
                  title="Previous match"
                >
                  <ChevronUp className="w-4 h-4" />
                </button>
                <button
                  onClick={handleNextMatch}
                  className="btn btn-ghost p-1.5"
                  title="Next match"
                >
                  <ChevronDown className="w-4 h-4" />
                </button>
              </>
            )}
          </div>
        </div>

        {/* Quick section links */}
        {data?.sections && data.sections.length > 0 && (
          <div className="flex flex-wrap gap-2 mb-4">
            {data.sections.slice(0, 10).map((section) => (
              <button
                key={section}
                onClick={() => handleJumpToSection(section)}
                className={`text-xs px-2 py-1 rounded transition-colors ${
                  selectedSection === section
                    ? 'bg-[var(--color-accent)] text-white'
                    : 'bg-[var(--color-bg-secondary)] text-[var(--color-text-secondary)] hover:bg-[var(--color-bg-tertiary)]'
                }`}
              >
                {section.replace(/ \([^)]+\)/, '').substring(0, 20)}
              </button>
            ))}
            {data.sections.length > 10 && (
              <span className="text-xs text-[var(--color-text-tertiary)] px-2 py-1">
                +{data.sections.length - 10} more
              </span>
            )}
          </div>
        )}
      </div>

      {/* YAML content */}
      <div className="card p-0 overflow-hidden">
        <div ref={contentRef} className="flex h-[500px] overflow-auto">
          {/* Line numbers */}
          <div className="sticky left-0 flex-shrink-0 py-4 pl-4 pr-2 bg-[var(--color-bg-tertiary)] text-[var(--color-text-tertiary)] font-mono text-xs text-right select-none border-r border-[var(--color-border-primary)]">
            <pre>{getLineNumbers(displayContent)}</pre>
          </div>
          {/* Content */}
          <pre className="flex-1 p-4 font-mono text-xs text-[var(--color-text-secondary)] whitespace-pre">
                {searchTerm
                  ? displayContent.split('\n').map((line, i) => {
                      const lowerLine = line.toLowerCase();
                      const lowerSearch = searchTerm.toLowerCase();
                      if (lowerLine.includes(lowerSearch)) {
                        // Highlight matching text
                        const parts = [];
                        let lastIndex = 0;
                        let index = lowerLine.indexOf(lowerSearch);
                        while (index !== -1) {
                          parts.push(line.substring(lastIndex, index));
                          parts.push(
                            <span key={`${i}-${index}`} className="bg-[var(--color-warning)]/40 text-[var(--color-warning)]">
                              {line.substring(index, index + searchTerm.length)}
                            </span>
                          );
                          lastIndex = index + searchTerm.length;
                          index = lowerLine.indexOf(lowerSearch, lastIndex);
                        }
                        parts.push(line.substring(lastIndex));
                        return (
                          <div key={i} data-match="true" className="bg-[var(--color-warning)]/10">
                            {parts}
                          </div>
                        );
                      }
                      return <div key={i}>{line || ' '}</div>;
                    })
                  : displayContent.split('\n').map((line, i) => {
                      // Syntax highlighting
                      let className = '';
                      if (line.startsWith('#')) {
                        className = 'text-[var(--color-text-tertiary)]'; // Comments
                      } else if (line.match(/^\s*[a-z_]+:/i) && !line.includes('[REDACTED]')) {
                        // Keys
                        const colonIdx = line.indexOf(':');
                        const key = line.substring(0, colonIdx + 1);
                        const value = line.substring(colonIdx + 1);
                        return (
                          <div key={i}>
                            <span className="text-[var(--color-accent)]">{key}</span>
                            <span className={value.includes('#') ? '' : 'text-[var(--color-profit)]'}>
                              {value}
                            </span>
                          </div>
                        );
                      } else if (line.includes('[REDACTED]') || line.includes('[ENV_VAR]')) {
                        className = 'text-[var(--color-loss)]';
                      }
                      return (
                        <div key={i} className={className}>
                          {line || ' '}
                        </div>
                      );
                    })}
          </pre>
        </div>
      </div>

      {/* Status bar */}
      <div className="text-xs text-[var(--color-text-tertiary)] flex items-center gap-4">
        <span>{displayContent.split('\n').length} lines shown</span>
        {selectedSection && <span>Section: {selectedSection}</span>}
        {searchTerm && (
          <span>
            {displayContent.toLowerCase().split(searchTerm.toLowerCase()).length - 1} matches
          </span>
        )}
      </div>
    </div>
  );
}

function SettingsTab({ initialSubTab = 'services' }: { initialSubTab?: 'services' | 'config' }) {
  const { data: services, isLoading: servicesLoading } = useServices();
  const [activeSubTab, setActiveSubTab] = useState<'services' | 'config'>(initialSubTab);

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

function GoLiveTab({ onNavigateToSettings }: { onNavigateToSettings?: () => void }) {
  const { data, isLoading, error, refetch } = usePreflight();
  const { mutate: applyFixes, isPending: isApplying } = useApplyPreflightFixes();
  const [showSubaccountDetails, setShowSubaccountDetails] = useState(false);
  const [isRefreshing, setIsRefreshing] = useState(false);

  const handleRefresh = async () => {
    setIsRefreshing(true);
    try {
      await refetch();
    } finally {
      setIsRefreshing(false);
    }
  };

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
  const fundedCount = data.subaccounts.filter((sa) => sa.status === 'funded').length;

  return (
    <div className="space-y-4">
      {/* Status Header - Compact */}
      <div
        className={`card p-4 border-l-4 ${
          data.ready
            ? 'border-l-[var(--color-profit)] bg-[var(--color-profit)]/5'
            : 'border-l-[var(--color-loss)] bg-[var(--color-loss)]/5'
        }`}
      >
        <div className="flex items-center justify-between flex-wrap gap-3">
          {/* Left: Status */}
          <div className="flex items-center gap-3">
            {data.ready ? (
              <Rocket className="w-6 h-6 text-[var(--color-profit)]" />
            ) : (
              <AlertTriangle className="w-6 h-6 text-[var(--color-loss)]" />
            )}
            <div>
              <span className="font-bold text-[var(--color-text-primary)]">
                {data.ready ? 'Ready for Live Trading' : 'Not Ready'}
              </span>
              <span className="text-sm text-[var(--color-text-secondary)] ml-2">
                {failedChecks.length > 0
                  ? `${failedChecks.length} check(s) failed`
                  : warnChecks.length > 0
                    ? `${warnChecks.length} warning(s)`
                    : 'All checks passed'}
              </span>
            </div>
          </div>

          {/* Right: Actions */}
          <div className="flex items-center gap-2">
            <button
              onClick={handleRefresh}
              disabled={isRefreshing}
              className="btn btn-ghost p-2"
              title="Refresh status"
            >
              <RefreshCw className={`w-4 h-4 ${isRefreshing ? 'animate-spin' : ''}`} />
            </button>
            {onNavigateToSettings && (
              <button
                onClick={onNavigateToSettings}
                className="btn btn-secondary flex items-center gap-2"
              >
                <Edit2 className="w-4 h-4" />
                <span className="hidden sm:inline">Edit Config</span>
              </button>
            )}
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

      {/* Emergency Stops - Show prominently if any */}
      {data.emergency_stops.length > 0 && (
        <div className="card p-4 border border-[var(--color-loss)]/50 bg-[var(--color-loss)]/5">
          <div className="flex items-center gap-2 text-[var(--color-loss)] font-medium mb-2">
            <AlertCircle className="w-4 h-4" />
            Active Emergency Stops ({data.emergency_stops.length})
          </div>
          <div className="space-y-1">
            {data.emergency_stops.map((stop, idx) => (
              <div key={idx} className="text-sm text-[var(--color-text-secondary)]">
                <span className="font-mono">[{stop.scope}:{stop.scope_id}]</span> {stop.reason || 'No reason'}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Two-column layout for checks and stats */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        {/* Preflight Checks */}
        <div className="card p-4">
          <h3 className="text-xs font-semibold text-[var(--color-text-tertiary)] uppercase mb-3">
            Preflight Checks
          </h3>
          <div className="space-y-2">
            {data.checks.map((check) => (
              <div key={check.name} className="flex items-start gap-2">
                <CheckStatusIcon status={check.status} />
                <div className="flex-1 min-w-0">
                  <span className="text-sm font-medium text-[var(--color-text-primary)]">
                    {check.name}
                  </span>
                  {check.can_fix && (
                    <span className="ml-2 text-xs px-1.5 py-0.5 rounded bg-[var(--color-accent)]/20 text-[var(--color-accent)]">
                      Fixable
                    </span>
                  )}
                  <p className="text-xs text-[var(--color-text-tertiary)]">{check.message}</p>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Quick Stats */}
        <div className="card p-4">
          <h3 className="text-xs font-semibold text-[var(--color-text-tertiary)] uppercase mb-3">
            Current Status
          </h3>
          <div className="grid grid-cols-2 gap-3">
            <div className="p-3 bg-[var(--color-bg-secondary)] rounded-lg">
              <p className="text-xs text-[var(--color-text-tertiary)]">Pool / Required</p>
              <p className={`text-lg font-bold ${
                data.pool_stats.total >= data.pool_stats.required
                  ? 'text-[var(--color-profit)]'
                  : 'text-[var(--color-loss)]'
              }`}>
                {data.pool_stats.total} / {data.pool_stats.required}
              </p>
            </div>
            <div className="p-3 bg-[var(--color-bg-secondary)] rounded-lg">
              <p className="text-xs text-[var(--color-text-tertiary)]">Live Strategies</p>
              <p className="text-lg font-bold text-[var(--color-text-primary)]">
                {data.pool_stats.live}
              </p>
            </div>
            <div className="p-3 bg-[var(--color-bg-secondary)] rounded-lg">
              <p className="text-xs text-[var(--color-text-tertiary)]">Subaccounts Funded</p>
              <p className={`text-lg font-bold ${
                fundedCount === data.subaccounts.length
                  ? 'text-[var(--color-profit)]'
                  : 'text-[var(--color-warning)]'
              }`}>
                {fundedCount} / {data.subaccounts.length}
              </p>
            </div>
            <div className="p-3 bg-[var(--color-bg-secondary)] rounded-lg">
              <p className="text-xs text-[var(--color-text-tertiary)]">Trading Mode</p>
              <p className={`text-lg font-bold ${
                data.config_summary.dry_run
                  ? 'text-[var(--color-warning)]'
                  : 'text-[var(--color-profit)]'
              }`}>
                {data.config_summary.dry_run ? 'DRY RUN' : 'LIVE'}
              </p>
            </div>
          </div>
        </div>
      </div>

      {/* Subaccounts - Collapsible */}
      <div className="card p-4">
        <button
          onClick={() => setShowSubaccountDetails(!showSubaccountDetails)}
          className="flex items-center justify-between w-full text-left"
        >
          <h3 className="text-xs font-semibold text-[var(--color-text-tertiary)] uppercase">
            Subaccounts ({data.subaccounts.length})
          </h3>
          <span className="text-xs text-[var(--color-accent)]">
            {showSubaccountDetails ? 'Hide' : 'Show'} Details
          </span>
        </button>

        {showSubaccountDetails && (
          <div className="mt-3 space-y-2">
            {data.subaccounts.map((sa) => (
              <SubaccountStatusRow key={sa.id} sa={sa} />
            ))}
          </div>
        )}

        {!showSubaccountDetails && (
          <div className="mt-3 flex gap-4 text-sm">
            <span className="text-[var(--color-profit)]">
              {fundedCount} funded
            </span>
            <span className="text-[var(--color-loss)]">
              {data.subaccounts.filter((sa) => sa.status === 'underfunded').length} underfunded
            </span>
            <span className="text-[var(--color-text-tertiary)]">
              {data.subaccounts.filter((sa) => !sa.exists).length} missing
            </span>
          </div>
        )}
      </div>

      {/* Config Summary - Minimal */}
      <div className="card p-4">
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-xs font-semibold text-[var(--color-text-tertiary)] uppercase">
            Configuration
          </h3>
          {onNavigateToSettings && (
            <button
              onClick={onNavigateToSettings}
              className="text-xs text-[var(--color-accent)] hover:underline flex items-center gap-1"
            >
              <Edit2 className="w-3 h-3" />
              Edit in Settings
            </button>
          )}
        </div>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-sm">
          <div>
            <span className="text-[var(--color-text-tertiary)]">Subaccounts: </span>
            <span className="font-medium">{data.config_summary.num_subaccounts}</span>
          </div>
          <div>
            <span className="text-[var(--color-text-tertiary)]">Capital/Sub: </span>
            <span className="font-medium">${data.config_summary.capital_per_subaccount}</span>
          </div>
          <div>
            <span className="text-[var(--color-text-tertiary)]">Min Balance: </span>
            <span className="font-medium">${data.config_summary.min_operational}</span>
          </div>
          <div>
            <span className="text-[var(--color-text-tertiary)]">Max Live: </span>
            <span className="font-medium">{data.config_summary.max_live_strategies}</span>
          </div>
        </div>
      </div>
    </div>
  );
}

// === Main Page ===

export default function System() {
  const [activeTab, setActiveTab] = useState<TabType>('golive');
  const [settingsSubTab, setSettingsSubTab] = useState<'services' | 'config'>('services');

  const navigateToConfig = () => {
    setSettingsSubTab('config');
    setActiveTab('settings');
  };

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
      {activeTab === 'golive' && <GoLiveTab onNavigateToSettings={navigateToConfig} />}
      {activeTab === 'tasks' && <TasksTab />}
      {activeTab === 'logs' && <LogsTab />}
      {activeTab === 'settings' && <SettingsTab initialSubTab={settingsSubTab} />}
    </div>
  );
}
