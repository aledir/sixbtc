import { useState } from 'react';
import {
  usePipelineHealth,
  useQualityDistribution,
  useMetricsAlerts,
  useMetricsAggregated,
  useMetricsTimeseries,
} from '../hooks/useApi';
import { useTheme } from '../contexts/ThemeContext';
import type {
  PipelineStageHealth,
  QualityDistributionResponse,
  MetricAlert,
  MetricsAggregatedResponse,
  MetricsPeriod,
  MetricsType,
  QueueDepthsDataPoint,
  ThroughputDataPoint,
  QualityDataPoint,
  UtilizationDataPoint,
  SuccessRatesDataPoint
} from '../types';
import { Activity, AlertTriangle, ArrowRight, Bell, Clock, TrendingUp, Gauge, BarChart3, Zap, CheckCircle } from 'lucide-react';
import {
  BarChart, Bar, LineChart, Line, AreaChart, Area,
  XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, Legend
} from 'recharts';

// === Utility Functions ===

function getStatusColor(status: string): string {
  const colors: Record<string, string> = {
    'healthy': 'bg-[var(--color-profit)]',
    'backpressure': 'bg-[var(--color-warning)]',
    'stalled': 'bg-[var(--color-loss)]',
    'error': 'bg-[var(--color-loss)]',
    'degraded': 'bg-[var(--color-warning)]',
    'critical': 'bg-[var(--color-loss)]',
  };
  return colors[status] || 'bg-[var(--color-text-tertiary)]';
}


