import { useState } from 'react';
import {
  usePipelineHealth,
  usePipelineStats,
  useQualityDistribution,
  useMetricsAlerts,
  useMetricsAggregated,
  useMetricsTimeseries,
  useMetricsCurrent
} from '../hooks/useApi';
import type {
  PipelineStageHealth,
  PipelineStatsResponse,
  QualityDistributionResponse,
  MetricAlert,
  MetricsAggregatedResponse,
  MetricsCurrentResponse,
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
  XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, Legend, ReferenceLine
} from 'recharts';

// === Utility Functions ===

function getStatusColor(status: string): string {
  const colors = {
    'healthy': 'bg-profit',
    'backpressure': 'bg-warning',
    'stalled': 'bg-loss',
    'error': 'bg-loss',
    'degraded': 'bg-warning',
    'critical': 'bg-loss',
  };
  return colors[status as keyof typeof colors] || 'bg-muted';
}

function getStatusTextColor(status: string): string {
  const colors = {
    'healthy': 'text-profit',
    'backpressure': 'text-warning',
    'stalled': 'text-loss',
    'error': 'text-loss',
    'degraded': 'text-warning',
    'critical': 'text-loss',
  };
  return colors[status as keyof typeof colors] || 'text-muted';
}

function getSeverityColor(severity: string): { bg: string; text: string; border: string } {
  switch (severity) {
    case 'critical':
      return { bg: 'bg-loss/10', text: 'text-loss', border: 'border-loss' };
    case 'warning':
      return { bg: 'bg-warning/10', text: 'text-warning', border: 'border-warning' };
    default:
      return { bg: 'bg-muted/10', text: 'text-muted', border: 'border-muted' };
  }
}

function formatTimestamp(ts: string): string {
  return new Date(ts).toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' });
}

// === NEW: Metrics Alert Banner ===

