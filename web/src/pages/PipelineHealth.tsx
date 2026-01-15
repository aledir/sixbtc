import { useState } from 'react';
import {
  useMetricsSnapshot,
  useMetricsAlerts,
  useMetricsTimeseries,
} from '../hooks/useApi';
import type {
  MetricAlert,
  MetricsPeriod,
  MetricsType,
  MetricsSnapshotResponse,
  QueueDepthsDataPoint,
  ThroughputDataPoint,
} from '../types';
import {
  Activity,
  AlertTriangle,
  ArrowDown,
  Bell,
  Clock,
  TrendingUp,
  BarChart3,
  Zap,
  CheckCircle,
  XCircle,
  Filter,
  Shuffle,
  TestTube,
  Database,
  Play,
} from 'lucide-react';
import {
  BarChart,
  Bar,
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
  Legend,
  Cell,
} from 'recharts';

// === Utility Functions ===

function formatTimestamp(ts: string): string {
  return new Date(ts).toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' });
}

function formatNumber(n: number | null | undefined): string {
  if (n === null || n === undefined) return '-';
  if (n >= 1000) return `${(n / 1000).toFixed(1)}k`;
  return n.toFixed(n < 10 ? 1 : 0);
}

function formatPct(n: number | null | undefined): string {
  if (n === null || n === undefined) return '-';
  return `${(n * 100).toFixed(1)}%`;
}

// === Components ===

