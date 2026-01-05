// React Query hooks for API calls

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import * as api from '../lib/api';

// Refresh intervals (ms)
const FAST_REFRESH = 10000;   // 10 seconds for live data
const SLOW_REFRESH = 60000;   // 1 minute for less critical data

// Status
export function useStatus() {
  return useQuery({
    queryKey: ['status'],
    queryFn: api.getStatus,
    refetchInterval: FAST_REFRESH,
  });
}

// Strategies
export function useStrategies(params?: Parameters<typeof api.getStrategies>[0]) {
  return useQuery({
    queryKey: ['strategies', params],
    queryFn: () => api.getStrategies(params),
    refetchInterval: SLOW_REFRESH,
  });
}

export function useStrategy(id: string | null) {
  return useQuery({
    queryKey: ['strategy', id],
    queryFn: () => api.getStrategy(id!),
    enabled: !!id,
  });
}

export function useStrategyBacktest(id: string | null) {
  return useQuery({
    queryKey: ['strategyBacktest', id],
    queryFn: () => api.getStrategyBacktest(id!),
    enabled: !!id,
  });
}

// Trades
export function useTrades(params?: Parameters<typeof api.getTrades>[0]) {
  return useQuery({
    queryKey: ['trades', params],
    queryFn: () => api.getTrades(params),
    refetchInterval: FAST_REFRESH,
  });
}

export function useTradesSummary(params?: Parameters<typeof api.getTradesSummary>[0]) {
  return useQuery({
    queryKey: ['tradesSummary', params],
    queryFn: () => api.getTradesSummary(params),
    refetchInterval: SLOW_REFRESH,
  });
}

// Subaccounts
export function useSubaccounts() {
  return useQuery({
    queryKey: ['subaccounts'],
    queryFn: api.getSubaccounts,
    refetchInterval: FAST_REFRESH,
  });
}

// Services
export function useServices() {
  return useQuery({
    queryKey: ['services'],
    queryFn: api.getServices,
    refetchInterval: FAST_REFRESH,
  });
}

export function useServiceControl() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ name, action }: { name: string; action: 'start' | 'stop' | 'restart' }) =>
      api.controlService(name, action),
    onSuccess: () => {
      // Invalidate services query to refresh status
      queryClient.invalidateQueries({ queryKey: ['services'] });
      queryClient.invalidateQueries({ queryKey: ['status'] });
    },
  });
}

export function useEmergencyStop() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: api.emergencyStop,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['services'] });
      queryClient.invalidateQueries({ queryKey: ['status'] });
    },
  });
}

// Logs
export function useLogs(service: string, params?: Parameters<typeof api.getLogs>[1]) {
  return useQuery({
    queryKey: ['logs', service, params],
    queryFn: () => api.getLogs(service, params),
    refetchInterval: FAST_REFRESH,
  });
}

// Config
export function useConfig() {
  return useQuery({
    queryKey: ['config'],
    queryFn: api.getConfig,
    staleTime: Infinity, // Config rarely changes
  });
}

export function useThresholds() {
  return useQuery({
    queryKey: ['thresholds'],
    queryFn: api.getThresholds,
    staleTime: Infinity,
  });
}

// Pipeline Health
export function usePipelineHealth() {
  return useQuery({
    queryKey: ['pipelineHealth'],
    queryFn: api.getPipelineHealth,
    refetchInterval: FAST_REFRESH,  // 10s for real-time monitoring
  });
}

export function usePipelineStats(params: { period: string }) {
  return useQuery({
    queryKey: ['pipelineStats', params],
    queryFn: () => api.getPipelineStats(params),
    refetchInterval: SLOW_REFRESH,  // 60s
  });
}

export function useQualityDistribution() {
  return useQuery({
    queryKey: ['qualityDistribution'],
    queryFn: api.getQualityDistribution,
    refetchInterval: SLOW_REFRESH,  // 60s
  });
}

