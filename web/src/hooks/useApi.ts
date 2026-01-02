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
