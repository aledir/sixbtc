// API Types - matching backend schemas

export interface ServiceInfo {
  name: string;
  status: 'RUNNING' | 'STOPPED' | 'ERROR';
  pid: number | null;
  uptime_seconds: number | null;
}

export interface PipelineCounts {
  GENERATED: number;
  VALIDATED: number;
  ACTIVE: number;
  LIVE: number;
  RETIRED: number;
  FAILED: number;
}

export interface PortfolioSummary {
  total_pnl: number;
  total_pnl_pct: number;
  pnl_24h: number;
  pnl_24h_pct: number;
  pnl_7d: number;
  pnl_7d_pct: number;
  max_drawdown: number;
  open_positions: number;
  trades_today: number;
}

export interface Alert {
  level: 'info' | 'warning' | 'error';
  message: string;
  timestamp: string;
}

export interface StatusResponse {
  uptime_seconds: number;
  pipeline: PipelineCounts;
  services: ServiceInfo[];
  portfolio: PortfolioSummary;
  alerts: Alert[];
}

export interface StrategyListItem {
  id: string;
  name: string;
  strategy_type: string | null;
  timeframe: string | null;
  status: string;
  sharpe_ratio: number | null;
  win_rate: number | null;
  total_trades: number | null;
  total_pnl: number | null;
  created_at: string;
}

export interface BacktestMetrics {
  sharpe_ratio: number | null;
  win_rate: number | null;
  expectancy: number | null;
  max_drawdown: number | null;
  total_trades: number | null;
  total_return: number | null;
  ed_ratio: number | null;
  consistency: number | null;
  period_type: string | null;
  period_days: number | null;
}

export interface StrategyDetail {
  id: string;
  name: string;
  strategy_type: string | null;
  timeframe: string | null;
  status: string;
  code: string | null;
  pattern_ids: string[] | null;
  pattern_coins: string[] | null;
  created_at: string;
  updated_at: string | null;
  backtest: BacktestMetrics | null;
  live_pnl: number | null;
  live_trades: number | null;
}

export interface StrategiesResponse {
  items: StrategyListItem[];
  total: number;
  limit: number;
  offset: number;
}

export interface TradeItem {
  id: string;
  strategy_id: string;
  strategy_name: string | null;
  symbol: string;
  side: 'long' | 'short';
  status: 'open' | 'closed';
  entry_price: number;
  exit_price: number | null;
  size: number;
  pnl: number | null;
  pnl_pct: number | null;
  subaccount_index: number | null;
  opened_at: string;
  closed_at: string | null;
}

export interface TradesResponse {
  items: TradeItem[];
  total: number;
  limit: number;
  offset: number;
}

export interface TradesSummary {
  total_trades: number;
  winning_trades: number;
  losing_trades: number;
  win_rate: number;
  total_pnl: number;
  avg_pnl: number;
  best_trade: number;
  worst_trade: number;
}

export interface SubaccountInfo {
  index: number;
  status: 'active' | 'idle' | 'error';
  strategy_id: string | null;
  strategy_name: string | null;
  balance: number;
  pnl: number;
  pnl_pct: number;
  open_positions: number;
  last_trade_at: string | null;
}

export interface SubaccountsResponse {
  items: SubaccountInfo[];
  total_balance: number;
  total_pnl: number;
}

export interface LogLine {
  timestamp: string;
  level: string;
  logger: string;
  message: string;
}

export interface LogsResponse {
  service: string;
  lines: LogLine[];
  total_lines: number;
}

export interface ServiceControlResponse {
  success: boolean;
  message: string;
  service: string;
  action: string;
}

// Pipeline Health Types
export interface PipelineStageHealth {
  stage: string;
  status: 'healthy' | 'backpressure' | 'stalled' | 'error';
  queue_depth: number;
  queue_limit: number;
  utilization_pct: number;
  processing_rate: number;
  avg_processing_time: number | null;
  active_workers: number;
  max_workers: number;
  success_rate: number;
  failure_rate: number;
  processed_last_hour: number;
  processed_last_24h: number;
  failed_last_hour: number;
}

