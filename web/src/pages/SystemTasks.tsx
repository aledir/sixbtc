import { useState } from 'react';
import {
  useTaskExecutions,
  useCoinRegistryStats,
  usePairsUpdateHistory,
  useSchedulerHealth,
  useTriggerTask
} from '../hooks/useApi';
import { AlertCircle, CheckCircle, Clock, Play, Activity } from 'lucide-react';

function TaskStatusBadge({ status }: { status: string }) {
  const colors: Record<string, string> = {
    SUCCESS: 'badge-profit',
    FAILED: 'badge-loss',
    RUNNING: 'badge-warning'
  };

  const icons: Record<string, React.ReactNode> = {
    SUCCESS: <CheckCircle className="w-3 h-3" />,
    FAILED: <AlertCircle className="w-3 h-3" />,
    RUNNING: <Clock className="w-3 h-3" />
  };

  return (
    <span className={`badge ${colors[status] || 'badge-neutral'} inline-flex items-center gap-1`}>
      {icons[status]}
      {status}
    </span>
  );
}

export default function SystemTasks() {
  const [selectedTaskType, setSelectedTaskType] = useState<string | null>(null);

  const { data: health } = useSchedulerHealth();
  const { data: executions } = useTaskExecutions({ task_type: selectedTaskType || undefined });
  const { data: registryStats } = useCoinRegistryStats();
  const { data: pairsHistory } = usePairsUpdateHistory(10);

  const { mutate: triggerTask, isPending: isTriggering } = useTriggerTask();

  const handleTriggerTask = (taskName: string) => {
    if (confirm(`Are you sure you want to manually trigger '${taskName}'?`)) {
      triggerTask({
        taskName,
        triggeredBy: 'user:web-dashboard'
      });
    }
  };

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div>
        <h1 className="text-2xl font-bold text-[var(--color-text-primary)]">System Tasks</h1>
        <p className="text-sm text-[var(--color-text-secondary)] mt-1">
          Monitor and control scheduled operations
        </p>
      </div>

      {/* Top Stats - 2 cols mobile, 4 cols desktop */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="card">
          <p className="text-xs text-[var(--color-text-tertiary)] uppercase mb-1">Status</p>
          <p className="text-xl font-bold text-[var(--color-text-primary)]">
            {health?.status === 'healthy' ? 'Healthy' : 'Unhealthy'}
          </p>
        </div>
        <div className="card">
          <p className="text-xs text-[var(--color-text-tertiary)] uppercase mb-1">Executions (1h)</p>
          <p className="text-xl font-bold text-[var(--color-text-primary)]">{health?.recent_executions_1h || 0}</p>
        </div>
        <div className="card">
          <p className="text-xs text-[var(--color-text-tertiary)] uppercase mb-1">Failures (1h)</p>
          <p className="text-xl font-bold text-[var(--color-loss)]">{health?.recent_failures_1h || 0}</p>
        </div>
        <div className="card">
          <p className="text-xs text-[var(--color-text-tertiary)] uppercase mb-1">Running</p>
          <p className="text-xl font-bold text-[var(--color-text-primary)]">{health?.currently_running || 0}</p>
        </div>
      </div>

      {/* Coin Registry Stats */}
      <div className="card">
        <h2 className="text-sm font-semibold text-[var(--color-text-tertiary)] uppercase mb-4">Coin Registry</h2>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <div>
            <p className="text-xs text-[var(--color-text-tertiary)] uppercase mb-1">Active Coins</p>
            <p className="text-xl font-bold text-[var(--color-text-primary)]">{registryStats?.active_coins || 0}</p>
            <p className="text-xs text-[var(--color-text-tertiary)] mt-1">
              of {registryStats?.total_coins || 0} total
            </p>
          </div>
          <div>
            <p className="text-xs text-[var(--color-text-tertiary)] uppercase mb-1">Cache Age</p>
            <p className="text-xl font-bold text-[var(--color-text-primary)]">
              {registryStats?.cache_age_seconds
                ? `${Math.floor(registryStats.cache_age_seconds)}s`
                : 'N/A'}
            </p>
          </div>
          <div>
            <p className="text-xs text-[var(--color-text-tertiary)] uppercase mb-1">Last Update</p>
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
          <h2 className="text-sm font-semibold text-[var(--color-text-tertiary)] uppercase">Recent Executions</h2>
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
                  <p className="font-medium text-[var(--color-text-primary)]">{exec.task_name}</p>
                  <TaskStatusBadge status={exec.status} />
                  <span className="text-xs text-[var(--color-text-tertiary)] hide-mobile">{exec.task_type}</span>
                </div>
                <p className="text-xs text-[var(--color-text-tertiary)] mt-1">
                  Started: {new Date(exec.started_at).toLocaleString()}
                  {exec.duration_seconds && ` | Duration: ${exec.duration_seconds.toFixed(2)}s`}
                </p>
                {exec.error_message && (
                  <p className="text-xs text-[var(--color-loss)] mt-1 truncate">Error: {exec.error_message}</p>
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
          <h2 className="text-sm font-semibold text-[var(--color-text-tertiary)] uppercase">Pairs Update History</h2>
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
                  <p className="font-medium text-[var(--color-text-primary)]">{update.total_pairs}</p>
                </div>
                <div>
                  <p className="text-xs text-[var(--color-text-tertiary)]">New</p>
                  <p className="font-medium text-[var(--color-profit)]">+{update.new_pairs}</p>
                </div>
                <div>
                  <p className="text-xs text-[var(--color-text-tertiary)]">Updated</p>
                  <p className="font-medium text-[var(--color-text-primary)]">{update.updated_pairs}</p>
                </div>
                <div>
                  <p className="text-xs text-[var(--color-text-tertiary)]">Deactivated</p>
                  <p className="font-medium text-[var(--color-loss)]">-{update.deactivated_pairs}</p>
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
