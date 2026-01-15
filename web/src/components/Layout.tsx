import { NavLink, Outlet } from 'react-router-dom';
import { LayoutDashboard, TrendingUp, LineChart, ScrollText, Settings, AlertTriangle, Activity, Trophy, FileCode, CheckCircle, Clock } from 'lucide-react';
import { useStatus } from '../hooks/useApi';

const navItems = [
  { to: '/', icon: LayoutDashboard, label: 'Overview' },
  { to: '/pipeline', icon: Activity, label: 'Pipeline' },
  { to: '/rankings', icon: Trophy, label: 'Rankings' },
  { to: '/strategies', icon: TrendingUp, label: 'Strategies' },
  { to: '/templates', icon: FileCode, label: 'Templates' },
  { to: '/validation', icon: CheckCircle, label: 'Validation' },
  { to: '/trading', icon: LineChart, label: 'Trading' },
  { to: '/system-tasks', icon: Clock, label: 'System Tasks' },
  { to: '/logs', icon: ScrollText, label: 'Logs' },
  { to: '/settings', icon: Settings, label: 'Settings' },
];

function formatUptime(seconds: number): string {
  const days = Math.floor(seconds / 86400);
  const hours = Math.floor((seconds % 86400) / 3600);
  const mins = Math.floor((seconds % 3600) / 60);
  if (days > 0) return `${days}d ${hours}h`;
  if (hours > 0) return `${hours}h ${mins}m`;
  return `${mins}m`;
}

export default function Layout() {
  const { data: status, isError } = useStatus();

  const servicesOk = status?.services.every((s) => s.status === 'RUNNING') ?? false;
  const hasAlerts = (status?.alerts.length ?? 0) > 0;

  return (
    <div className="flex min-h-screen bg-background text-foreground font-mono">
      {/* Sidebar */}
      <aside className="w-56 bg-card border-r border-border flex flex-col">
        {/* Logo */}
        <div className="p-4 border-b border-border">
          <h1 className="text-xl font-bold text-profit">SixBTC</h1>
          <p className="text-xs text-muted mt-1">Control Center</p>
        </div>

        {/* Navigation */}
        <nav className="flex-1 p-2">
          {navItems.map(({ to, icon: Icon, label }) => (
            <NavLink
              key={to}
              to={to}
              end={to === '/'}
              className={({ isActive }) =>
                `flex items-center gap-3 px-3 py-2 rounded text-sm transition-colors ${
                  isActive
                    ? 'bg-profit/10 text-profit'
                    : 'text-muted hover:text-foreground hover:bg-white/5'
                }`
              }
            >
              <Icon size={18} />
              {label}
            </NavLink>
          ))}
        </nav>

        {/* System Status */}
        <div className="p-3 border-t border-border">
          <div className="flex items-center justify-between text-xs">
            <div className="flex items-center gap-2">
              <span
                className={`w-2 h-2 rounded-full ${
                  isError ? 'bg-loss' : servicesOk ? 'bg-profit animate-pulse' : 'bg-warning'
                }`}
              />
              <span className="text-muted">
                {isError ? 'API Offline' : servicesOk ? 'System OK' : 'Issues'}
              </span>
            </div>
            {status && (
              <span className="text-muted">{formatUptime(status.uptime_seconds)}</span>
            )}
          </div>
        </div>
      </aside>

      {/* Main Content */}
      <main className="flex-1 flex flex-col overflow-hidden">
        {/* Alert Bar */}
        {hasAlerts && (
          <div className="bg-warning/10 border-b border-warning/20 px-4 py-2">
            <div className="flex items-center gap-2 text-warning text-sm">
              <AlertTriangle size={16} />
              <span>{status?.alerts[0]?.message}</span>
              {(status?.alerts.length ?? 0) > 1 && (
                <span className="text-xs text-muted ml-2">
                  +{(status?.alerts.length ?? 1) - 1} more
                </span>
              )}
            </div>
          </div>
        )}

        {/* Page Content */}
        <div className="flex-1 overflow-auto p-6">
          <Outlet />
        </div>
      </main>
    </div>
  );
}
