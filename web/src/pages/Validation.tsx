import { useQuery } from '@tanstack/react-query';
import { CheckCircle, XCircle, AlertCircle } from 'lucide-react';
import { PieChart, Pie, Cell, ResponsiveContainer, Legend, Tooltip } from 'recharts';

export default function Validation() {
  const { data, isLoading, error } = useQuery({
    queryKey: ['validationReport'],
    queryFn: async () => {
      const res = await fetch('http://localhost:8080/api/validation/report');
      if (!res.ok) throw new Error('Failed to fetch validation report');
      return res.json();
    },
    refetchInterval: 60000,
  });

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-profit"></div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center gap-2 text-loss">
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
        <h1 className="text-2xl font-bold">Validation Report</h1>
        <p className="text-sm text-muted mt-1">
          Strategy validation statistics and pass/fail rates
        </p>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-3 gap-4">
        <div className="bg-card border border-border rounded-lg p-6">
          <div className="flex items-center gap-3">
            <div className="w-12 h-12 rounded-full bg-white/10 flex items-center justify-center">
              <CheckCircle size={24} className="text-foreground" />
            </div>
            <div>
              <div className="text-sm text-muted">Total Validated</div>
              <div className="text-2xl font-bold text-foreground">{data?.total_validated || 0}</div>
            </div>
          </div>
        </div>

        <div className="bg-card border border-border rounded-lg p-6">
          <div className="flex items-center gap-3">
            <div className="w-12 h-12 rounded-full bg-profit/20 flex items-center justify-center">
              <CheckCircle size={24} className="text-profit" />
            </div>
            <div>
              <div className="text-sm text-muted">Passed</div>
              <div className="text-2xl font-bold text-profit">{data?.passed || 0}</div>
              <div className="text-xs text-muted mt-1">
                {((data?.pass_rate || 0) * 100).toFixed(1)}% pass rate
              </div>
            </div>
          </div>
        </div>

        <div className="bg-card border border-border rounded-lg p-6">
          <div className="flex items-center gap-3">
            <div className="w-12 h-12 rounded-full bg-loss/20 flex items-center justify-center">
              <XCircle size={24} className="text-loss" />
            </div>
            <div>
              <div className="text-sm text-muted">Failed</div>
              <div className="text-2xl font-bold text-loss">{data?.failed || 0}</div>
              <div className="text-xs text-muted mt-1">
                {((data?.fail_rate || 0) * 100).toFixed(1)}% fail rate
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Chart */}
      <div className="bg-card border border-border rounded-lg p-6">
        <h2 className="text-lg font-semibold mb-4">Validation Distribution</h2>
        <div className="h-80">
          <ResponsiveContainer width="100%" height={320}>
            <PieChart>
              <Pie
                data={chartData}
                cx="50%"
                cy="50%"
                labelLine={false}
                label={({ name, percent }) => `${name}: ${((percent || 0) * 100).toFixed(0)}%`}
                outerRadius={120}
                fill="#8884d8"
                dataKey="value"
              >
                {chartData.map((entry, index) => (
                  <Cell key={`cell-${index}`} fill={entry.color} />
                ))}
              </Pie>
              <Tooltip />
              <Legend />
            </PieChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Validation Criteria Info */}
      <div className="bg-card border border-border rounded-lg p-6">
        <h2 className="text-lg font-semibold mb-4">Validation Criteria</h2>
        <div className="space-y-3 text-sm">
          <div className="flex items-start gap-3">
            <CheckCircle size={16} className="text-profit mt-0.5" />
            <div>
              <div className="font-semibold">Lookahead Bias Check</div>
              <div className="text-muted">AST analysis to detect future data usage</div>
            </div>
          </div>
          <div className="flex items-start gap-3">
            <CheckCircle size={16} className="text-profit mt-0.5" />
            <div>
              <div className="font-semibold">Shuffle Test</div>
              <div className="text-muted">Empirical validation for temporal stability</div>
            </div>
          </div>
          <div className="flex items-start gap-3">
            <CheckCircle size={16} className="text-profit mt-0.5" />
            <div>
              <div className="font-semibold">Walk-Forward Validation</div>
              <div className="text-muted">Performance consistency across time windows</div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