function MetricsAlertBanner({ alerts }: { alerts: MetricAlert[] }) {
  if (alerts.length === 0) return null;

  const sortedAlerts = [...alerts].sort((a, b) => {
    const order: Record<string, number> = { critical: 0, warning: 1, info: 2 };
    return order[a.severity] - order[b.severity];
  });

  return (
    <div className="space-y-2">
      {sortedAlerts.slice(0, 3).map((alert, i) => {
        const isCritical = alert.severity === 'critical';
        const isWarning = alert.severity === 'warning';
        return (
          <div
            key={i}
            className={`card p-3 flex items-center gap-3 ${
              isCritical ? 'border-[var(--color-loss)] bg-[var(--color-loss-bg)]' :
              isWarning ? 'border-[var(--color-warning)] bg-[var(--color-warning-bg)]' : ''
            }`}
          >
            <Bell className={`w-4 h-4 flex-shrink-0 ${
              isCritical ? 'text-[var(--color-loss)]' :
              isWarning ? 'text-[var(--color-warning)]' : 'text-[var(--color-text-tertiary)]'
            }`} />
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2">
                <span className={`badge ${isCritical ? 'badge-loss' : isWarning ? 'badge-warning' : 'badge-neutral'}`}>
                  {alert.severity}
                </span>
                <span className="text-xs text-[var(--color-text-tertiary)]">
                  {alert.type.replace('_', ' ')}
                </span>
              </div>
              <p className={`text-sm truncate ${
                isCritical ? 'text-[var(--color-loss)]' :
                isWarning ? 'text-[var(--color-warning)]' : 'text-[var(--color-text-secondary)]'
              }`}>{alert.message}</p>
            </div>
            <div className="text-right flex-shrink-0">
              {alert.current_value !== undefined && (
                <div className="text-sm font-mono">{alert.current_value.toFixed(2)}</div>
              )}
              <div className="text-xs text-[var(--color-text-tertiary)] flex items-center gap-1">
                <Clock className="w-3 h-3" />
                {alert.duration_minutes}m
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}

function PeriodSelector({ value, onChange }: { value: MetricsPeriod; onChange: (period: MetricsPeriod) => void }) {
  const periods: MetricsPeriod[] = ['1h', '6h', '24h', '7d', '30d'];

  return (
    <div className="flex gap-1 bg-[var(--color-bg-secondary)] rounded-lg p-1">
      {periods.map(period => (
        <button
          key={period}
          onClick={() => onChange(period)}
          className={`px-3 py-1.5 text-sm rounded-md transition-colors ${
            value === period
              ? 'bg-[var(--color-accent-muted)] text-[var(--color-accent)] font-medium'
              : 'text-[var(--color-text-tertiary)] hover:text-[var(--color-text-primary)]'
          }`}
        >
          {period}
        </button>
      ))}
    </div>
  );
}

// Full 10-step pipeline funnel
function PipelineFunnel({ snapshot }: { snapshot: MetricsSnapshotResponse }) {
  const { funnel, failures } = snapshot;

  // Define all 10 pipeline stages
  const stages = [
    { key: 'generated', label: 'Generated', value: funnel.generated, icon: Zap, color: '#6b7280' },
    { key: 'validated', label: 'Validated', value: funnel.validated, failed: funnel.validation_failed, icon: CheckCircle, color: '#3b82f6' },
    { key: 'combinations', label: 'Parametric', value: funnel.combinations_tested, icon: BarChart3, color: '#8b5cf6' },
    { key: 'is_passed', label: 'IS Backtest', value: funnel.is_passed, icon: TrendingUp, color: '#06b6d4' },
    { key: 'oos_passed', label: 'OOS Backtest', value: funnel.oos_passed, icon: TrendingUp, color: '#0891b2' },
    { key: 'score_passed', label: 'Score Filter', value: funnel.score_passed, failed: failures.score_reject, icon: Filter, color: '#f59e0b' },
    { key: 'shuffle_passed', label: 'Shuffle Test', value: funnel.shuffle_passed, failed: failures.shuffle_fail, icon: Shuffle, color: '#10b981' },
    { key: 'mw_passed', label: 'Multi-Window', value: funnel.multi_window_passed, failed: failures.mw_fail, icon: TestTube, color: '#14b8a6' },
    { key: 'robustness', label: 'Robustness', value: funnel.robustness_passed, icon: Database, color: '#22c55e' },
    { key: 'live', label: 'LIVE', value: funnel.live, icon: Play, color: '#10b981' },
  ];

  // Calculate conversion rates
  const maxValue = Math.max(...stages.map(s => s.value), 1);

  return (
    <div className="space-y-2">
      {stages.map((stage, i) => {
        const Icon = stage.icon;
        const widthPct = Math.max((stage.value / maxValue) * 100, 5);
        const prevValue = i > 0 ? stages[i - 1].value : stage.value;
        const conversionRate = prevValue > 0 ? (stage.value / prevValue) * 100 : 100;
        const isLast = i === stages.length - 1;

        return (
          <div key={stage.key}>
            <div className="flex items-center gap-3">
              <div className="w-24 flex items-center gap-2 text-sm">
                <Icon className="w-4 h-4" style={{ color: stage.color }} />
                <span className="text-[var(--color-text-secondary)] truncate">{stage.label}</span>
              </div>
              <div className="flex-1">
                <div className="h-8 bg-[var(--color-bg-secondary)] rounded-lg overflow-hidden relative">
                  <div
                    className="h-full rounded-lg transition-all duration-500"
                    style={{ width: `${widthPct}%`, backgroundColor: stage.color }}
                  />
                  <div className="absolute inset-0 flex items-center justify-between px-3">
                    <span className="text-sm font-mono font-medium text-white drop-shadow-sm">
                      {formatNumber(stage.value)}
                    </span>
                    {stage.failed !== undefined && stage.failed > 0 && (
                      <span className="text-xs text-[var(--color-loss)] bg-[var(--color-bg-primary)]/80 px-1 rounded">
                        -{stage.failed}
                      </span>
                    )}
                  </div>
                </div>
              </div>
              <div className="w-16 text-right">
                {i > 0 && (
                  <span className={`text-xs font-mono ${
                    conversionRate >= 80 ? 'text-[var(--color-profit)]' :
                    conversionRate >= 50 ? 'text-[var(--color-warning)]' :
                    'text-[var(--color-loss)]'
                  }`}>
                    {conversionRate.toFixed(0)}%
                  </span>
                )}
              </div>
            </div>
            {!isLast && (
              <div className="flex justify-center py-1">
                <ArrowDown className="w-4 h-4 text-[var(--color-text-tertiary)]" />
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}

// Real-time KPI cards from snapshot
function RealtimeKPIs({ snapshot }: { snapshot: MetricsSnapshotResponse }) {
  const { throughput, timing, pool, live } = snapshot;

  const kpis = [
    {
      label: 'Generated/24h',
      value: throughput.generated,
      icon: Zap,
    },
    {
      label: 'Validated/24h',
      value: throughput.validated,
      icon: CheckCircle,
    },
    {
      label: 'Backtested/24h',
      value: throughput.backtested,
      icon: TrendingUp,
    },
    {
      label: 'Pool Size',
      value: `${pool.size}/${pool.limit}`,
      icon: Database,
      warning: pool.size >= pool.limit * 0.9,
    },
    {
      label: 'Live Strategies',
      value: live.count,
      icon: Play,
      profit: live.count > 0,
    },
    {
      label: 'Avg BT Time',
      value: timing.backtesting ? `${(timing.backtesting / 1000).toFixed(1)}s` : '-',
      icon: Clock,
    },
  ];

  return (
    <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
      {kpis.map((kpi, i) => {
        const Icon = kpi.icon;
        return (
          <div key={i} className="card p-3">
            <div className="flex items-center gap-2 mb-1">
              <Icon className="w-4 h-4 text-[var(--color-text-tertiary)]" />
              <span className="text-xs text-[var(--color-text-tertiary)]">{kpi.label}</span>
            </div>
            <div className={`text-lg font-mono font-semibold ${
              kpi.warning ? 'text-[var(--color-warning)]' :
              kpi.profit ? 'text-[var(--color-profit)]' :
              'text-[var(--color-text-primary)]'
            }`}>
              {typeof kpi.value === 'number' ? formatNumber(kpi.value) : kpi.value}
            </div>
          </div>
        );
      })}
    </div>
  );
}

// Queue depths visualization
function QueueDepths({ snapshot }: { snapshot: MetricsSnapshotResponse }) {
  const { queue_depths, backpressure } = snapshot;

  const queues = [
    { name: 'Generated', value: queue_depths.generated ?? 0, limit: backpressure.gen_limit, color: '#6b7280' },
    { name: 'Validated', value: queue_depths.validated ?? 0, limit: backpressure.val_limit, color: '#3b82f6' },
    { name: 'BT Waiting', value: backpressure.bt_waiting, limit: 100, color: '#8b5cf6' },
    { name: 'BT Running', value: backpressure.bt_processing, limit: 10, color: '#06b6d4' },
    { name: 'Active', value: queue_depths.active ?? 0, limit: 300, color: '#10b981' },
    { name: 'Live', value: queue_depths.live ?? 0, limit: 30, color: '#22c55e' },
  ];

  return (
    <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
      {queues.map(q => {
        const pct = q.limit > 0 ? (q.value / q.limit) * 100 : 0;
        const isFull = pct >= 90;
        return (
          <div key={q.name} className="card p-3">
            <div className="flex items-center justify-between mb-2">
              <span className="text-xs text-[var(--color-text-tertiary)]">{q.name}</span>
              <span className={`text-xs font-mono ${isFull ? 'text-[var(--color-warning)]' : 'text-[var(--color-text-secondary)]'}`}>
                {q.value}/{q.limit}
              </span>
            </div>
            <div className="h-2 bg-[var(--color-bg-secondary)] rounded-full overflow-hidden">
              <div
                className="h-full rounded-full transition-all"
                style={{ width: `${Math.min(pct, 100)}%`, backgroundColor: isFull ? 'var(--color-warning)' : q.color }}
              />
            </div>
          </div>
        );
      })}
    </div>
  );
}

// Failure analysis
function FailureAnalysis({ snapshot }: { snapshot: MetricsSnapshotResponse }) {
  const { failures, is_backtest, oos_backtest, robustness } = snapshot;

  // Combine all failure reasons
  const failureData = [
    { stage: 'Validation', count: failures.validation, color: '#ef4444' },
    { stage: 'IS Sharpe', count: is_backtest.fail_reasons?.sharpe ?? 0, color: '#f97316' },
    { stage: 'IS WinRate', count: is_backtest.fail_reasons?.wr ?? 0, color: '#f59e0b' },
    { stage: 'IS Trades', count: is_backtest.fail_reasons?.trades ?? 0, color: '#eab308' },
    { stage: 'OOS Sharpe', count: oos_backtest.fail_reasons?.sharpe ?? 0, color: '#84cc16' },
    { stage: 'Score', count: failures.score_reject, color: '#22c55e' },
    { stage: 'Shuffle', count: failures.shuffle_fail, color: '#14b8a6' },
    { stage: 'Multi-Win', count: failures.mw_fail, color: '#06b6d4' },
    { stage: 'Robustness', count: robustness.failed, color: '#3b82f6' },
  ].filter(f => f.count > 0);

  if (failureData.length === 0) {
    return (
      <div className="text-center py-8 text-[var(--color-text-tertiary)]">
        No failures recorded in current period
      </div>
    );
  }

  return (
    <ResponsiveContainer width="100%" height={250}>
      <BarChart data={failureData} layout="vertical">
        <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
        <XAxis type="number" stroke="var(--color-text-tertiary)" fontSize={11} />
        <YAxis type="category" dataKey="stage" stroke="var(--color-text-tertiary)" fontSize={11} width={80} />
        <Tooltip
          contentStyle={{
            backgroundColor: 'var(--color-bg-secondary)',
            border: '1px solid var(--color-border)',
            borderRadius: '8px',
            fontSize: '12px'
          }}
        />
        <Bar dataKey="count" name="Failures">
          {failureData.map((entry, index) => (
            <Cell key={`cell-${index}`} fill={entry.color} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}

// Backtest quality stats
function BacktestQuality({ snapshot }: { snapshot: MetricsSnapshotResponse }) {
  const { is_backtest, oos_backtest, score, pool, robustness } = snapshot;

  const stats = [
    {
      label: 'IS Pass Rate',
      value: is_backtest.count > 0 ? formatPct(is_backtest.passed / is_backtest.count) : '-',
      detail: `${is_backtest.passed}/${is_backtest.count}`,
    },
    {
      label: 'IS Avg Sharpe',
      value: is_backtest.passed_avg?.sharpe?.toFixed(2) ?? '-',
      profit: (is_backtest.passed_avg?.sharpe ?? 0) >= 1.5,
    },
    {
      label: 'OOS Pass Rate',
      value: oos_backtest.count > 0 ? formatPct(oos_backtest.passed / oos_backtest.count) : '-',
      detail: `${oos_backtest.passed}/${oos_backtest.count}`,
    },
    {
      label: 'OOS Avg Sharpe',
      value: oos_backtest.passed_avg?.sharpe?.toFixed(2) ?? '-',
      profit: (oos_backtest.passed_avg?.sharpe ?? 0) >= 1.0,
    },
    {
      label: 'Score Threshold',
      value: score.min_score_threshold.toFixed(1),
    },
    {
      label: 'Avg Pool Score',
      value: pool.score_avg?.toFixed(1) ?? '-',
    },
    {
      label: 'Robustness Avg',
      value: robustness.pool.avg_robustness?.toFixed(2) ?? '-',
      profit: (robustness.pool.avg_robustness ?? 0) >= 0.8,
    },
    {
      label: 'Pool Win Rate',
      value: pool.quality.winrate_avg ? formatPct(pool.quality.winrate_avg) : '-',
      profit: (pool.quality.winrate_avg ?? 0) >= 0.55,
    },
  ];

  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
      {stats.map((stat, i) => (
        <div key={i} className="text-center">
          <div className="text-xs text-[var(--color-text-tertiary)] mb-1">{stat.label}</div>
          <div className={`text-lg font-mono font-semibold ${
            stat.profit ? 'text-[var(--color-profit)]' : 'text-[var(--color-text-primary)]'
          }`}>
            {stat.value}
          </div>
          {stat.detail && (
            <div className="text-xs text-[var(--color-text-tertiary)]">{stat.detail}</div>
          )}
        </div>
      ))}
    </div>
  );
}

// Source distribution
function SourceDistribution({ snapshot }: { snapshot: MetricsSnapshotResponse }) {
  const { generator, pool } = snapshot;

  // Combine generator and pool data by source
  const sources = Object.keys({ ...generator.by_source, ...pool.by_source });
  const data = sources.map(source => ({
    source: source.replace('pattern_gen', 'pgn').replace('pattern', 'pat'),
    generated: generator.by_source[source] ?? 0,
    inPool: pool.by_source[source] ?? 0,
    avgScore: pool.avg_score_by_source[source] ?? null,
  })).filter(d => d.generated > 0 || d.inPool > 0);

  if (data.length === 0) {
    return (
      <div className="text-center py-8 text-[var(--color-text-tertiary)]">
        No source data available
      </div>
    );
  }

  return (
    <ResponsiveContainer width="100%" height={250}>
      <BarChart data={data}>
        <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
        <XAxis dataKey="source" stroke="var(--color-text-tertiary)" fontSize={11} />
        <YAxis stroke="var(--color-text-tertiary)" fontSize={11} />
        <Tooltip
          contentStyle={{
            backgroundColor: 'var(--color-bg-secondary)',
            border: '1px solid var(--color-border)',
            borderRadius: '8px',
            fontSize: '12px'
          }}
        />
        <Legend />
        <Bar dataKey="generated" name="Generated (24h)" fill="#6b7280" />
        <Bar dataKey="inPool" name="In Pool" fill="#10b981" />
      </BarChart>
    </ResponsiveContainer>
  );
}

// Historical chart selector
function MetricTypeSelector({ value, onChange }: { value: MetricsType; onChange: (metric: MetricsType) => void }) {
  const metrics: { key: MetricsType; label: string }[] = [
    { key: 'queue_depths', label: 'Queues' },
    { key: 'throughput', label: 'Throughput' },
  ];

  return (
    <div className="flex gap-1 bg-[var(--color-bg-secondary)] rounded-lg p-1">
      {metrics.map(m => (
        <button
          key={m.key}
          onClick={() => onChange(m.key)}
          className={`px-3 py-1.5 text-sm rounded-md transition-colors ${
            value === m.key
              ? 'bg-[var(--color-accent-muted)] text-[var(--color-accent)] font-medium'
              : 'text-[var(--color-text-tertiary)] hover:text-[var(--color-text-primary)]'
          }`}
        >
          {m.label}
        </button>
      ))}
    </div>
  );
}

// Historical timeseries chart
function TimeseriesChart({ data, type }: { data: any[]; type: MetricsType }) {
  if (type === 'queue_depths') {
    const chartData = data.map((d: QueueDepthsDataPoint) => ({
      time: formatTimestamp(d.timestamp),
      Generated: d.generated,
      Validated: d.validated,
      Active: d.active,
      Live: d.live,
    }));

    return (
      <ResponsiveContainer width="100%" height={250}>
        <LineChart data={chartData}>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
          <XAxis dataKey="time" stroke="var(--color-text-tertiary)" fontSize={11} />
          <YAxis stroke="var(--color-text-tertiary)" fontSize={11} />
          <Tooltip
            contentStyle={{
              backgroundColor: 'var(--color-bg-secondary)',
              border: '1px solid var(--color-border)',
              borderRadius: '8px',
              fontSize: '12px'
            }}
          />
          <Legend />
          <Line type="monotone" dataKey="Generated" stroke="#6b7280" strokeWidth={2} dot={false} />
          <Line type="monotone" dataKey="Validated" stroke="#3b82f6" strokeWidth={2} dot={false} />
          <Line type="monotone" dataKey="Active" stroke="#a855f7" strokeWidth={2} dot={false} />
          <Line type="monotone" dataKey="Live" stroke="#10b981" strokeWidth={2} dot={false} />
        </LineChart>
      </ResponsiveContainer>
    );
  }

  if (type === 'throughput') {
    const chartData = data.map((d: ThroughputDataPoint) => ({
      time: formatTimestamp(d.timestamp),
      Generation: d.generation ?? 0,
      Validation: d.validation ?? 0,
      Backtesting: d.backtesting ?? 0,
    }));

    return (
      <ResponsiveContainer width="100%" height={250}>
        <LineChart data={chartData}>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--color-border)" />
          <XAxis dataKey="time" stroke="var(--color-text-tertiary)" fontSize={11} />
          <YAxis stroke="var(--color-text-tertiary)" fontSize={11} />
          <Tooltip
            contentStyle={{
              backgroundColor: 'var(--color-bg-secondary)',
              border: '1px solid var(--color-border)',
              borderRadius: '8px',
              fontSize: '12px'
            }}
          />
          <Legend />
          <Line type="monotone" dataKey="Generation" stroke="#6b7280" strokeWidth={2} dot={false} />
          <Line type="monotone" dataKey="Validation" stroke="#3b82f6" strokeWidth={2} dot={false} />
          <Line type="monotone" dataKey="Backtesting" stroke="#10b981" strokeWidth={2} dot={false} />
        </LineChart>
      </ResponsiveContainer>
    );
  }

  return null;
}

// === Main Page ===

export default function PipelineHealth() {
  const [period, setPeriod] = useState<MetricsPeriod>('24h');
  const [activeMetric, setActiveMetric] = useState<MetricsType>('throughput');

  const { data: snapshot, isLoading: snapshotLoading, error: snapshotError } = useMetricsSnapshot();
  const { data: alerts } = useMetricsAlerts();
  const { data: timeseries } = useMetricsTimeseries({ period, metric: activeMetric });

  if (snapshotLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Activity className="w-8 h-8 animate-spin text-[var(--color-text-tertiary)]" />
      </div>
    );
  }

  if (snapshotError || !snapshot) {
    return (
      <div className="card border-[var(--color-loss)]/20 bg-[var(--color-loss-bg)]">
        <div className="text-center py-8">
          <XCircle className="w-12 h-12 text-[var(--color-loss)] mx-auto mb-3" />
          <p className="text-[var(--color-loss)] font-medium">Failed to load pipeline metrics</p>
          <p className="text-sm text-[var(--color-text-tertiary)] mt-2">Check if the backend is running</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-[var(--color-text-primary)]">Pipeline Health</h1>
          <p className="text-sm text-[var(--color-text-secondary)] mt-1">
            10-step strategy validation funnel
          </p>
        </div>
        <div className="flex items-center gap-3">
          <span className={`badge ${
            snapshot.status === 'OK' ? 'badge-profit' :
            snapshot.status === 'WARNING' ? 'badge-warning' : 'badge-loss'
          }`}>
            {snapshot.status}
          </span>
          <span className={`badge ${snapshot.trading_mode === 'LIVE' ? 'badge-profit' : 'badge-warning'}`}>
            {snapshot.trading_mode}
          </span>
        </div>
      </div>

      {/* Alerts */}
      {alerts?.alerts && alerts.alerts.length > 0 && (
        <MetricsAlertBanner alerts={alerts.alerts} />
      )}

      {/* Issue Banner */}
      {snapshot.issue && (
        <div className="card border-[var(--color-warning)] bg-[var(--color-warning-bg)] p-3">
          <div className="flex items-center gap-2">
            <AlertTriangle className="w-5 h-5 text-[var(--color-warning)]" />
            <span className="text-sm text-[var(--color-warning)]">{snapshot.issue}</span>
          </div>
        </div>
      )}

      {/* Real-time KPIs */}
      <RealtimeKPIs snapshot={snapshot} />

      {/* Queue Depths */}
      <div className="card">
        <h2 className="text-lg font-semibold text-[var(--color-text-primary)] mb-4">Queue Depths</h2>
        <QueueDepths snapshot={snapshot} />
      </div>

      {/* Pipeline Funnel */}
      <div className="card">
        <h2 className="text-lg font-semibold text-[var(--color-text-primary)] mb-4">
          Pipeline Funnel (24h)
        </h2>
        <PipelineFunnel snapshot={snapshot} />
      </div>

      {/* Backtest Quality Stats */}
      <div className="card">
        <h2 className="text-lg font-semibold text-[var(--color-text-primary)] mb-4">Backtest Quality</h2>
        <BacktestQuality snapshot={snapshot} />
      </div>

      {/* Two column layout for charts */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Failure Analysis */}
        <div className="card">
          <h2 className="text-lg font-semibold text-[var(--color-text-primary)] mb-4">Failure Analysis</h2>
          <FailureAnalysis snapshot={snapshot} />
        </div>

        {/* Source Distribution */}
        <div className="card">
          <h2 className="text-lg font-semibold text-[var(--color-text-primary)] mb-4">Source Distribution</h2>
          <SourceDistribution snapshot={snapshot} />
        </div>
      </div>

      {/* Historical Metrics */}
      <div className="card">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-4">
          <h2 className="text-lg font-semibold text-[var(--color-text-primary)]">Historical Trends</h2>
          <div className="flex items-center gap-3">
            <PeriodSelector value={period} onChange={setPeriod} />
            <MetricTypeSelector value={activeMetric} onChange={setActiveMetric} />
          </div>
        </div>
        {timeseries && timeseries.data.length > 0 ? (
          <TimeseriesChart data={timeseries.data} type={activeMetric} />
        ) : (
          <div className="h-64 flex items-center justify-center text-[var(--color-text-tertiary)]">
            No historical data available
          </div>
        )}
      </div>
    </div>
  );
}