function MetricsAlertBanner({ alerts }: { alerts: MetricAlert[] }) {
  if (alerts.length === 0) return null;

  // Sort by severity: critical first, then warning, then info
  const sortedAlerts = [...alerts].sort((a, b) => {
    const order = { critical: 0, warning: 1, info: 2 };
    return order[a.severity] - order[b.severity];
  });

  return (
    <div className="space-y-2">
      {sortedAlerts.slice(0, 3).map((alert, i) => {
        const colors = getSeverityColor(alert.severity);
        return (
          <div
            key={i}
            className={`${colors.bg} border ${colors.border} rounded-lg p-3 flex items-center gap-3`}
          >
            <Bell className={`w-4 h-4 ${colors.text} flex-shrink-0`} />
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2">
                <span className={`text-xs font-semibold uppercase ${colors.text}`}>
                  {alert.severity}
                </span>
                <span className="text-xs text-muted">
                  {alert.type.replace('_', ' ')}
                </span>
              </div>
              <p className={`text-sm ${colors.text} truncate`}>{alert.message}</p>
            </div>
            <div className="text-right flex-shrink-0">
              {alert.current_value !== undefined && (
                <div className="text-sm font-mono">{alert.current_value.toFixed(2)}</div>
              )}
              <div className="text-xs text-muted flex items-center gap-1">
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

// === NEW: Period Selector ===

function PeriodSelector({
  value,
  onChange
}: {
  value: MetricsPeriod;
  onChange: (period: MetricsPeriod) => void;
}) {
  const periods: MetricsPeriod[] = ['1h', '6h', '24h', '7d', '30d'];

  return (
    <div className="flex gap-1 bg-background rounded-lg p-1">
      {periods.map(period => (
        <button
          key={period}
          onClick={() => onChange(period)}
          className={`px-3 py-1 text-sm rounded transition-colors ${
            value === period
              ? 'bg-profit/10 text-profit font-semibold'
              : 'text-muted hover:text-foreground'
          }`}
        >
          {period}
        </button>
      ))}
    </div>
  );
}

// === NEW: Metric Type Selector ===

function MetricTypeSelector({
  value,
  onChange
}: {
  value: MetricsType;
  onChange: (metric: MetricsType) => void;
}) {
  const metrics: { key: MetricsType; label: string; icon: React.ReactNode }[] = [
    { key: 'queue_depths', label: 'Queue Depths', icon: <BarChart3 className="w-4 h-4" /> },
    { key: 'throughput', label: 'Throughput', icon: <TrendingUp className="w-4 h-4" /> },
    { key: 'quality', label: 'Quality', icon: <Zap className="w-4 h-4" /> },
    { key: 'utilization', label: 'Utilization', icon: <Gauge className="w-4 h-4" /> },
    { key: 'success_rates', label: 'Success Rates', icon: <CheckCircle className="w-4 h-4" /> },
  ];

  return (
    <div className="flex gap-2">
      {metrics.map(m => (
        <button
          key={m.key}
          onClick={() => onChange(m.key)}
          className={`flex items-center gap-2 px-3 py-1.5 text-sm rounded-lg transition-colors ${
            value === m.key
              ? 'bg-profit/10 text-profit border border-profit/30'
              : 'bg-background text-muted hover:text-foreground border border-border'
          }`}
        >
          {m.icon}
          {m.label}
        </button>
      ))}
    </div>
  );
}

// === NEW: Aggregated KPI Cards ===

function AggregatedKPICards({ data }: { data: MetricsAggregatedResponse }) {
  const kpis = [
    {
      label: 'Avg Queue Depth',
      value: Math.round(data.queue_depths.avg_generated + data.queue_depths.avg_validated + data.queue_depths.avg_active),
      detail: `G:${data.queue_depths.avg_generated.toFixed(0)} V:${data.queue_depths.avg_validated.toFixed(0)} A:${data.queue_depths.avg_active.toFixed(0)}`,
    },
    {
      label: 'Max Utilization',
      value: `${(Math.max(data.utilization.max_generated, data.utilization.max_validated, data.utilization.max_active) * 100).toFixed(0)}%`,
      detail: `G:${(data.utilization.max_generated * 100).toFixed(0)}% V:${(data.utilization.max_validated * 100).toFixed(0)}% A:${(data.utilization.max_active * 100).toFixed(0)}%`,
      warning: Math.max(data.utilization.max_generated, data.utilization.max_validated, data.utilization.max_active) > 0.9,
    },
    {
      label: 'Avg Sharpe',
      value: data.quality.avg_sharpe?.toFixed(2) ?? '-',
      detail: data.quality.avg_sharpe && data.quality.avg_sharpe >= 1.0 ? 'Good' : data.quality.avg_sharpe && data.quality.avg_sharpe >= 0.5 ? 'Fair' : 'Low',
      profit: data.quality.avg_sharpe && data.quality.avg_sharpe >= 1.0,
    },
    {
      label: 'Avg Win Rate',
      value: data.quality.avg_win_rate ? `${(data.quality.avg_win_rate * 100).toFixed(1)}%` : '-',
      detail: data.quality.avg_win_rate && data.quality.avg_win_rate >= 0.55 ? 'Edge' : data.quality.avg_win_rate && data.quality.avg_win_rate >= 0.5 ? 'Breakeven' : 'Below 50%',
      profit: data.quality.avg_win_rate && data.quality.avg_win_rate >= 0.55,
    },
  ];

  return (
    <div className="grid grid-cols-4 gap-4">
      {kpis.map((kpi, i) => (
        <div key={i} className="bg-card border border-border rounded-lg p-4">
          <div className="text-xs text-muted mb-1">{kpi.label}</div>
          <div className={`text-2xl font-bold font-mono ${
            kpi.warning ? 'text-warning' : kpi.profit ? 'text-profit' : ''
          }`}>
            {kpi.value}
          </div>
          <div className="text-xs text-muted mt-1">{kpi.detail}</div>
        </div>
      ))}
    </div>
  );
}

// === NEW: Queue Depths Chart ===

function QueueDepthsChart({ data }: { data: QueueDepthsDataPoint[] }) {
  const chartData = data.map(d => ({
    timestamp: formatTimestamp(d.timestamp),
    Generated: d.generated,
    Validated: d.validated,
    Active: d.active,
    Live: d.live,
  }));

  return (
    <ResponsiveContainer width="100%" height={300}>
      <LineChart data={chartData}>
        <CartesianGrid strokeDasharray="3 3" stroke="#1f1f1f" />
        <XAxis dataKey="timestamp" stroke="#888" fontSize={12} />
        <YAxis stroke="#888" fontSize={12} />
        <Tooltip
          contentStyle={{ backgroundColor: '#111', border: '1px solid #1f1f1f', borderRadius: '4px' }}
          labelStyle={{ color: '#888' }}
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

// === NEW: Throughput Metrics Chart ===

function ThroughputMetricsChart({ data }: { data: ThroughputDataPoint[] }) {
  const chartData = data.map(d => ({
    timestamp: formatTimestamp(d.timestamp),
    Generation: d.generation ?? 0,
    Validation: d.validation ?? 0,
    Backtesting: d.backtesting ?? 0,
  }));

  return (
    <ResponsiveContainer width="100%" height={300}>
      <LineChart data={chartData}>
        <CartesianGrid strokeDasharray="3 3" stroke="#1f1f1f" />
        <XAxis dataKey="timestamp" stroke="#888" fontSize={12} />
        <YAxis stroke="#888" fontSize={12} label={{ value: 'Strategies/Hour', angle: -90, position: 'insideLeft', style: { fill: '#888', fontSize: 12 } }} />
        <Tooltip
          contentStyle={{ backgroundColor: '#111', border: '1px solid #1f1f1f', borderRadius: '4px' }}
          labelStyle={{ color: '#888' }}
        />
        <Legend />
        <Line type="monotone" dataKey="Generation" stroke="#6b7280" strokeWidth={2} dot={false} />
        <Line type="monotone" dataKey="Validation" stroke="#3b82f6" strokeWidth={2} dot={false} />
        <Line type="monotone" dataKey="Backtesting" stroke="#10b981" strokeWidth={2} dot={false} />
        <ReferenceLine y={5} stroke="#f59e0b" strokeDasharray="5 5" label={{ value: 'Min Threshold', fill: '#f59e0b', fontSize: 10 }} />
      </LineChart>
    </ResponsiveContainer>
  );
}

// === NEW: Quality Trend Chart ===

function QualityTrendChart({ data }: { data: QualityDataPoint[] }) {
  const chartData = data.map(d => ({
    timestamp: formatTimestamp(d.timestamp),
    Sharpe: d.avg_sharpe ?? 0,
    'Win Rate': d.avg_win_rate ? d.avg_win_rate * 100 : 0,
    Expectancy: d.avg_expectancy ? d.avg_expectancy * 100 : 0,
  }));

  return (
    <ResponsiveContainer width="100%" height={300}>
      <LineChart data={chartData}>
        <CartesianGrid strokeDasharray="3 3" stroke="#1f1f1f" />
        <XAxis dataKey="timestamp" stroke="#888" fontSize={12} />
        <YAxis yAxisId="left" stroke="#888" fontSize={12} />
        <YAxis yAxisId="right" orientation="right" stroke="#888" fontSize={12} unit="%" />
        <Tooltip
          contentStyle={{ backgroundColor: '#111', border: '1px solid #1f1f1f', borderRadius: '4px' }}
          labelStyle={{ color: '#888' }}
        />
        <Legend />
        <Line yAxisId="left" type="monotone" dataKey="Sharpe" stroke="#10b981" strokeWidth={2} dot={false} />
        <Line yAxisId="right" type="monotone" dataKey="Win Rate" stroke="#3b82f6" strokeWidth={2} dot={false} />
        <Line yAxisId="right" type="monotone" dataKey="Expectancy" stroke="#a855f7" strokeWidth={2} dot={false} />
        <ReferenceLine yAxisId="left" y={0.3} stroke="#ef4444" strokeDasharray="5 5" label={{ value: 'Alert Threshold', fill: '#ef4444', fontSize: 10 }} />
        <ReferenceLine yAxisId="left" y={1.0} stroke="#10b981" strokeDasharray="5 5" label={{ value: 'Good', fill: '#10b981', fontSize: 10 }} />
      </LineChart>
    </ResponsiveContainer>
  );
}

// === NEW: Utilization Chart ===

function UtilizationChart({ data }: { data: UtilizationDataPoint[] }) {
  const chartData = data.map(d => ({
    timestamp: formatTimestamp(d.timestamp),
    Generated: (d.generated ?? 0) * 100,
    Validated: (d.validated ?? 0) * 100,
    Active: (d.active ?? 0) * 100,
  }));

  return (
    <ResponsiveContainer width="100%" height={300}>
      <AreaChart data={chartData}>
        <CartesianGrid strokeDasharray="3 3" stroke="#1f1f1f" />
        <XAxis dataKey="timestamp" stroke="#888" fontSize={12} />
        <YAxis stroke="#888" fontSize={12} unit="%" domain={[0, 100]} />
        <Tooltip
          contentStyle={{ backgroundColor: '#111', border: '1px solid #1f1f1f', borderRadius: '4px' }}
          labelStyle={{ color: '#888' }}
          formatter={(value) => typeof value === 'number' ? `${value.toFixed(1)}%` : value}
        />
        <Legend />
        <ReferenceLine y={90} stroke="#ef4444" strokeDasharray="5 5" label={{ value: 'Critical', fill: '#ef4444', fontSize: 10 }} />
        <ReferenceLine y={80} stroke="#f59e0b" strokeDasharray="5 5" label={{ value: 'Warning', fill: '#f59e0b', fontSize: 10 }} />
        <Area type="monotone" dataKey="Generated" stackId="1" stroke="#6b7280" fill="#6b7280" fillOpacity={0.3} />
        <Area type="monotone" dataKey="Validated" stackId="2" stroke="#3b82f6" fill="#3b82f6" fillOpacity={0.3} />
        <Area type="monotone" dataKey="Active" stackId="3" stroke="#a855f7" fill="#a855f7" fillOpacity={0.3} />
      </AreaChart>
    </ResponsiveContainer>
  );
}

// === NEW: Success Rates Chart ===

function SuccessRatesChart({ data }: { data: SuccessRatesDataPoint[] }) {
  const chartData = data.map(d => ({
    timestamp: formatTimestamp(d.timestamp),
    Validation: d.validation ? d.validation * 100 : 0,
    Backtesting: d.backtesting ? d.backtesting * 100 : 0,
  }));

  return (
    <ResponsiveContainer width="100%" height={300}>
      <LineChart data={chartData}>
        <CartesianGrid strokeDasharray="3 3" stroke="#1f1f1f" />
        <XAxis dataKey="timestamp" stroke="#888" fontSize={12} />
        <YAxis stroke="#888" fontSize={12} unit="%" domain={[0, 100]} />
        <Tooltip
          contentStyle={{ backgroundColor: '#111', border: '1px solid #1f1f1f', borderRadius: '4px' }}
          labelStyle={{ color: '#888' }}
          formatter={(value) => typeof value === 'number' ? `${value.toFixed(1)}%` : value}
        />
        <Legend />
        <Line type="monotone" dataKey="Validation" stroke="#3b82f6" strokeWidth={2} dot={false} />
        <Line type="monotone" dataKey="Backtesting" stroke="#10b981" strokeWidth={2} dot={false} />
        <ReferenceLine y={50} stroke="#f59e0b" strokeDasharray="5 5" label={{ value: '50%', fill: '#f59e0b', fontSize: 10 }} />
      </LineChart>
    </ResponsiveContainer>
  );
}

// === NEW: Current Metrics Snapshot ===

function CurrentMetricsSnapshot({ data }: { data: MetricsCurrentResponse }) {
  return (
    <div className="bg-card border border-border rounded-lg p-4">
      <div className="flex items-center justify-between mb-4">
        <h3 className="font-semibold">Current Snapshot</h3>
        <div className="flex items-center gap-2">
          <span className={`px-2 py-0.5 rounded text-xs font-semibold uppercase ${getStatusTextColor(data.overall_status)} ${getStatusColor(data.overall_status)}/20`}>
            {data.overall_status}
          </span>
          {data.bottleneck_stage && (
            <span className="text-xs text-warning">
              Bottleneck: {data.bottleneck_stage}
            </span>
          )}
        </div>
      </div>

      <div className="grid grid-cols-4 gap-4 text-sm">
        {/* Queue Depths */}
        <div>
          <div className="text-xs text-muted mb-2">Queue Depths</div>
          <div className="space-y-1 font-mono text-xs">
            <div className="flex justify-between"><span>Generated:</span><span>{data.queue_depths.generated}</span></div>
            <div className="flex justify-between"><span>Validated:</span><span>{data.queue_depths.validated}</span></div>
            <div className="flex justify-between"><span>Active:</span><span>{data.queue_depths.active}</span></div>
            <div className="flex justify-between text-profit"><span>Live:</span><span>{data.queue_depths.live}</span></div>
          </div>
        </div>

        {/* Throughput */}
        <div>
          <div className="text-xs text-muted mb-2">Throughput (strat/h)</div>
          <div className="space-y-1 font-mono text-xs">
            <div className="flex justify-between"><span>Generation:</span><span>{data.throughput.generation?.toFixed(1) ?? '-'}</span></div>
            <div className="flex justify-between"><span>Validation:</span><span>{data.throughput.validation?.toFixed(1) ?? '-'}</span></div>
            <div className="flex justify-between"><span>Backtesting:</span><span>{data.throughput.backtesting?.toFixed(1) ?? '-'}</span></div>
          </div>
        </div>

        {/* Quality */}
        <div>
          <div className="text-xs text-muted mb-2">Quality Metrics</div>
          <div className="space-y-1 font-mono text-xs">
            <div className="flex justify-between"><span>Avg Sharpe:</span><span className={data.quality.avg_sharpe && data.quality.avg_sharpe >= 1 ? 'text-profit' : ''}>{data.quality.avg_sharpe?.toFixed(2) ?? '-'}</span></div>
            <div className="flex justify-between"><span>Avg Win Rate:</span><span className={data.quality.avg_win_rate && data.quality.avg_win_rate >= 0.55 ? 'text-profit' : ''}>{data.quality.avg_win_rate ? `${(data.quality.avg_win_rate * 100).toFixed(1)}%` : '-'}</span></div>
            <div className="flex justify-between"><span>Avg Expectancy:</span><span>{data.quality.avg_expectancy ? `${(data.quality.avg_expectancy * 100).toFixed(2)}%` : '-'}</span></div>
          </div>
        </div>

        {/* Success Rates */}
        <div>
          <div className="text-xs text-muted mb-2">Success Rates</div>
          <div className="space-y-1 font-mono text-xs">
            <div className="flex justify-between">
              <span>Validation:</span>
              <span className={data.success_rates?.validation && data.success_rates.validation >= 0.5 ? 'text-profit' : ''}>
                {data.success_rates?.validation != null ? `${(data.success_rates.validation * 100).toFixed(1)}%` : '-'}
              </span>
            </div>
            <div className="flex justify-between">
              <span>Backtesting:</span>
              <span className={data.success_rates?.backtesting && data.success_rates.backtesting >= 0.5 ? 'text-profit' : ''}>
                {data.success_rates?.backtesting != null ? `${(data.success_rates.backtesting * 100).toFixed(1)}%` : '-'}
              </span>
            </div>
          </div>
        </div>
      </div>

      <div className="mt-3 pt-3 border-t border-border text-xs text-muted">
        Last update: {new Date(data.timestamp).toLocaleString()}
      </div>
    </div>
  );
}

// === Existing Components ===

function CriticalIssuesAlert({ issues }: { issues: string[] }) {
  if (issues.length === 0) return null;

  return (
    <div className="bg-loss/10 border border-loss rounded-lg p-4">
      <div className="flex items-start gap-3">
        <AlertTriangle className="w-5 h-5 text-loss flex-shrink-0 mt-0.5" />
        <div>
          <h3 className="text-sm font-semibold text-loss mb-2">
            Critical Issues ({issues.length})
          </h3>
          <ul className="space-y-1">
            {issues.map((issue, i) => (
              <li key={i} className="text-sm text-loss">
                {issue}
              </li>
            ))}
          </ul>
        </div>
      </div>
    </div>
  );
}

function PipelineFlowDiagram({ stages }: { stages: PipelineStageHealth[] }) {
  return (
    <div className="flex items-center justify-between gap-4">
      {stages.map((stage, i) => (
        <div key={stage.stage} className="flex items-center gap-4 flex-1">
          <div className="flex-1 bg-background border border-border rounded-lg p-4">
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm font-semibold capitalize">{stage.stage}</span>
              <div className={`w-3 h-3 rounded-full ${getStatusColor(stage.status)}`} />
            </div>
            <div className="text-xs text-muted">
              <div>Queue: {stage.queue_depth} / {stage.queue_limit}</div>
              <div>Rate: {stage.processing_rate.toFixed(1)}/h</div>
            </div>
          </div>
          {i < stages.length - 1 && (
            <ArrowRight className="w-5 h-5 text-muted flex-shrink-0" />
          )}
        </div>
      ))}
    </div>
  );
}

function StageDetailCard({ stage }: { stage: PipelineStageHealth }) {
  const statusColor = getStatusColor(stage.status);
  const statusTextColor = getStatusTextColor(stage.status);

  return (
    <div className="bg-card border border-border rounded-lg p-4">
      <div className="flex items-center justify-between mb-3">
        <h3 className="font-semibold capitalize">{stage.stage}</h3>
        <span className={`text-sm uppercase ${statusTextColor}`}>{stage.status}</span>
      </div>
      <div className="mb-4">
        <div className="flex justify-between text-xs mb-1">
          <span className="text-muted">Queue Utilization</span>
          <span>{stage.queue_depth} / {stage.queue_limit}</span>
        </div>
        <div className="h-2 bg-background rounded-full overflow-hidden">
          <div
            className={`h-full ${statusColor}`}
            style={{ width: `${Math.min(stage.utilization_pct, 100)}%` }}
          />
        </div>
        <div className="text-xs text-muted mt-1 text-right">
          {stage.utilization_pct.toFixed(1)}%
        </div>
      </div>
      <div className="grid grid-cols-2 gap-3 text-sm">
        <div>
          <div className="text-xs text-muted">Rate</div>
          <div className="font-mono">{stage.processing_rate.toFixed(1)}/h</div>
        </div>
        <div>
          <div className="text-xs text-muted">Success</div>
          <div className="font-mono">{stage.success_rate.toFixed(1)}%</div>
        </div>
        <div>
          <div className="text-xs text-muted">Last Hour</div>
          <div className="font-mono">{stage.processed_last_hour}</div>
        </div>
        <div>
          <div className="text-xs text-muted">Workers</div>
          <div className="font-mono">{stage.active_workers}/{stage.max_workers}</div>
        </div>
      </div>
    </div>
  );
}

function ThroughputChart({ data }: { data: PipelineStatsResponse }) {
  const chartData = data.data_points.reduce((acc, point) => {
    const existing = acc.find(d => d.timestamp === point.timestamp);
    if (existing) {
      existing[point.stage] = point.throughput;
    } else {
      acc.push({
        timestamp: new Date(point.timestamp).toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' }),
        [point.stage]: point.throughput
      });
    }
    return acc;
  }, [] as any[]);

  return (
    <ResponsiveContainer width="100%" height={300}>
      <LineChart data={chartData}>
        <CartesianGrid strokeDasharray="3 3" stroke="#1f1f1f" />
        <XAxis dataKey="timestamp" stroke="#888" fontSize={12} />
        <YAxis stroke="#888" fontSize={12} label={{ value: 'Strategies/Hour', angle: -90, position: 'insideLeft', style: { fill: '#888', fontSize: 12 } }} />
        <Tooltip
          contentStyle={{ backgroundColor: '#111', border: '1px solid #1f1f1f', borderRadius: '4px' }}
          labelStyle={{ color: '#888' }}
        />
        <Legend />
        <Line type="monotone" dataKey="generation" stroke="#6b7280" strokeWidth={2} dot={false} />
        <Line type="monotone" dataKey="validation" stroke="#3b82f6" strokeWidth={2} dot={false} />
        <Line type="monotone" dataKey="backtesting" stroke="#a855f7" strokeWidth={2} dot={false} />
        <Line type="monotone" dataKey="classification" stroke="#10b981" strokeWidth={2} dot={false} />
      </LineChart>
    </ResponsiveContainer>
  );
}

function QualityDistributionChart({ data }: { data: QualityDistributionResponse }) {
  const chartData = data.distributions.map(dist => {
    const bucketData: any = { stage: dist.stage };
    dist.buckets.forEach(bucket => {
      bucketData[bucket.range] = bucket.count;
    });
    return bucketData;
  });

  return (
    <ResponsiveContainer width="100%" height={250}>
      <BarChart data={chartData}>
        <CartesianGrid strokeDasharray="3 3" stroke="#1f1f1f" />
        <XAxis dataKey="stage" stroke="#888" fontSize={12} />
        <YAxis stroke="#888" fontSize={12} />
        <Tooltip
          contentStyle={{ backgroundColor: '#111', border: '1px solid #1f1f1f', borderRadius: '4px' }}
          labelStyle={{ color: '#888' }}
        />
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
  // State for selectors
  const [period, setPeriod] = useState<MetricsPeriod>('24h');
  const [activeMetric, setActiveMetric] = useState<MetricsType>('throughput');

  // Existing hooks
  const { data: health, isLoading: healthLoading, error: healthError } = usePipelineHealth();
  const { data: stats } = usePipelineStats({ period: '24h' });
  const { data: quality } = useQualityDistribution();

  // New hooks
  const { data: alerts } = useMetricsAlerts();
  const { data: aggregated } = useMetricsAggregated({ period });
  const { data: timeseries } = useMetricsTimeseries({ period, metric: activeMetric });
  const { data: current } = useMetricsCurrent();

  if (healthLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Activity className="w-8 h-8 animate-spin text-muted" />
      </div>
    );
  }

  if (healthError) {
    return (
      <div className="bg-loss/10 border border-loss/20 rounded-lg p-6 text-center">
        <p className="text-loss">Failed to load pipeline health</p>
        <p className="text-xs text-muted mt-2">Check if the backend is running</p>
      </div>
    );
  }

  if (!health) return null;

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div>
        <h1 className="text-2xl font-bold">Pipeline Health</h1>
        <p className="text-sm text-muted mt-1">
          Real-time monitoring of Generation - Validation - Backtest - Classification
        </p>
      </div>

      {/* NEW: Metrics Alert Banner */}
      {alerts?.alerts && alerts.alerts.length > 0 && (
        <MetricsAlertBanner alerts={alerts.alerts} />
      )}

      {/* Overall Status Badge */}
      <div className="flex items-center gap-3">
        <span className="text-sm text-muted">Overall Status:</span>
        <span className={`px-3 py-1 rounded text-sm font-semibold uppercase ${getStatusTextColor(health.overall_status)}`}>
          {health.overall_status}
        </span>
        {health.bottleneck && (
          <>
            <span className="text-muted">-</span>
            <span className="text-sm text-warning">
              Bottleneck: <span className="font-semibold capitalize">{health.bottleneck}</span>
            </span>
          </>
        )}
      </div>

      {/* NEW: Period Selector + Aggregated Stats */}
      <div className="flex items-center justify-between">
        <PeriodSelector value={period} onChange={setPeriod} />
        {aggregated && (
          <div className="text-xs text-muted">
            {aggregated.snapshots_analyzed} snapshots analyzed
          </div>
        )}
      </div>

      {/* NEW: Aggregated KPI Cards */}
      {aggregated && <AggregatedKPICards data={aggregated} />}

      {/* Critical Issues */}
      <CriticalIssuesAlert issues={health.critical_issues} />

      {/* Pipeline Flow Visualization */}
      <div className="bg-card border border-border rounded-lg p-6">
        <h2 className="text-lg font-semibold mb-4">Pipeline Flow</h2>
        <PipelineFlowDiagram stages={health.stages} />
      </div>

      {/* Stage Details Grid */}
      <div>
        <h2 className="text-lg font-semibold mb-4">Stage Details</h2>
        <div className="grid grid-cols-2 gap-4">
          {health.stages.map(stage => (
            <StageDetailCard key={stage.stage} stage={stage} />
          ))}
        </div>
      </div>

      {/* NEW: Historical Metrics Section */}
      <div className="bg-card border border-border rounded-lg p-6">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold">Historical Metrics</h2>
          <MetricTypeSelector value={activeMetric} onChange={setActiveMetric} />
        </div>

        {timeseries && timeseries.data.length > 0 ? (
          <>
            {activeMetric === 'queue_depths' && (
              <QueueDepthsChart data={timeseries.data as QueueDepthsDataPoint[]} />
            )}
            {activeMetric === 'throughput' && (
              <ThroughputMetricsChart data={timeseries.data as ThroughputDataPoint[]} />
            )}
            {activeMetric === 'quality' && (
              <QualityTrendChart data={timeseries.data as QualityDataPoint[]} />
            )}
            {activeMetric === 'utilization' && (
              <UtilizationChart data={timeseries.data as UtilizationDataPoint[]} />
            )}
            {activeMetric === 'success_rates' && (
              <SuccessRatesChart data={timeseries.data as SuccessRatesDataPoint[]} />
            )}
          </>
        ) : (
          <div className="h-64 flex items-center justify-center text-muted">
            No historical data available for this period
          </div>
        )}
      </div>

      {/* Throughput Trend Chart (existing) */}
      {stats && (
        <div className="bg-card border border-border rounded-lg p-6">
          <h2 className="text-lg font-semibold mb-4">Pipeline Throughput Trend</h2>
          <ThroughputChart data={stats} />
        </div>
      )}

      {/* Quality Distribution */}
      {quality && quality.distributions.length > 0 && (
        <div className="bg-card border border-border rounded-lg p-6">
          <h2 className="text-lg font-semibold mb-4">Strategy Quality Distribution</h2>
          <QualityDistributionChart data={quality} />
        </div>
      )}

      {/* NEW: Current Metrics Snapshot */}
      {current && <CurrentMetricsSnapshot data={current} />}
    </div>
  );
}
