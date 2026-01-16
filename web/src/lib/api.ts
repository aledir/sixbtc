// API client for SixBTC Control Center

// Dynamic API base URL - uses same host as frontend but port 8080
export const API_BASE = `${window.location.protocol}//${window.location.hostname}:8080/api`;

async function fetchJson<T>(url: string, options?: RequestInit): Promise<T> {
  const response = await fetch(url, {
    headers: {
      'Content-Type': 'application/json',
    },
    ...options,
  });

  if (!response.ok) {
    const error = await response.text();
    throw new Error(`API Error: ${response.status} - ${error}`);
  }

  return response.json();
}

// Status
export async function getStatus() {
  return fetchJson<import('../types').StatusResponse>(`${API_BASE}/status`);
}

// Strategies
export async function getStrategies(params?: {
  status?: string;
  type?: string;
  timeframe?: string;
  limit?: number;
  offset?: number;
}) {
  const searchParams = new URLSearchParams();
  if (params?.status) searchParams.set('status', params.status);
  if (params?.type) searchParams.set('type', params.type);
  if (params?.timeframe) searchParams.set('timeframe', params.timeframe);
  if (params?.limit) searchParams.set('limit', params.limit.toString());
  if (params?.offset) searchParams.set('offset', params.offset.toString());

  const query = searchParams.toString();
  return fetchJson<import('../types').StrategiesResponse>(
    `${API_BASE}/strategies${query ? `?${query}` : ''}`
  );
}

export async function getStrategy(id: string) {
  return fetchJson<import('../types').StrategyDetail>(`${API_BASE}/strategies/${id}`);
}

export async function getStrategyBacktest(id: string) {
  return fetchJson<{ strategy_name: string; results: unknown[] }>(
    `${API_BASE}/strategies/${id}/backtest`
  );
}

// Trades
export async function getTrades(params?: {
  status?: string;
  strategy_id?: string;
  symbol?: string;
  days?: number;
  limit?: number;
  offset?: number;
}) {
  const searchParams = new URLSearchParams();
  if (params?.status) searchParams.set('status', params.status);
  if (params?.strategy_id) searchParams.set('strategy_id', params.strategy_id);
  if (params?.symbol) searchParams.set('symbol', params.symbol);
  if (params?.days) searchParams.set('days', params.days.toString());
  if (params?.limit) searchParams.set('limit', params.limit.toString());
  if (params?.offset) searchParams.set('offset', params.offset.toString());

  const query = searchParams.toString();
  return fetchJson<import('../types').TradesResponse>(
    `${API_BASE}/trades${query ? `?${query}` : ''}`
  );
}

export async function getTradesSummary(params?: { days?: number; strategy_id?: string }) {
  const searchParams = new URLSearchParams();
  if (params?.days) searchParams.set('days', params.days.toString());
  if (params?.strategy_id) searchParams.set('strategy_id', params.strategy_id);

  const query = searchParams.toString();
  return fetchJson<import('../types').TradesSummary>(
    `${API_BASE}/trades/summary${query ? `?${query}` : ''}`
  );
}

// Subaccounts
export async function getSubaccounts() {
  return fetchJson<import('../types').SubaccountsResponse>(`${API_BASE}/subaccounts`);
}

export async function getSubaccount(id: number) {
  return fetchJson<import('../types').SubaccountInfo>(`${API_BASE}/subaccounts/${id}`);
}

// Services
export async function getServices() {
  return fetchJson<import('../types').ServiceInfo[]>(`${API_BASE}/services`);
}

export async function controlService(name: string, action: 'start' | 'stop' | 'restart') {
  return fetchJson<import('../types').ServiceControlResponse>(
    `${API_BASE}/services/${name}/${action}`,
    { method: 'POST' }
  );
}

// Logs
export async function getLogs(service: string, params?: {
  lines?: number;
  level?: string;
  search?: string;
}) {
  const searchParams = new URLSearchParams();
  if (params?.lines) searchParams.set('lines', params.lines.toString());
  if (params?.level) searchParams.set('level', params.level);
  if (params?.search) searchParams.set('search', params.search);

  const query = searchParams.toString();
  return fetchJson<import('../types').LogsResponse>(
    `${API_BASE}/logs/${service}${query ? `?${query}` : ''}`
  );
}

