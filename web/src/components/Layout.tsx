import { Link, useLocation } from 'react-router-dom';
import {
  LayoutDashboard,
  TrendingUp,
  LineChart,
  FileText,
  Settings,
  AlertTriangle,
} from 'lucide-react';
import { useEmergencyStop } from '../hooks/useApi';

interface LayoutProps {
  children: React.ReactNode;
}

const navigation = [
  { name: 'Overview', href: '/', icon: LayoutDashboard },
  { name: 'Strategies', href: '/strategies', icon: TrendingUp },
  { name: 'Trading', href: '/trading', icon: LineChart },
  { name: 'Logs', href: '/logs', icon: FileText },
  { name: 'Settings', href: '/settings', icon: Settings },
];

export function Layout({ children }: LayoutProps) {
  const location = useLocation();
  const emergencyStop = useEmergencyStop();

  const handleEmergencyStop = () => {
    if (confirm('Are you sure you want to trigger EMERGENCY STOP? This will halt all trading.')) {
      emergencyStop.mutate();
    }
  };

  return (
    <div className="flex min-h-screen w-full">
      {/* Sidebar */}
      <aside className="w-64 bg-card border-r border-terminal flex flex-col">
        {/* Logo */}
        <div className="p-4 border-b border-terminal">
          <h1 className="text-xl font-bold text-profit">SixBTC</h1>
          <p className="text-sm text-muted">Control Center</p>
        </div>

        {/* Navigation */}
        <nav className="flex-1 p-4 space-y-2">
          {navigation.map((item) => {
            const isActive = location.pathname === item.href;
            return (
              <Link
                key={item.name}
                to={item.href}
                className={`flex items-center gap-3 px-3 py-2 rounded-md text-sm transition-colors ${
                  isActive
                    ? 'bg-profit/10 text-profit'
                    : 'text-muted hover:text-foreground hover:bg-white/5'
                }`}
              >
                <item.icon className="w-5 h-5" />
                {item.name}
              </Link>
            );
          })}
        </nav>

        {/* Emergency Stop Button */}
        <div className="p-4 border-t border-terminal">
          <button
            onClick={handleEmergencyStop}
            disabled={emergencyStop.isPending}
            className="w-full flex items-center justify-center gap-2 px-4 py-3 bg-loss/20 hover:bg-loss/30 text-loss rounded-md font-semibold transition-colors disabled:opacity-50"
          >
            <AlertTriangle className="w-5 h-5" />
            {emergencyStop.isPending ? 'Stopping...' : 'Emergency Stop'}
          </button>
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 overflow-auto">
        <div className="p-6">{children}</div>
      </main>
    </div>
  );
}
