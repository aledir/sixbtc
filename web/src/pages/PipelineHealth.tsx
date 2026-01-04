import { usePipelineHealth, usePipelineStats, useQualityDistribution } from '../hooks/useApi';
import type { PipelineStageHealth, PipelineStatsResponse, QualityDistributionResponse } from '../types';
import { Activity, AlertTriangle, ArrowRight } from 'lucide-react';
import { BarChart, Bar, LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid, Legend } from 'recharts';

// === Utility Functions ===

function getStatusColor(status: string): string {
  const colors = {
    'healthy': 'bg-profit',
    'backpressure': 'bg-warning',
    'stalled': 'bg-loss',
    'error': 'bg-loss',
  };
  return colors[status as keyof typeof colors] || 'bg-muted';
}

function getStatusTextColor(status: string): string {
  const colors = {
    'healthy': 'text-profit',
    'backpressure': 'text-warning',
    'stalled': 'text-loss',
    'error': 'text-loss',
  };
  return colors[status as keyof typeof colors] || 'text-muted';
}

// === Components ===

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
                • {issue}
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
          {/* Stage Node */}
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

          {/* Arrow */}
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
      {/* Header */}
      <div className="flex items-center justify-between mb-3">
        <h3 className="font-semibold capitalize">{stage.stage}</h3>
        <span className={`text-sm uppercase ${statusTextColor}`}>{stage.status}</span>
      </div>

      {/* Queue Utilization Bar */}
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

      {/* Metrics Grid */}
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
  // Transform data for Recharts
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
  // Transform data for stacked bar chart
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
  const { data: health, isLoading: healthLoading, error: healthError } = usePipelineHealth();
  const { data: stats } = usePipelineStats({ period: '24h' });
  const { data: quality } = useQualityDistribution();

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
          Real-time monitoring of Generation → Validation → Backtest → Classification
        </p>
      </div>

      {/* Overall Status Badge */}
      <div className="flex items-center gap-3">
        <span className="text-sm text-muted">Overall Status:</span>
        <span className={`px-3 py-1 rounded text-sm font-semibold uppercase ${getStatusTextColor(health.overall_status)}`}>
          {health.overall_status}
        </span>
        {health.bottleneck && (
          <>
            <span className="text-muted">•</span>
            <span className="text-sm text-warning">
              Bottleneck: <span className="font-semibold capitalize">{health.bottleneck}</span>
            </span>
          </>
        )}
      </div>

      {/* Critical Alerts */}
      <CriticalIssuesAlert issues={health.critical_issues} />

      {/* Pipeline Flow Visualization */}
      <div className="bg-card border border-border rounded-lg p-6">
        <h2 className="text-lg font-semibold mb-4">Pipeline Flow</h2>
        <PipelineFlowDiagram stages={health.stages} />
      </div>

      {/* Stage Details Grid (2x2) */}
      <div>
        <h2 className="text-lg font-semibold mb-4">Stage Details</h2>
        <div className="grid grid-cols-2 gap-4">
          {health.stages.map(stage => (
            <StageDetailCard key={stage.stage} stage={stage} />
          ))}
        </div>
      </div>

      {/* Throughput Trend Chart */}
      {stats && (
        <div className="bg-card border border-border rounded-lg p-6">
          <h2 className="text-lg font-semibold mb-4">Throughput Trend</h2>
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
    </div>
  );
}
