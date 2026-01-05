import { useQuery } from '@tanstack/react-query';
import { API_BASE } from '../lib/api';
import { FileCode, AlertCircle } from 'lucide-react';

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
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-profit"></div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center gap-2 text-loss">
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
        <h1 className="text-2xl font-bold">Strategy Templates</h1>
        <p className="text-sm text-muted mt-1">
          Template analytics and success rates
        </p>
      </div>

      {/* Summary Stats */}
      <div className="grid grid-cols-4 gap-4">
        <div className="bg-card border border-border rounded-lg p-4">
          <div className="text-sm text-muted">Total Templates</div>
          <div className="text-2xl font-bold text-profit mt-1">{data?.total || 0}</div>
        </div>
        <div className="bg-card border border-border rounded-lg p-4">
          <div className="text-sm text-muted">Avg Success Rate</div>
          <div className="text-2xl font-bold text-foreground mt-1">
            {templates.length > 0
              ? ((templates.reduce((sum: number, t: any) => sum + t.success_rate, 0) / templates.length) * 100).toFixed(1)
              : 0}%
          </div>
        </div>
        <div className="bg-card border border-border rounded-lg p-4">
          <div className="text-sm text-muted">Total Generated</div>
          <div className="text-2xl font-bold text-foreground mt-1">
            {templates.reduce((sum: number, t: any) => sum + t.total_generated, 0)}
          </div>
        </div>
        <div className="bg-card border border-border rounded-lg p-4">
          <div className="text-sm text-muted">Live Strategies</div>
          <div className="text-2xl font-bold text-profit mt-1">
            {templates.reduce((sum: number, t: any) => sum + t.live, 0)}
          </div>
        </div>
      </div>

      {/* Templates Table */}
      <div className="bg-card border border-border rounded-lg">
        <div className="p-4 border-b border-border">
          <h2 className="text-lg font-semibold flex items-center gap-2">
            <FileCode size={20} />
            Templates
          </h2>
        </div>

        {templates.length === 0 ? (
          <div className="p-12 text-center text-muted">No templates found</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-white/5 border-b border-border">
                <tr className="text-left text-xs text-muted">
                  <th className="py-2 px-4 font-medium">Template</th>
                  <th className="py-2 px-4 font-medium">Type</th>
                  <th className="py-2 px-4 font-medium">TF</th>
                  <th className="py-2 px-4 font-medium text-right">Generated</th>
                  <th className="py-2 px-4 font-medium text-right">Tested</th>
                  <th className="py-2 px-4 font-medium text-right">Selected</th>
                  <th className="py-2 px-4 font-medium text-right">Live</th>
                  <th className="py-2 px-4 font-medium text-right">Success Rate</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {templates.map((template: any) => (
                  <tr key={template.id} className="hover:bg-white/5">
                    <td className="py-3 px-4">
                      <div className="font-mono text-foreground">{template.name}</div>
                    </td>
                    <td className="py-3 px-4">
                      <span className="px-2 py-1 rounded bg-white/10 text-xs font-mono">
                        {template.strategy_type}
                      </span>
                    </td>
                    <td className="py-3 px-4">
                      <span className="text-xs font-mono text-muted">{template.timeframe}</span>
                    </td>
                    <td className="py-3 px-4 text-right font-mono text-muted">
                      {template.total_generated}
                    </td>
                    <td className="py-3 px-4 text-right font-mono">
                      {template.tested}
                    </td>
                    <td className="py-3 px-4 text-right font-mono text-profit">
                      {template.selected}
                    </td>
                    <td className="py-3 px-4 text-right font-mono font-semibold text-profit">
                      {template.live}
                    </td>
                    <td className="py-3 px-4 text-right font-mono font-bold">
                      <span className={template.success_rate >= 0.5 ? 'text-profit' : template.success_rate >= 0.3 ? 'text-warning' : 'text-loss'}>
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