export interface PipelineHealthResponse {
  timestamp: string;
  overall_status: 'healthy' | 'degraded' | 'critical';
  stages: PipelineStageHealth[];
  bottleneck: string | null;
  throughput_strategies_per_hour: number;
  critical_issues: string[];
}

export interface PipelineTimeSeriesPoint {
  timestamp: string;
  stage: string;
  throughput: number;
  avg_processing_time: number | null;
  queue_depth: number;
  failures: number;
}

export interface PipelineStatsResponse {
  period_hours: number;
  data_points: PipelineTimeSeriesPoint[];
  total_generated: number;
  total_validated: number;
  total_active: number;
  total_live: number;
  overall_throughput: number;
  bottleneck_stage: string;
}

export interface QualityBucket {
  range: string;
  count: number;
  avg_sharpe: number;
  avg_win_rate: number;
}

export interface QualityDistribution {
  stage: string;
  buckets: QualityBucket[];
  by_type: Record<string, number>;
  by_timeframe: Record<string, number>;
}

export interface QualityDistributionResponse {
  distributions: QualityDistribution[];
}

// =============================================================================
// STRATEGY RANKINGS
// =============================================================================

export interface RankedStrategy {
  id: string;
  name: string;
  strategy_type: string;
  timeframe: string;
  status: string;
  score: number | null;
  sharpe: number | null;
  expectancy: number | null;
  win_rate: number | null;
  total_trades: number | null;
  max_drawdown: number | null;
  ranking_type: 'backtest' | 'live';

  // Live-specific fields
  score_backtest?: number | null;
  total_pnl?: number | null;
  degradation_pct?: number | null;
  last_update?: string | null;
}

export interface RankingResponse {
  ranking_type: 'backtest' | 'live';
  count: number;
  strategies: RankedStrategy[];
  avg_score: number;
  avg_sharpe?: number | null;
  avg_pnl?: number | null;
}

// =============================================================================
// DEGRADATION MONITORING
// =============================================================================

export interface DegradationPoint {
  id: string;
  name: string;
  strategy_type: string;
  timeframe: string;
  score_backtest: number | null;
  score_live: number | null;
  degradation_pct: number | null;
  total_pnl: number | null;
  total_trades_live: number | null;
  live_since: string | null;
}

export interface DegradationResponse {
  total_live_strategies: number;
  degrading_count: number;
  avg_degradation: number;
  worst_degraders: DegradationPoint[];
  all_points: DegradationPoint[];
}

// =============================================================================
// PERFORMANCE ANALYTICS
// =============================================================================

export interface EquityPoint {
  timestamp: string;
  equity: number;
  balance: number;
  unrealized_pnl: number;
  realized_pnl: number;
  total_pnl: number;
}

export interface PerformanceEquityResponse {
  period: string;
  subaccount_id: number | null;
  data_points: EquityPoint[];
  start_equity: number;
  end_equity: number;
  peak_equity: number;
  max_drawdown: number;
  current_drawdown: number;
  total_return: number;
}

// =============================================================================
// SCHEDULED TASKS
// =============================================================================

export interface TaskExecutionDetail {
  id: string;
  task_name: string;
  task_type: string;
  status: string;
  started_at: string;
  completed_at?: string;
  duration_seconds?: number;
  error_message?: string;
  metadata: Record<string, any>;
  triggered_by: string;
}

export interface TaskExecutionListResponse {
  executions: TaskExecutionDetail[];
  total: number;
}

export interface TaskStatsResponse {
  task_name: string;
  period_hours: number;
  total_executions: number;
  successful_executions: number;
  failed_executions: number;
  avg_duration_seconds?: number;
  failure_rate: number;
  last_execution?: string;
}

export interface TaskTriggerResponse {
  success: boolean;
  message: string;
  execution_id?: string;
}

// =============================================================================
// COIN REGISTRY
// =============================================================================

export interface CoinRegistryStatsResponse {
  total_coins: number;
  active_coins: number;
  cache_age_seconds?: number;
  db_updated_at?: string;
}

