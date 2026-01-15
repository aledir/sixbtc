import { useQuery } from '@tanstack/react-query';
import { CheckCircle, XCircle, AlertCircle, Activity } from 'lucide-react';
import { PieChart, Pie, Cell, ResponsiveContainer, Legend, Tooltip } from 'recharts';
import { useTheme } from '../contexts/ThemeContext';

export default function Validation() {
  const { theme } = useTheme();
  const { data, isLoading, error } = useQuery({
    queryKey: ['validationReport'],
    queryFn: async () => {
      const res = await fetch('http://localhost:8080/api/validation/report');
      if (!res.ok) throw new Error('Failed to fetch validation report');
      return res.json();
    },
    refetchInterval: 60000,
  });

  // Chart colors based on theme
  const chartColors = {
    tooltip: {
      bg: theme === 'dark' ? '#1e293b' : '#ffffff',
      border: theme === 'dark' ? '#334155' : '#e2e8f0',
      text: theme === 'dark' ? '#e2e8f0' : '#1e293b',
    },
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Activity className="w-8 h-8 animate-spin text-[var(--color-text-tertiary)]" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center gap-2 text-[var(--color-loss)]">
        <AlertCircle size={20} />
        <span>Error loading validation report: {(error as Error).message}</span>
      </div>
    );
  }

  const chartData = [
    { name: 'Passed', value: data?.passed || 0, color: '#10b981' },
    { name: 'Failed', value: data?.failed || 0, color: '#ef4444' },
  ];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-[var(--color-text-primary)]">Validation Report</h1>
        <p className="text-sm text-[var(--color-text-secondary)] mt-1">
          Strategy validation statistics and pass/fail rates
        </p>
      </div>

      {/* Summary Cards - 1 col mobile, 3 cols desktop */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div className="card">
          <div className="flex items-center gap-3">
            <div className="w-12 h-12 rounded-full bg-[var(--color-bg-secondary)] flex items-center justify-center">
              <CheckCircle size={24} className="text-[var(--color-text-secondary)]" />
            </div>
            <div>
              <div className="text-sm text-[var(--color-text-tertiary)]">Total Validated</div>
              <div className="text-2xl font-bold text-[var(--color-text-primary)]">{data?.total_validated || 0}</div>
            </div>
          </div>
        </div>

        <div className="card">
          <div className="flex items-center gap-3">
            <div className="w-12 h-12 rounded-full bg-[var(--color-profit)]/20 flex items-center justify-center">
              <CheckCircle size={24} className="text-[var(--color-profit)]" />
            </div>
            <div>
              <div className="text-sm text-[var(--color-text-tertiary)]">Passed</div>
              <div className="text-2xl font-bold text-[var(--color-profit)]">{data?.passed || 0}</div>
              <div className="text-xs text-[var(--color-text-tertiary)] mt-1">
                {((data?.pass_rate || 0) * 100).toFixed(1)}% pass rate
              </div>
            </div>
          </div>
        </div>

        <div className="card">
          <div className="flex items-center gap-3">
            <div className="w-12 h-12 rounded-full bg-[var(--color-loss)]/20 flex items-center justify-center">
              <XCircle size={24} className="text-[var(--color-loss)]" />
            </div>
            <div>
              <div className="text-sm text-[var(--color-text-tertiary)]">Failed</div>
              <div className="text-2xl font-bold text-[var(--color-loss)]">{data?.failed || 0}</div>
              <div className="text-xs text-[var(--color-text-tertiary)] mt-1">
                {((data?.fail_rate || 0) * 100).toFixed(1)}% fail rate
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Two column layout on desktop */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Chart */}
        <div className="card">
          <h2 className="text-sm font-semibold text-[var(--color-text-tertiary)] uppercase mb-4">
            Validation Distribution
          </h2>
          <div className="h-64 sm:h-80">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie
                  data={chartData}
                  cx="50%"
                  cy="50%"
                  labelLine={false}
                  label={({ name, percent }) => `${name}: ${((percent || 0) * 100).toFixed(0)}%`}
                  outerRadius={100}
                  fill="#8884d8"
                  dataKey="value"
                >
                  {chartData.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={entry.color} />
                  ))}
                </Pie>
                <Tooltip
                  contentStyle={{
                    backgroundColor: chartColors.tooltip.bg,
                    border: `1px solid ${chartColors.tooltip.border}`,
                    borderRadius: '8px',
                    fontSize: '12px',
                  }}
                  labelStyle={{ color: chartColors.tooltip.text }}
                />
                <Legend
                  wrapperStyle={{ fontSize: '12px' }}
                />
              </PieChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Validation Criteria Info */}
        <div className="card">
          <h2 className="text-sm font-semibold text-[var(--color-text-tertiary)] uppercase mb-4">
            Validation Criteria
          </h2>
          <div className="space-y-4">
            <div className="flex items-start gap-3 p-3 bg-[var(--color-bg-secondary)] rounded-lg">
              <CheckCircle size={18} className="text-[var(--color-profit)] mt-0.5 flex-shrink-0" />
              <div>
                <div className="font-semibold text-[var(--color-text-primary)]">Lookahead Bias Check</div>
                <div className="text-sm text-[var(--color-text-secondary)] mt-1">
                  AST analysis to detect future data usage
                </div>
              </div>
            </div>
            <div className="flex items-start gap-3 p-3 bg-[var(--color-bg-secondary)] rounded-lg">
              <CheckCircle size={18} className="text-[var(--color-profit)] mt-0.5 flex-shrink-0" />
              <div>
                <div className="font-semibold text-[var(--color-text-primary)]">Shuffle Test</div>
                <div className="text-sm text-[var(--color-text-secondary)] mt-1">
                  Empirical validation for temporal stability
                </div>
              </div>
            </div>
            <div className="flex items-start gap-3 p-3 bg-[var(--color-bg-secondary)] rounded-lg">
              <CheckCircle size={18} className="text-[var(--color-profit)] mt-0.5 flex-shrink-0" />
              <div>
                <div className="font-semibold text-[var(--color-text-primary)]">Walk-Forward Validation</div>
                <div className="text-sm text-[var(--color-text-secondary)] mt-1">
                  Performance consistency across time windows
                </div>
              </div>
            </div>
            <div className="flex items-start gap-3 p-3 bg-[var(--color-bg-secondary)] rounded-lg">
              <CheckCircle size={18} className="text-[var(--color-profit)] mt-0.5 flex-shrink-0" />
              <div>
                <div className="font-semibold text-[var(--color-text-primary)]">Syntax & Execution</div>
                <div className="text-sm text-[var(--color-text-secondary)] mt-1">
                  Code syntax verification and safe execution test
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
