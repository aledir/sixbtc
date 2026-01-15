import { useQuery } from '@tanstack/react-query';
import { API_BASE } from '../lib/api';
import { FileCode, AlertCircle, Activity } from 'lucide-react';

export default function Templates() {
  const { data, isLoading, error } = useQuery({
    queryKey: ['templates'],
    queryFn: async () => {
      const res = await fetch(`${API_BASE}/templates`);
      if (!res.ok) throw new Error('Failed to fetch templates');
      return res.json();
    },
    refetchInterval: 60000,
  });

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
        <span>Error loading templates: {(error as Error).message}</span>
      </div>
    );
  }

  const templates = data?.items || [];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-[var(--color-text-primary)]">Strategy Templates</h1>
        <p className="text-sm text-[var(--color-text-secondary)] mt-1">
          Template analytics and success rates
        </p>
      </div>

      {/* Summary Stats - 2 cols mobile, 4 cols desktop */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="card">
          <div className="text-sm text-[var(--color-text-tertiary)]">Total Templates</div>
          <div className="text-2xl font-bold text-[var(--color-profit)] mt-1">{data?.total || 0}</div>
        </div>
        <div className="card">
          <div className="text-sm text-[var(--color-text-tertiary)]">Avg Success Rate</div>
          <div className="text-2xl font-bold text-[var(--color-text-primary)] mt-1">
            {templates.length > 0
              ? ((templates.reduce((sum: number, t: any) => sum + t.success_rate, 0) / templates.length) * 100).toFixed(1)
              : 0}%
          </div>
        </div>
        <div className="card">
          <div className="text-sm text-[var(--color-text-tertiary)]">Total Generated</div>
          <div className="text-2xl font-bold text-[var(--color-text-primary)] mt-1">
            {templates.reduce((sum: number, t: any) => sum + t.total_generated, 0)}
          </div>
        </div>
        <div className="card">
          <div className="text-sm text-[var(--color-text-tertiary)]">Live Strategies</div>
          <div className="text-2xl font-bold text-[var(--color-profit)] mt-1">
            {templates.reduce((sum: number, t: any) => sum + t.live, 0)}
          </div>
        </div>
      </div>

      {/* Templates Table */}
      <div className="card p-0 overflow-hidden">
        <div className="p-4 border-b border-[var(--color-border-primary)]">
          <h2 className="text-lg font-semibold flex items-center gap-2 text-[var(--color-text-primary)]">
            <FileCode size={20} />
            Templates
          </h2>
        </div>

        {templates.length === 0 ? (
          <div className="p-12 text-center text-[var(--color-text-tertiary)]">No templates found</div>
        ) : (
          <div className="table-responsive">
            <table className="table">
              <thead>
                <tr>
                  <th>Template</th>
                  <th className="hide-mobile">Type</th>
                  <th className="hide-mobile">TF</th>
                  <th className="text-right hide-mobile">Generated</th>
                  <th className="text-right hide-mobile">Tested</th>
                  <th className="text-right">Selected</th>
                  <th className="text-right">Live</th>
                  <th className="text-right">Success</th>
                </tr>
              </thead>
              <tbody>
                {templates.map((template: any) => (
                  <tr key={template.id} className="border-b border-[var(--color-border-primary)] hover:bg-[var(--color-bg-secondary)]">
                    <td className="px-4 py-3">
                      <div className="font-mono text-sm text-[var(--color-text-primary)]">{template.name}</div>
                    </td>
                    <td className="px-4 py-3 hide-mobile">
                      <span className="badge badge-neutral">
                        {template.strategy_type}
                      </span>
                    </td>
                    <td className="px-4 py-3 hide-mobile">
                      <span className="text-xs font-mono text-[var(--color-text-tertiary)]">{template.timeframe}</span>
                    </td>
                    <td className="px-4 py-3 text-right font-mono text-sm text-[var(--color-text-tertiary)] hide-mobile">
                      {template.total_generated}
                    </td>
                    <td className="px-4 py-3 text-right font-mono text-sm text-[var(--color-text-secondary)] hide-mobile">
                      {template.tested}
                    </td>
                    <td className="px-4 py-3 text-right font-mono text-sm text-[var(--color-profit)]">
                      {template.selected}
                    </td>
                    <td className="px-4 py-3 text-right font-mono text-sm font-semibold text-[var(--color-profit)]">
                      {template.live}
                    </td>
                    <td className="px-4 py-3 text-right font-mono text-sm font-bold">
                      <span className={template.success_rate >= 0.5 ? 'text-[var(--color-profit)]' : template.success_rate >= 0.3 ? 'text-[var(--color-warning)]' : 'text-[var(--color-loss)]'}>
                        {(template.success_rate * 100).toFixed(1)}%
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}