export interface PairsUpdateDetail {
  execution_id: string;
  started_at: string;
  completed_at?: string;
  duration_seconds?: number;
  status: string;
  total_pairs: number;
  new_pairs: number;
  updated_pairs: number;
  deactivated_pairs: number;
  top_10_symbols: string[];
}

export interface PairsUpdateHistoryResponse {
  updates: PairsUpdateDetail[];
  total: number;
}

// =============================================================================
// PIPELINE METRICS API
// =============================================================================

export type MetricsPeriod = '1h' | '6h' | '24h' | '7d' | '30d';
export type MetricsType = 'queue_depths' | 'throughput' | 'quality' | 'utilization' | 'success_rates';

// GET /api/metrics/timeseries - Queue Depths data point
export interface QueueDepthsDataPoint {
  timestamp: string;
  generated: number;
  validated: number;
  active: number;
  live: number;
  retired: number;
  failed: number;
}

// GET /api/metrics/timeseries - Throughput data point
export interface ThroughputDataPoint {
  timestamp: string;
  generation: number | null;
  validation: number | null;
  backtesting: number | null;
}

// GET /api/metrics/timeseries - Quality data point
export interface QualityDataPoint {
  timestamp: string;
  avg_sharpe: number | null;
  avg_win_rate: number | null;
  avg_expectancy: number | null;
}

// GET /api/metrics/timeseries - Utilization data point
export interface UtilizationDataPoint {
  timestamp: string;
  generated: number | null;
  validated: number | null;
  active: number | null;
}

// GET /api/metrics/timeseries - Success Rates data point
export interface SuccessRatesDataPoint {
  timestamp: string;
  validation: number | null;
  backtesting: number | null;
}

// GET /api/metrics/timeseries response
export interface MetricsTimeseriesResponse {
  period: MetricsPeriod;
  metric: MetricsType;
  data_points: number;
  data: QueueDepthsDataPoint[] | ThroughputDataPoint[] | QualityDataPoint[] | UtilizationDataPoint[] | SuccessRatesDataPoint[];
}

// GET /api/metrics/aggregated response
export interface MetricsAggregatedResponse {
  period: MetricsPeriod;
  snapshots_analyzed: number;
  queue_depths: {
    avg_generated: number;
    avg_validated: number;
    avg_active: number;
  };
  utilization: {
    max_generated: number;
    max_validated: number;
    max_active: number;
  };
  quality: {
    avg_sharpe: number | null;
    avg_win_rate: number | null;
  };
  success_rates: {
    avg_validation: number | null;
    avg_backtesting: number | null;
  };
}

// GET /api/metrics/alerts
export type AlertSeverity = 'info' | 'warning' | 'critical';
export type AlertType = 'backpressure' | 'low_throughput' | 'quality_degradation' | 'system_critical';

export interface MetricAlert {
  severity: AlertSeverity;
  type: AlertType;
  message: string;
  duration_minutes: number;
  current_value?: number;
  bottleneck?: string;
}

export interface MetricsAlertsResponse {
  timestamp: string;
  alerts_count: number;
  alerts: MetricAlert[];
}

// GET /api/metrics/current response
export interface MetricsCurrentResponse {
  timestamp: string;
  overall_status: 'healthy' | 'degraded' | 'critical';
  bottleneck_stage: string | null;
  queue_depths: {
    generated: number;
    validated: number;
    active: number;
    live: number;
    retired: number;
    failed: number;
  };
  utilization: {
    generated: number | null;
    validated: number | null;
    active: number | null;
  };
  throughput: {
    generation: number | null;
    validation: number | null;
    backtesting: number | null;
  };
  quality: {
    avg_sharpe: number | null;
    avg_win_rate: number | null;
    avg_expectancy: number | null;
  };
  success_rates: {
    validation: number | null;
    backtesting: number | null;
  };
  breakdown: {
    pattern_strategies: number;
    ai_strategies: number;
  };
}

