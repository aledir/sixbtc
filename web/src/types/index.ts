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
  TESTED: number;
  SELECTED: number;
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