function formatTimestamp(ts: string): string {
  return new Date(ts).toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' });
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

function MetricTypeSelector({ value, onChange }: { value: MetricsType; onChange: (metric: MetricsType) => void }) {
  const metrics: { key: MetricsType; label: string; icon: React.ReactNode }[] = [
    { key: 'queue_depths', label: 'Queues', icon: <BarChart3 className="w-4 h-4" /> },
    { key: 'throughput', label: 'Throughput', icon: <TrendingUp className="w-4 h-4" /> },
    { key: 'quality', label: 'Quality', icon: <Zap className="w-4 h-4" /> },
    { key: 'utilization', label: 'Utilization', icon: <Gauge className="w-4 h-4" /> },
    { key: 'success_rates', label: 'Success', icon: <CheckCircle className="w-4 h-4" /> },
  ];

  return (
    <div className="flex flex-wrap gap-2">
      {metrics.map(m => (
        <button
          key={m.key}
          onClick={() => onChange(m.key)}
          className={`btn ${value === m.key ? 'btn-primary' : 'btn-ghost'} text-xs px-2 py-1`}
        >
          {m.icon}
          <span className="hide-mobile">{m.label}</span>
        </button>
      ))}
    </div>
  );
}

function AggregatedKPICards({ data }: { data: MetricsAggregatedResponse }) {
  const kpis = [
    {
      label: 'Avg Queue',
      value: Math.round(data.queue_depths.avg_generated + data.queue_depths.avg_validated + data.queue_depths.avg_active),
      detail: `G:${data.queue_depths.avg_generated.toFixed(0)} V:${data.queue_depths.avg_validated.toFixed(0)}`,
    },
    {
      label: 'Max Util',
      value: `${(Math.max(data.utilization.max_generated, data.utilization.max_validated, data.utilization.max_active) * 100).toFixed(0)}%`,
      warning: Math.max(data.utilization.max_generated, data.utilization.max_validated, data.utilization.max_active) > 0.9,
    },
    {
      label: 'Avg Sharpe',
      value: data.quality.avg_sharpe?.toFixed(2) ?? '-',
      profit: data.quality.avg_sharpe && data.quality.avg_sharpe >= 1.0,
    },
    {
      label: 'Win Rate',
      value: data.quality.avg_win_rate ? `${(data.quality.avg_win_rate * 100).toFixed(1)}%` : '-',
      profit: data.quality.avg_win_rate && data.quality.avg_win_rate >= 0.55,
    },
  ];

  return (
    <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
      {kpis.map((kpi, i) => (
        <div key={i} className="card">
          <div className="metric-label">{kpi.label}</div>
          <div className={`metric-value ${
            kpi.warning ? 'text-[var(--color-warning)]' : kpi.profit ? 'text-[var(--color-profit)]' : ''
          }`}>
            {kpi.value}
          </div>
          {kpi.detail && <div className="text-xs text-[var(--color-text-tertiary)] mt-1">{kpi.detail}</div>}
        </div>
      ))}
    </div>
  );
}

function PipelineFlowDiagram({ stages }: { stages: PipelineStageHealth[] }) {
  return (
    <div className="flex flex-col md:flex-row items-stretch md:items-center justify-between gap-4">
      {stages.map((stage, i) => (
        <div key={stage.stage} className="flex flex-col md:flex-row items-center gap-2 md:gap-4 flex-1">
          <div className="w-full card">
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm font-semibold capitalize text-[var(--color-text-primary)]">{stage.stage}</span>
              <div className={`w-3 h-3 rounded-full ${getStatusColor(stage.status)}`} />
            </div>
            <div className="text-xs text-[var(--color-text-tertiary)] space-y-1">
              <div>Queue: {stage.queue_depth} / {stage.queue_limit}</div>
              <div>Rate: {stage.processing_rate.toFixed(1)}/h</div>
            </div>
          </div>
          {i < stages.length - 1 && (
            <ArrowRight className="w-5 h-5 text-[var(--color-text-tertiary)] flex-shrink-0 rotate-90 md:rotate-0" />
          )}
        </div>
      ))}
    </div>
  );
}

function StageDetailCard({ stage }: { stage: PipelineStageHealth }) {
  return (
    <div className="card">
      <div className="flex items-center justify-between mb-3">
        <h3 className="font-semibold capitalize text-[var(--color-text-primary)]">{stage.stage}</h3>
        <span className={`badge ${
          stage.status === 'healthy' ? 'badge-profit' :
          stage.status === 'backpressure' ? 'badge-warning' : 'badge-loss'
        }`}>{stage.status}</span>
      </div>
      <div className="mb-4">
        <div className="flex justify-between text-xs mb-1">
          <span className="text-[var(--color-text-tertiary)]">Queue Utilization</span>
          <span className="text-[var(--color-text-secondary)]">{stage.queue_depth} / {stage.queue_limit}</span>
        </div>
        <div className="h-2 bg-[var(--color-bg-secondary)] rounded-full overflow-hidden">
          <div
            className={`h-full ${getStatusColor(stage.status)}`}
            style={{ width: `${Math.min(stage.utilization_pct, 100)}%` }}
          />
        </div>
        <div className="text-xs text-[var(--color-text-tertiary)] mt-1 text-right">
          {stage.utilization_pct.toFixed(1)}%
        </div>
      </div>
      <div className="grid grid-cols-2 gap-3 text-sm">
        <div>
          <div className="text-xs text-[var(--color-text-tertiary)]">Rate</div>
          <div className="font-mono text-[var(--color-text-primary)]">{stage.processing_rate.toFixed(1)}/h</div>
        </div>
        <div>
          <div className="text-xs text-[var(--color-text-tertiary)]">Success</div>
          <div className="font-mono text-[var(--color-text-primary)]">{stage.success_rate.toFixed(1)}%</div>
        </div>
        <div>
          <div className="text-xs text-[var(--color-text-tertiary)]">Last Hour</div>
          <div className="font-mono text-[var(--color-text-primary)]">{stage.processed_last_hour}</div>
        </div>
        <div>
          <div className="text-xs text-[var(--color-text-tertiary)]">Workers</div>
          <div className="font-mono text-[var(--color-text-primary)]">{stage.active_workers}/{stage.max_workers}</div>
        </div>
      </div>
    </div>
  );
}

// Chart components use theme-aware colors
function TimeseriesChart({ data, type, theme }: { data: any[]; type: MetricsType; theme: string }) {
  const chartColors = {
    grid: theme === 'dark' ? '#334155' : '#e2e8f0',
    axis: theme === 'dark' ? '#64748b' : '#94a3b8',
    tooltip: {
      bg: theme === 'dark' ? '#1e293b' : '#ffffff',
      border: theme === 'dark' ? '#334155' : '#e2e8f0',
    },
  };

  if (type === 'queue_depths') {
    const chartData = data.map((d: QueueDepthsDataPoint) => ({
      time: formatTimestamp(d.timestamp),
      Generated: d.generated,
      Validated: d.validated,
      Active: d.active,
      Live: d.live,
    }));

    return (
      <ResponsiveContainer width="100%" height={300}>
        <LineChart data={chartData}>
          <CartesianGrid strokeDasharray="3 3" stroke={chartColors.grid} />
          <XAxis dataKey="time" stroke={chartColors.axis} fontSize={11} />
          <YAxis stroke={chartColors.axis} fontSize={11} />
          <Tooltip contentStyle={{ backgroundColor: chartColors.tooltip.bg, border: `1px solid ${chartColors.tooltip.border}`, borderRadius: '8px', fontSize: '12px' }} />
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
      <ResponsiveContainer width="100%" height={300}>
        <LineChart data={chartData}>
          <CartesianGrid strokeDasharray="3 3" stroke={chartColors.grid} />
          <XAxis dataKey="time" stroke={chartColors.axis} fontSize={11} />
          <YAxis stroke={chartColors.axis} fontSize={11} />
          <Tooltip contentStyle={{ backgroundColor: chartColors.tooltip.bg, border: `1px solid ${chartColors.tooltip.border}`, borderRadius: '8px', fontSize: '12px' }} />
          <Legend />
          <Line type="monotone" dataKey="Generation" stroke="#6b7280" strokeWidth={2} dot={false} />
          <Line type="monotone" dataKey="Validation" stroke="#3b82f6" strokeWidth={2} dot={false} />
          <Line type="monotone" dataKey="Backtesting" stroke="#10b981" strokeWidth={2} dot={false} />
        </LineChart>
      </ResponsiveContainer>
    );
  }

  if (type === 'quality') {
    const chartData = data.map((d: QualityDataPoint) => ({
      time: formatTimestamp(d.timestamp),
      Sharpe: d.avg_sharpe ?? 0,
      'Win Rate': d.avg_win_rate ? d.avg_win_rate * 100 : 0,
    }));

    return (
      <ResponsiveContainer width="100%" height={300}>
        <LineChart data={chartData}>
          <CartesianGrid strokeDasharray="3 3" stroke={chartColors.grid} />
          <XAxis dataKey="time" stroke={chartColors.axis} fontSize={11} />
          <YAxis yAxisId="left" stroke={chartColors.axis} fontSize={11} />
          <YAxis yAxisId="right" orientation="right" stroke={chartColors.axis} fontSize={11} unit="%" />
          <Tooltip contentStyle={{ backgroundColor: chartColors.tooltip.bg, border: `1px solid ${chartColors.tooltip.border}`, borderRadius: '8px', fontSize: '12px' }} />
          <Legend />
          <Line yAxisId="left" type="monotone" dataKey="Sharpe" stroke="#10b981" strokeWidth={2} dot={false} />
          <Line yAxisId="right" type="monotone" dataKey="Win Rate" stroke="#3b82f6" strokeWidth={2} dot={false} />
        </LineChart>
      </ResponsiveContainer>
    );
  }

  if (type === 'utilization') {
    const chartData = data.map((d: UtilizationDataPoint) => ({
      time: formatTimestamp(d.timestamp),
      Generated: (d.generated ?? 0) * 100,
      Validated: (d.validated ?? 0) * 100,
      Active: (d.active ?? 0) * 100,
    }));

    return (
      <ResponsiveContainer width="100%" height={300}>
        <AreaChart data={chartData}>
          <CartesianGrid strokeDasharray="3 3" stroke={chartColors.grid} />
          <XAxis dataKey="time" stroke={chartColors.axis} fontSize={11} />
          <YAxis stroke={chartColors.axis} fontSize={11} unit="%" domain={[0, 100]} />
          <Tooltip contentStyle={{ backgroundColor: chartColors.tooltip.bg, border: `1px solid ${chartColors.tooltip.border}`, borderRadius: '8px', fontSize: '12px' }} formatter={(value) => typeof value === 'number' ? `${value.toFixed(1)}%` : value} />
          <Legend />
          <Area type="monotone" dataKey="Generated" stroke="#6b7280" fill="#6b7280" fillOpacity={0.3} />
          <Area type="monotone" dataKey="Validated" stroke="#3b82f6" fill="#3b82f6" fillOpacity={0.3} />
          <Area type="monotone" dataKey="Active" stroke="#a855f7" fill="#a855f7" fillOpacity={0.3} />
        </AreaChart>
      </ResponsiveContainer>
    );
  }

  if (type === 'success_rates') {
    const chartData = data.map((d: SuccessRatesDataPoint) => ({
      time: formatTimestamp(d.timestamp),
      Validation: d.validation ? d.validation * 100 : 0,
      Backtesting: d.backtesting ? d.backtesting * 100 : 0,
    }));

    return (
      <ResponsiveContainer width="100%" height={300}>
        <LineChart data={chartData}>
          <CartesianGrid strokeDasharray="3 3" stroke={chartColors.grid} />
          <XAxis dataKey="time" stroke={chartColors.axis} fontSize={11} />
          <YAxis stroke={chartColors.axis} fontSize={11} unit="%" domain={[0, 100]} />
          <Tooltip contentStyle={{ backgroundColor: chartColors.tooltip.bg, border: `1px solid ${chartColors.tooltip.border}`, borderRadius: '8px', fontSize: '12px' }} formatter={(value) => typeof value === 'number' ? `${value.toFixed(1)}%` : value} />
          <Legend />
          <Line type="monotone" dataKey="Validation" stroke="#3b82f6" strokeWidth={2} dot={false} />
          <Line type="monotone" dataKey="Backtesting" stroke="#10b981" strokeWidth={2} dot={false} />
        </LineChart>
      </ResponsiveContainer>
    );
  }

  return null;
}

function QualityDistributionChart({ data, theme }: { data: QualityDistributionResponse; theme: string }) {
  const chartColors = {
    grid: theme === 'dark' ? '#334155' : '#e2e8f0',
    axis: theme === 'dark' ? '#64748b' : '#94a3b8',
    tooltip: { bg: theme === 'dark' ? '#1e293b' : '#ffffff', border: theme === 'dark' ? '#334155' : '#e2e8f0' },
  };

  const chartData = data.distributions.map(dist => {
    const bucketData: any = { stage: dist.stage };
    dist.buckets.forEach(bucket => { bucketData[bucket.range] = bucket.count; });
    return bucketData;
  });

  return (
    <ResponsiveContainer width="100%" height={250}>
      <BarChart data={chartData}>
        <CartesianGrid strokeDasharray="3 3" stroke={chartColors.grid} />
        <XAxis dataKey="stage" stroke={chartColors.axis} fontSize={11} />
        <YAxis stroke={chartColors.axis} fontSize={11} />
        <Tooltip contentStyle={{ backgroundColor: chartColors.tooltip.bg, border: `1px solid ${chartColors.tooltip.border}`, borderRadius: '8px', fontSize: '12px' }} />
        <Legend />
        <Bar dataKey="0-20" stackId="a" fill="#ef4444" />
        <Bar dataKey="20-40" stackId="a" fill="#f97316" />
        <Bar dataKey="40-60" stackId="a" fill="#eab308" />
        <Bar dataKey="60-80" stackId="a" fill="#84cc16" />
        <Bar dataKey="80-100" stackId="a" fill="#22c55e" />
      </BarChart>
    </ResponsiveContainer>
  );
}

// === Main Page ===

export default function PipelineHealth() {
  const { theme } = useTheme();
  const [period, setPeriod] = useState<MetricsPeriod>('24h');
  const [activeMetric, setActiveMetric] = useState<MetricsType>('throughput');

  const { data: health, isLoading: healthLoading, error: healthError } = usePipelineHealth();
  const { data: quality } = useQualityDistribution();
  const { data: alerts } = useMetricsAlerts();
  const { data: aggregated } = useMetricsAggregated({ period });
  const { data: timeseries } = useMetricsTimeseries({ period, metric: activeMetric });

  if (healthLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Activity className="w-8 h-8 animate-spin text-[var(--color-text-tertiary)]" />
      </div>
    );
  }

  if (healthError) {
    return (
      <div className="card border-[var(--color-loss)]/20 bg-[var(--color-loss-bg)]">
        <div className="text-center py-8">
          <p className="text-[var(--color-loss)] font-medium">Failed to load pipeline health</p>
          <p className="text-sm text-[var(--color-text-tertiary)] mt-2">Check if the backend is running</p>
        </div>
      </div>
    );
  }

  if (!health) return null;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-[var(--color-text-primary)]">Pipeline Health</h1>
        <p className="text-sm text-[var(--color-text-secondary)] mt-1">
          Real-time monitoring of strategy pipeline
        </p>
      </div>

      {/* Alerts */}
      {alerts?.alerts && alerts.alerts.length > 0 && (
        <MetricsAlertBanner alerts={alerts.alerts} />
      )}

      {/* Overall Status */}
      <div className="flex flex-wrap items-center gap-3">
        <span className="text-sm text-[var(--color-text-tertiary)]">Status:</span>
        <span className={`badge ${
          health.overall_status === 'healthy' ? 'badge-profit' :
          health.overall_status === 'degraded' ? 'badge-warning' : 'badge-loss'
        }`}>
          {health.overall_status}
        </span>
        {health.bottleneck && (
          <span className="text-sm text-[var(--color-warning)]">
            Bottleneck: <span className="font-medium capitalize">{health.bottleneck}</span>
          </span>
        )}
      </div>

      {/* Period Selector + KPIs */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <PeriodSelector value={period} onChange={setPeriod} />
        {aggregated && (
          <span className="text-xs text-[var(--color-text-tertiary)]">
            {aggregated.snapshots_analyzed} snapshots
          </span>
        )}
      </div>

      {aggregated && <AggregatedKPICards data={aggregated} />}

      {/* Critical Issues */}
      {health.critical_issues.length > 0 && (
        <div className="card border-[var(--color-loss)] bg-[var(--color-loss-bg)]">
          <div className="flex items-start gap-3">
            <AlertTriangle className="w-5 h-5 text-[var(--color-loss)] flex-shrink-0 mt-0.5" />
            <div>
              <h3 className="text-sm font-semibold text-[var(--color-loss)] mb-2">
                Critical Issues ({health.critical_issues.length})
              </h3>
              <ul className="space-y-1">
                {health.critical_issues.map((issue, i) => (
                  <li key={i} className="text-sm text-[var(--color-loss)]">{issue}</li>
                ))}
              </ul>
            </div>
          </div>
        </div>
      )}

      {/* Pipeline Flow */}
      <div className="card">
        <h2 className="text-lg font-semibold text-[var(--color-text-primary)] mb-4">Pipeline Flow</h2>
        <PipelineFlowDiagram stages={health.stages} />
      </div>

      {/* Stage Details */}
      <div>
        <h2 className="text-lg font-semibold text-[var(--color-text-primary)] mb-4">Stage Details</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {health.stages.map(stage => (
            <StageDetailCard key={stage.stage} stage={stage} />
          ))}
        </div>
      </div>

      {/* Historical Metrics */}
      <div className="card">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 mb-4">
          <h2 className="text-lg font-semibold text-[var(--color-text-primary)]">Historical Metrics</h2>
          <MetricTypeSelector value={activeMetric} onChange={setActiveMetric} />
        </div>
        {timeseries && timeseries.data.length > 0 ? (
          <TimeseriesChart data={timeseries.data} type={activeMetric} theme={theme} />
        ) : (
          <div className="h-64 flex items-center justify-center text-[var(--color-text-tertiary)]">
            No historical data available
          </div>
        )}
      </div>

      {/* Quality Distribution */}
      {quality && quality.distributions.some(d => d.buckets.length > 0) && (
        <div className="card">
          <h2 className="text-lg font-semibold text-[var(--color-text-primary)] mb-4">Quality Distribution</h2>
          <QualityDistributionChart data={quality} theme={theme} />
        </div>
      )}
    </div>
  );
}