// =============================================================================
// PIPELINE EVENTS (Event-based tracking)
// =============================================================================

// GET /api/metrics/events
export interface StrategyEvent {
  id: string;
  timestamp: string;
  strategy_name: string;
  stage: string;
  event_type: string;
  status: 'started' | 'passed' | 'failed' | 'completed';
  duration_ms: number | null;
  metadata: Record<string, any> | null;
}

export interface EventsResponse {
  period_hours: number;
  filters: {
    stage: string | null;
    status: string | null;
  };
  count: number;
  events: StrategyEvent[];
}

// GET /api/metrics/funnel
export interface FunnelStage {
  stage: string;
  count: number;
  failed?: number;
  conversion_rate: number;
}

export interface FunnelResponse {
  period_hours: number;
  funnel: FunnelStage[];
  overall_conversion: number;
  retired_count: number;
}

// GET /api/metrics/failures
export interface FailureReason {
  reason: string;
  count: number;
  percentage: number;
}

export interface StageFailures {
  stage: string;
  total: number;
  reasons: FailureReason[];
}

export interface FailuresResponse {
  period_hours: number;
  total_failures: number;
  by_stage: StageFailures[];
}

// GET /api/metrics/timing
export interface StageTiming {
  avg_ms: number | null;
  min_ms: number | null;
  max_ms: number | null;
  sample_count: number;
}

export interface TimingResponse {
  period_hours: number;
  timing: Record<string, StageTiming>;
}

// =============================================================================
// FULL PIPELINE SNAPSHOT (GET /api/metrics/snapshot)
// =============================================================================

export interface SnapshotCapital {
  total: number;
  main_account: number;
  subaccounts: number;
}

export interface SnapshotGenerator {
  total_24h: number;
  by_source: Record<string, number>;
  by_type: Record<string, number>;
  by_direction: Record<string, number>;
  by_timeframe: Record<string, number>;
  timing_by_source: Record<string, number | null>;
  leverage: {
    min: number | null;
    max: number | null;
    avg: number | null;
  };
  by_provider: Record<string, number>;
  failures: number;
}

export interface SnapshotAiCalls {
  count: number | null;
  max_calls: number | null;
  remaining: number | null;
}

export interface SnapshotPatterns {
  unique_used: number;
  total_available: number | null;
  remaining: number | null;
}

export interface SnapshotValidator {
  queue: number;
  passed_24h: number;
  failed_24h: number;
  by_source_passed: Record<string, number>;
  by_source_failed: Record<string, number>;
  timing_avg_ms: number | null;
}

export interface SnapshotParametric {
  waiting: number;
  processing: number;
  total_bases: number;
  total_combos: number;
  passed_combos: number;
  failed_combos: number;
  bases_with_passed: number;
  bases_with_failed: number;
  passed_avg: {
    sharpe: number;
    wr: number;
    exp: number;
    trades: number;
  } | null;
  failed_avg: {
    sharpe: number;
    wr: number;
    exp: number;
    trades: number;
  } | null;
  fail_reasons: {
    sharpe: number;
    wr: number;
    exp: number;
    dd: number;
    trades: number;
  };
  avg_duration_ms: number | null;
  min_duration_ms: number | null;
  max_duration_ms: number | null;
}

export interface SnapshotBacktestStats {
  count: number;
  passed: number;
  failed: number;
  passed_avg: {
    sharpe: number | null;
    wr: number | null;
    exp: number | null;
    trades: number | null;
    dd?: number | null;
  };
  failed_avg: {
    sharpe: number | null;
    wr: number | null;
    exp: number | null;
    trades: number | null;
    dd?: number | null;
  };
  fail_reasons: {
    sharpe: number;
    wr: number;
    exp: number;
    dd: number;
    trades: number;
  };
  avg_duration_ms: number | null;
}

export interface SnapshotScore {
  min_score: number;
  max_score: number;
  avg_score: number;
}

export interface SnapshotShuffle {
  failed: number;
  cached: number;
}

export interface SnapshotWfa {
  failed: number;
}