// Config
export async function getConfig() {
  return fetchJson<{ config: Record<string, unknown> }>(`${API_BASE}/config`);
}

export async function getThresholds() {
  return fetchJson<Record<string, Record<string, unknown>>>(`${API_BASE}/config/thresholds`);
}

// Pipeline Health
export async function getPipelineHealth() {
  return fetchJson<import('../types').PipelineHealthResponse>(
    `${API_BASE}/pipeline/health`
  );
}

export async function getPipelineStats(params: { period: string }) {
  return fetchJson<import('../types').PipelineStatsResponse>(
    `${API_BASE}/pipeline/stats?period=${params.period}`
  );
}

export async function getQualityDistribution() {
  return fetchJson<import('../types').QualityDistributionResponse>(
    `${API_BASE}/strategies/quality-distribution`
  );
}

// Rankings
export async function getBacktestRanking(params?: { limit?: number }) {
  const searchParams = new URLSearchParams();
  if (params?.limit) searchParams.set('limit', params.limit.toString());

  const query = searchParams.toString();
  return fetchJson<import('../types').RankingResponse>(
    `${API_BASE}/strategies/rankings/backtest${query ? `?${query}` : ''}`
  );
}

export async function getLiveRanking(params?: { limit?: number }) {
  const searchParams = new URLSearchParams();
  if (params?.limit) searchParams.set('limit', params.limit.toString());

  const query = searchParams.toString();
  return fetchJson<import('../types').RankingResponse>(
    `${API_BASE}/strategies/rankings/live${query ? `?${query}` : ''}`
  );
}

export async function getDegradationAnalysis(params?: { threshold?: number }) {
  const searchParams = new URLSearchParams();
  if (params?.threshold) searchParams.set('threshold', params.threshold.toString());

  const query = searchParams.toString();
  return fetchJson<import('../types').DegradationResponse>(
    `${API_BASE}/strategies/degradation${query ? `?${query}` : ''}`
  );
}

export async function getPerformanceEquity(params?: { period?: string; strategy_id?: string }) {
  const searchParams = new URLSearchParams();
  if (params?.period) searchParams.set('period', params.period);
  if (params?.strategy_id) searchParams.set('strategy_id', params.strategy_id);

  const query = searchParams.toString();
  return fetchJson<import('../types').PerformanceEquityResponse>(
    `${API_BASE}/performance/equity${query ? `?${query}` : ''}`
  );
}

// Scheduler endpoints
export async function getTaskExecutions(params?: {
  task_name?: string;
  task_type?: string;
  status?: string;
  limit?: number;
}) {
  const searchParams = new URLSearchParams();
  if (params?.task_name) searchParams.set('task_name', params.task_name);
  if (params?.task_type) searchParams.set('task_type', params.task_type);
  if (params?.status) searchParams.set('status', params.status);
  if (params?.limit) searchParams.set('limit', params.limit.toString());

  const query = searchParams.toString();
  return fetchJson<import('../types').TaskExecutionListResponse>(
    `${API_BASE}/scheduler/tasks${query ? `?${query}` : ''}`
  );
}

export async function getTaskStats(taskName: string, periodHours: number = 24) {
  return fetchJson<import('../types').TaskStatsResponse>(
    `${API_BASE}/scheduler/tasks/${taskName}/stats?period_hours=${periodHours}`
  );
}

export async function triggerTask(taskName: string, triggeredBy: string) {
  return fetchJson<import('../types').TaskTriggerResponse>(
    `${API_BASE}/scheduler/tasks/${taskName}/trigger`,
    {
      method: 'POST',
      body: JSON.stringify({ triggered_by: triggeredBy }),
    }
  );
}

export async function getSchedulerHealth() {
  return fetchJson<any>(`${API_BASE}/scheduler/health`);
}

