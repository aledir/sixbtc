import { useState } from 'react';
import {
  useTaskExecutions,
  useCoinRegistryStats,
  usePairsUpdateHistory,
  useSchedulerHealth,
  useTriggerTask
} from '../hooks/useApi';
import { AlertCircle, CheckCircle, Clock, Play } from 'lucide-react';

function TaskStatusBadge({ status }: { status: string }) {
  const colors: Record<string, string> = {
    SUCCESS: 'bg-green-500/20 text-green-400 border-green-500/30',
    FAILED: 'bg-red-500/20 text-red-400 border-red-500/30',
    RUNNING: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30'
  };

  const icons: Record<string, React.ReactNode> = {
    SUCCESS: <CheckCircle className="w-3 h-3" />,
    FAILED: <AlertCircle className="w-3 h-3" />,
    RUNNING: <Clock className="w-3 h-3" />
  };

  return (
    <span className={`inline-flex items-center gap-1 px-2 py-1 rounded border text-xs font-medium ${colors[status] || 'bg-gray-500/20 text-gray-400 border-gray-500/30'}`}>
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
        <h1 className="text-2xl font-bold text-foreground">System Tasks</h1>
        <p className="text-sm text-muted-foreground mt-1">
          Monitor and control scheduled operations
        </p>
      </div>

      {/* Scheduler Health */}
      <div className="bg-card border border-border rounded-lg p-6">
        <h2 className="text-lg font-semibold text-foreground mb-4">Scheduler Health</h2>
        <div className="grid grid-cols-4 gap-4">
          <div>
            <p className="text-xs text-muted-foreground uppercase mb-1">Status</p>
            <p className="text-xl font-bold text-foreground">
              {health?.status === 'healthy' ? '✓ Healthy' : '⚠ Unhealthy'}
            </p>
          </div>
          <div>
            <p className="text-xs text-muted-foreground uppercase mb-1">Executions (1h)</p>
            <p className="text-xl font-bold text-foreground">{health?.recent_executions_1h || 0}</p>
          </div>
          <div>
            <p className="text-xs text-muted-foreground uppercase mb-1">Failures (1h)</p>
            <p className="text-xl font-bold text-destructive">{health?.recent_failures_1h || 0}</p>
          </div>
          <div>
            <p className="text-xs text-muted-foreground uppercase mb-1">Currently Running</p>
            <p className="text-xl font-bold text-foreground">{health?.currently_running || 0}</p>
          </div>
        </div>
      </div>

      {/* Coin Registry Stats */}
      <div className="bg-card border border-border rounded-lg p-6">
        <h2 className="text-lg font-semibold text-foreground mb-4">Coin Registry</h2>
        <div className="grid grid-cols-3 gap-4">
          <div>
            <p className="text-xs text-muted-foreground uppercase mb-1">Active Coins</p>
            <p className="text-xl font-bold text-foreground">{registryStats?.active_coins || 0}</p>
            <p className="text-xs text-muted-foreground mt-1">
              of {registryStats?.total_coins || 0} total
            </p>
          </div>
          <div>
            <p className="text-xs text-muted-foreground uppercase mb-1">Cache Age</p>
            <p className="text-xl font-bold text-foreground">
              {registryStats?.cache_age_seconds
                ? `${Math.floor(registryStats.cache_age_seconds)}s`
                : 'N/A'}
            </p>
          </div>
          <div>
            <p className="text-xs text-muted-foreground uppercase mb-1">Last Update</p>
            <p className="text-sm text-foreground mt-1">
              {registryStats?.db_updated_at
                ? new Date(registryStats.db_updated_at).toLocaleString()
                : 'Never'}
            </p>
          </div>
        </div>
      </div>

      {/* Task Execution History */}
      <div className="bg-card border border-border rounded-lg p-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold text-foreground">Recent Executions</h2>
          <div className="flex gap-2">
            <button
              className={`px-3 py-1 rounded text-sm font-medium transition-colors ${
                selectedTaskType === null
                  ? 'bg-primary text-primary-foreground'
                  : 'bg-secondary text-secondary-foreground hover:bg-secondary/80'
              }`}
              onClick={() => setSelectedTaskType(null)}
            >
              All
            </button>
            <button
              className={`px-3 py-1 rounded text-sm font-medium transition-colors ${
                selectedTaskType === 'scheduler'
                  ? 'bg-primary text-primary-foreground'
                  : 'bg-secondary text-secondary-foreground hover:bg-secondary/80'
              }`}
              onClick={() => setSelectedTaskType('scheduler')}
            >
              Scheduler
            </button>
            <button
              className={`px-3 py-1 rounded text-sm font-medium transition-colors ${
                selectedTaskType === 'data_update'
                  ? 'bg-primary text-primary-foreground'
                  : 'bg-secondary text-secondary-foreground hover:bg-secondary/80'
              }`}
              onClick={() => setSelectedTaskType('data_update')}
            >
              Data Updates
            </button>
          </div>
        </div>

        <div className="space-y-2">
          {executions?.executions.map((exec) => (
            <div
              key={exec.id}
              className="flex items-center justify-between p-3 bg-background rounded border border-border"
            >
              <div className="flex-1">
                <div className="flex items-center gap-2">
                  <p className="font-medium text-foreground">{exec.task_name}</p>
                  <TaskStatusBadge status={exec.status} />
                  <span className="text-xs text-muted-foreground">{exec.task_type}</span>
                </div>
                <p className="text-xs text-muted-foreground mt-1">
                  Started: {new Date(exec.started_at).toLocaleString()}
                  {exec.duration_seconds && ` • Duration: ${exec.duration_seconds.toFixed(2)}s`}
                </p>
                {exec.error_message && (
                  <p className="text-xs text-destructive mt-1">Error: {exec.error_message}</p>
                )}
              </div>
              <div className="text-xs text-muted-foreground">
                {exec.triggered_by}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Pairs Update History */}
      <div className="bg-card border border-border rounded-lg p-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold text-foreground">Pairs Update History</h2>
          <button
            className="inline-flex items-center gap-2 px-3 py-1 bg-primary text-primary-foreground rounded text-sm font-medium hover:bg-primary/90 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            onClick={() => handleTriggerTask('update_pairs')}
            disabled={isTriggering}
          >
            <Play className="w-4 h-4" />
            Trigger Update
          </button>
        </div>

        <div className="space-y-2">
          {pairsHistory?.updates.map((update) => (
            <div
              key={update.execution_id}
              className="p-3 bg-background rounded border border-border"
            >
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-2">
                  <TaskStatusBadge status={update.status} />
                  <span className="text-sm text-foreground">
                    {new Date(update.started_at).toLocaleString()}
                  </span>
                </div>
                {update.duration_seconds && (
                  <span className="text-xs text-muted-foreground">
                    {update.duration_seconds.toFixed(2)}s
                  </span>
                )}
              </div>

              <div className="grid grid-cols-4 gap-4 text-sm">
                <div>
                  <p className="text-xs text-muted-foreground">Total</p>
                  <p className="font-medium text-foreground">{update.total_pairs}</p>
                </div>
                <div>
                  <p className="text-xs text-muted-foreground">New</p>
                  <p className="font-medium text-green-400">+{update.new_pairs}</p>
                </div>
                <div>
                  <p className="text-xs text-muted-foreground">Updated</p>
                  <p className="font-medium text-foreground">{update.updated_pairs}</p>
                </div>
                <div>
                  <p className="text-xs text-muted-foreground">Deactivated</p>
                  <p className="font-medium text-destructive">-{update.deactivated_pairs}</p>
                </div>
              </div>

              {update.top_10_symbols.length > 0 && (
                <div className="mt-2">
                  <p className="text-xs text-muted-foreground mb-1">Top 10:</p>
                  <p className="text-xs font-mono text-foreground">
                    {update.top_10_symbols.join(', ')}
                  </p>
                </div>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