// Rankings
export function useBacktestRanking(params?: Parameters<typeof api.getBacktestRanking>[0]) {
  return useQuery({
    queryKey: ['backtestRanking', params],
    queryFn: () => api.getBacktestRanking(params),
    refetchInterval: SLOW_REFRESH,  // 60s
  });
}

export function useLiveRanking(params?: Parameters<typeof api.getLiveRanking>[0]) {
  return useQuery({
    queryKey: ['liveRanking', params],
    queryFn: () => api.getLiveRanking(params),
    refetchInterval: FAST_REFRESH,  // 10s for live monitoring
  });
}

export function useDegradationAnalysis(params?: Parameters<typeof api.getDegradationAnalysis>[0]) {
  return useQuery({
    queryKey: ['degradationAnalysis', params],
    queryFn: () => api.getDegradationAnalysis(params),
    refetchInterval: FAST_REFRESH,  // 10s for live monitoring
  });
}

// Performance
export function usePerformanceEquity(params?: Parameters<typeof api.getPerformanceEquity>[0]) {
  return useQuery({
    queryKey: ['performanceEquity', params],
    queryFn: () => api.getPerformanceEquity(params),
    refetchInterval: SLOW_REFRESH,  // 60s
  });
}

// Scheduler hooks
export function useTaskExecutions(params?: Parameters<typeof api.getTaskExecutions>[0]) {
  return useQuery({
    queryKey: ['taskExecutions', params],
    queryFn: () => api.getTaskExecutions(params),
    refetchInterval: SLOW_REFRESH,
  });
}

export function useTaskStats(taskName: string, periodHours: number = 24) {
  return useQuery({
    queryKey: ['taskStats', taskName, periodHours],
    queryFn: () => api.getTaskStats(taskName, periodHours),
    refetchInterval: SLOW_REFRESH,
  });
}

export function useSchedulerHealth() {
  return useQuery({
    queryKey: ['schedulerHealth'],
    queryFn: api.getSchedulerHealth,
    refetchInterval: FAST_REFRESH,
  });
}

export function useTriggerTask() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ taskName, triggeredBy }: { taskName: string; triggeredBy: string }) =>
      api.triggerTask(taskName, triggeredBy),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['taskExecutions'] });
      queryClient.invalidateQueries({ queryKey: ['schedulerHealth'] });
    },
  });
}

// Coin registry hooks
export function useCoinRegistryStats() {
  return useQuery({
    queryKey: ['coinRegistryStats'],
    queryFn: api.getCoinRegistryStats,
    refetchInterval: SLOW_REFRESH,
  });
}

export function usePairsUpdateHistory(limit: number = 20) {
  return useQuery({
    queryKey: ['pairsUpdateHistory', limit],
    queryFn: () => api.getPairsUpdateHistory(limit),
    refetchInterval: SLOW_REFRESH,
  });
}

// Pipeline Metrics hooks
export function useMetricsTimeseries(params: Parameters<typeof api.getMetricsTimeseries>[0]) {
  return useQuery({
    queryKey: ['metricsTimeseries', params],
    queryFn: () => api.getMetricsTimeseries(params),
    refetchInterval: SLOW_REFRESH,  // 60s - historical data
  });
}

export function useMetricsAggregated(params?: Parameters<typeof api.getMetricsAggregated>[0]) {
  return useQuery({
    queryKey: ['metricsAggregated', params],
    queryFn: () => api.getMetricsAggregated(params),
    refetchInterval: SLOW_REFRESH,  // 60s - aggregate stats
  });
}

export function useMetricsAlerts() {
  return useQuery({
    queryKey: ['metricsAlerts'],
    queryFn: api.getMetricsAlerts,
    refetchInterval: FAST_REFRESH,  // 10s - critical for alerts
  });
}

export function useMetricsCurrent() {
  return useQuery({
    queryKey: ['metricsCurrent'],
    queryFn: api.getMetricsCurrent,
    refetchInterval: FAST_REFRESH,  // 10s - current state
  });
}