// Coin registry endpoints
export async function getCoinRegistryStats() {
  return fetchJson<import('../types').CoinRegistryStatsResponse>(
    `${API_BASE}/coins/registry/stats`
  );
}

export async function getPairsUpdateHistory(limit: number = 20) {
  return fetchJson<import('../types').PairsUpdateHistoryResponse>(
    `${API_BASE}/coins/pairs/history?limit=${limit}`
  );
}

// Pipeline Metrics endpoints
export async function getMetricsTimeseries(params: {
  period?: import('../types').MetricsPeriod;
  metric?: import('../types').MetricsType;
}) {
  const searchParams = new URLSearchParams();
  if (params.period) searchParams.set('period', params.period);
  if (params.metric) searchParams.set('metric', params.metric);

  const query = searchParams.toString();
  return fetchJson<import('../types').MetricsTimeseriesResponse>(
    `${API_BASE}/metrics/timeseries${query ? `?${query}` : ''}`
  );
}

export async function getMetricsAggregated(params?: {
  period?: import('../types').MetricsPeriod;
}) {
  const searchParams = new URLSearchParams();
  if (params?.period) searchParams.set('period', params.period);

  const query = searchParams.toString();
  return fetchJson<import('../types').MetricsAggregatedResponse>(
    `${API_BASE}/metrics/aggregated${query ? `?${query}` : ''}`
  );
}

export async function getMetricsAlerts() {
  return fetchJson<import('../types').MetricsAlertsResponse>(
    `${API_BASE}/metrics/alerts`
  );
}

export async function getMetricsCurrent() {
  return fetchJson<import('../types').MetricsCurrentResponse>(
    `${API_BASE}/metrics/current`
  );
}

// Event-based metrics endpoints
export async function getMetricsEvents(params?: {
  hours?: number;
  stage?: string;
  status?: string;
  limit?: number;
}) {
  const searchParams = new URLSearchParams();
  if (params?.hours) searchParams.set('hours', params.hours.toString());
  if (params?.stage) searchParams.set('stage', params.stage);
  if (params?.status) searchParams.set('status', params.status);
  if (params?.limit) searchParams.set('limit', params.limit.toString());

  const query = searchParams.toString();
  return fetchJson<import('../types').EventsResponse>(
    `${API_BASE}/metrics/events${query ? `?${query}` : ''}`
  );
}

export async function getMetricsFunnel(params?: { hours?: number }) {
  const searchParams = new URLSearchParams();
  if (params?.hours) searchParams.set('hours', params.hours.toString());

  const query = searchParams.toString();
  return fetchJson<import('../types').FunnelResponse>(
    `${API_BASE}/metrics/funnel${query ? `?${query}` : ''}`
  );
}

export async function getMetricsFailures(params?: { hours?: number }) {
  const searchParams = new URLSearchParams();
  if (params?.hours) searchParams.set('hours', params.hours.toString());

  const query = searchParams.toString();
  return fetchJson<import('../types').FailuresResponse>(
    `${API_BASE}/metrics/failures${query ? `?${query}` : ''}`
  );
}

export async function getMetricsTiming(params?: { hours?: number }) {
  const searchParams = new URLSearchParams();
  if (params?.hours) searchParams.set('hours', params.hours.toString());

  const query = searchParams.toString();
  return fetchJson<import('../types').TimingResponse>(
    `${API_BASE}/metrics/timing${query ? `?${query}` : ''}`
  );
}

// Full pipeline snapshot - real-time computed metrics
export async function getMetricsSnapshot() {
  return fetchJson<import('../types').MetricsSnapshotResponse>(
    `${API_BASE}/metrics/snapshot`
  );
}

// Positions - real-time from Hyperliquid
export async function getPositions(params?: { subaccount_id?: number }) {
  const searchParams = new URLSearchParams();
  if (params?.subaccount_id) searchParams.set('subaccount_id', params.subaccount_id.toString());

  const query = searchParams.toString();
  return fetchJson<import('../types').PositionsResponse>(
    `${API_BASE}/positions${query ? `?${query}` : ''}`
  );
}