export interface SnapshotRobustness {
  passed: number;
  failed: number;
  avg_passed: number | null;
  min_threshold: number;
  pool: {
    avg_robustness: number | null;
    min_robustness: number | null;
    max_robustness: number | null;
  };
}

export interface SnapshotPoolQuality {
  expectancy_avg: number | null;
  sharpe_avg: number | null;
  winrate_avg: number | null;
  dd_avg: number | null;
}

export interface SnapshotPool {
  size: number;
  limit: number;
  score_min: number | null;
  score_max: number | null;
  score_avg: number | null;
  quality: SnapshotPoolQuality;
  by_source: Record<string, number>;
  avg_score_by_source: Record<string, number | null>;
  added_24h_by_source: Record<string, number>;
}

export interface SnapshotRetest {
  tested: number;
  passed: number;
  failed: number;
  pass_rate: number | null;
}

export interface SnapshotLive {
  count: number;
  avg_age_days: number | null;
  avg_score: number | null;
  type_distribution: Record<string, number>;
  timeframe_distribution: Record<string, number>;
  direction_distribution: Record<string, number>;
  rotations_24h: number;
  retirements_24h: number;
}

export interface SnapshotSubaccount {
  id: number;
  balance: number;
  strategy_name: string | null;
  timeframe: string | null;
  direction: string | null;
  coins_count: number;
  uptime_days: number | null;
  rpnl: number;
  rpnl_pct: number;
  upnl: number;
  positions: number;
  dd_pct: number;
  wr_pct: number;
  // True P&L from Hyperliquid (if available)
  hl_balance?: number;
  hl_net_deposits?: number;
  hl_true_pnl?: number;
  hl_true_pnl_pct?: number;
}

export interface SnapshotSchedulerTask {
  last_run: string | null;
  next_run: string | null;
  status: string;
  metadata: Record<string, any>;
}

export interface SnapshotScheduler {
  total_ok: number;
  total_tasks: number;
  tasks: Record<string, SnapshotSchedulerTask>;
}

export interface SnapshotBackpressure {
  gen_queue: number;
  gen_limit: number;
  gen_full: boolean;
  val_queue: number;
  val_limit: number;
  bt_waiting: number;
  bt_processing: number;
}

export interface SnapshotFunnel {
  generated: number;
  validated: number;
  validation_failed: number;
  combinations_tested: number;
  is_passed: number;
  oos_passed: number;
  score_passed: number;
  shuffle_passed: number;
  multi_window_passed: number;
  robustness_passed: number;
  pool_added: number;
  live: number;
}

export interface SnapshotThroughput {
  generated: number;
  validated: number;
  backtested: number;
}

export interface SnapshotTiming {
  validation: number | null;
  backtesting: number | null;
}

export interface SnapshotFailures {
  validation: number;
  parametric_fail: number;
  score_reject: number;
  shuffle_fail: number;
  shuffle_cached: number;
  mw_fail: number;
  pool_reject: number;
}

// Full snapshot response
export interface MetricsSnapshotResponse {
  timestamp: string;
  status: string;
  issue: string | null;
  trading_mode: 'DRY_RUN' | 'LIVE';

  capital: SnapshotCapital;
  queue_depths: Record<string, number>;

  generator: SnapshotGenerator;
  ai_calls: SnapshotAiCalls;
  patterns: SnapshotPatterns;

  validator: SnapshotValidator;
  parametric: SnapshotParametric;
  is_backtest: SnapshotBacktestStats;
  oos_backtest: SnapshotBacktestStats;
  score: SnapshotScore;
  shuffle: SnapshotShuffle;
  wfa: SnapshotWfa;
  robustness: SnapshotRobustness;
  pool: SnapshotPool;
  retest: SnapshotRetest;
  live: SnapshotLive;

  subaccounts: SnapshotSubaccount[];
  scheduler: SnapshotScheduler;

  backpressure: SnapshotBackpressure;
  funnel: SnapshotFunnel;
  throughput: SnapshotThroughput;
  timing: SnapshotTiming;
  failures: SnapshotFailures;
}
