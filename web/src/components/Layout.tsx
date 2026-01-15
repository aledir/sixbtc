import { NavLink, Outlet, useLocation } from 'react-router-dom';
import {
  LayoutDashboard,
  LineChart,
  TrendingUp,
  Activity,
  Settings,
  Sun,
  Moon,
  Menu,
  X,
  Trophy,
  FileCode,
  CheckCircle,
  Clock,
  ScrollText,
} from 'lucide-react';
import { useStatus } from '../hooks/useApi';
import { useTheme } from '../contexts/ThemeContext';
import { useState } from 'react';

// Main navigation items (shown in bottom bar on mobile)
const mainNavItems = [
  { to: '/', icon: LayoutDashboard, label: 'Overview' },
  { to: '/trading', icon: LineChart, label: 'Trading' },
  { to: '/strategies', icon: TrendingUp, label: 'Strategies' },
  { to: '/pipeline', icon: Activity, label: 'Pipeline' },
  { to: '/settings', icon: Settings, label: 'More' },
];

// All navigation items for desktop sidebar and mobile menu
const allNavItems = [
  { to: '/', icon: LayoutDashboard, label: 'Overview' },
  { to: '/trading', icon: LineChart, label: 'Trading' },
  { to: '/strategies', icon: TrendingUp, label: 'Strategies' },
  { to: '/pipeline', icon: Activity, label: 'Pipeline' },
  { to: '/rankings', icon: Trophy, label: 'Rankings' },
  { to: '/validation', icon: CheckCircle, label: 'Validation' },
  { to: '/templates', icon: FileCode, label: 'Templates' },
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

// Theme toggle button
function ThemeToggle() {
  const { theme, toggleTheme } = useTheme();

  return (
    <button
      onClick={toggleTheme}
      className="btn btn-ghost p-2"
      aria-label={`Switch to ${theme === 'light' ? 'dark' : 'light'} mode`}
    >
      {theme === 'light' ? <Moon size={20} /> : <Sun size={20} />}
    </button>
  );
}

// System status indicator
function StatusIndicator() {
  const { data: status, isError } = useStatus();
  const servicesOk = status?.services.every((s) => s.status === 'RUNNING') ?? false;

  return (
    <div className="flex items-center gap-2 text-sm">
      <span
        className={`w-2 h-2 rounded-full ${
          isError
            ? 'bg-[var(--color-loss)]'
            : servicesOk
              ? 'bg-[var(--color-profit)] animate-pulse-slow'
              : 'bg-[var(--color-warning)]'
        }`}
      />
      <span className="text-[var(--color-text-secondary)] hide-mobile">
        {isError ? 'Offline' : servicesOk ? 'Online' : 'Issues'}
      </span>
      {status && (
        <span className="text-[var(--color-text-tertiary)] hide-mobile">
          {formatUptime(status.uptime_seconds)}
        </span>
      )}
    </div>
  );
}

// Mobile menu overlay
function MobileMenu({ isOpen, onClose }: { isOpen: boolean; onClose: () => void }) {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 md:hidden">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/50 backdrop-blur-sm"
        onClick={onClose}
      />

      {/* Menu panel */}
      <div className="absolute right-0 top-0 bottom-0 w-72 bg-[var(--color-bg-elevated)] shadow-lg flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-[var(--color-border-primary)]">
          <span className="font-semibold">Menu</span>
          <button onClick={onClose} className="btn btn-ghost p-2">
            <X size={20} />
          </button>
        </div>

        {/* Nav items */}
        <nav className="flex-1 p-2 overflow-y-auto">
          {allNavItems.map(({ to, icon: Icon, label }) => (
            <NavLink
              key={to}
              to={to}
              end={to === '/'}
              onClick={onClose}
              className={({ isActive }) =>
                `flex items-center gap-3 px-4 py-3 rounded-lg text-sm transition-colors ${
                  isActive
                    ? 'bg-[var(--color-accent-muted)] text-[var(--color-accent)]'
                    : 'text-[var(--color-text-secondary)] hover:bg-[var(--color-bg-tertiary)]'
                }`
              }
            >
              <Icon size={20} />
              {label}
            </NavLink>
          ))}
        </nav>

        {/* Footer */}
        <div className="p-4 border-t border-[var(--color-border-primary)]">
          <div className="flex items-center justify-between">
            <StatusIndicator />
            <ThemeToggle />
          </div>
        </div>
      </div>
    </div>
  );
}

// Desktop sidebar
function DesktopSidebar() {
  return (
    <aside className="hidden md:flex w-60 flex-col bg-[var(--color-bg-elevated)] border-r border-[var(--color-border-primary)]">
      {/* Logo */}
      <div className="p-5 border-b border-[var(--color-border-primary)]">
        <h1 className="text-xl font-bold text-[var(--color-accent)]">SixBTC</h1>
        <p className="text-xs text-[var(--color-text-tertiary)] mt-1">Control Center</p>
      </div>

      {/* Navigation */}
      <nav className="flex-1 p-3 overflow-y-auto">
        {allNavItems.map(({ to, icon: Icon, label }) => (
          <NavLink
            key={to}
            to={to}
            end={to === '/'}
            className={({ isActive }) =>
              `flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-colors mb-1 ${
                isActive
                  ? 'bg-[var(--color-accent-muted)] text-[var(--color-accent)] font-medium'
                  : 'text-[var(--color-text-secondary)] hover:bg-[var(--color-bg-tertiary)] hover:text-[var(--color-text-primary)]'
              }`
            }
          >
            <Icon size={18} />
            {label}
          </NavLink>
        ))}
      </nav>

      {/* Footer */}
      <div className="p-4 border-t border-[var(--color-border-primary)]">
        <div className="flex items-center justify-between">
          <StatusIndicator />
          <ThemeToggle />
        </div>
      </div>
    </aside>
  );
}

// Mobile bottom tab bar
function MobileTabBar({ onMenuOpen }: { onMenuOpen: () => void }) {
  const location = useLocation();

  // Check if we're on one of the "More" pages
  const isMorePage = ['/rankings', '/validation', '/templates', '/system-tasks', '/logs', '/settings'].includes(
    location.pathname
  );

  return (
    <nav className="md:hidden fixed bottom-0 left-0 right-0 bg-[var(--color-bg-elevated)] border-t border-[var(--color-border-primary)] safe-bottom z-40">
      <div className="flex items-center justify-around h-16">
        {mainNavItems.map(({ to, icon: Icon, label }) => {
          // Special handling for "More" button
          if (label === 'More') {
            return (
              <button
                key="more"
                onClick={onMenuOpen}
                className={`flex flex-col items-center justify-center gap-1 flex-1 h-full transition-colors ${
                  isMorePage
                    ? 'text-[var(--color-accent)]'
                    : 'text-[var(--color-text-tertiary)]'
                }`}
              >
                <Menu size={22} />
                <span className="text-[10px] font-medium">{label}</span>
              </button>
            );
          }

          return (
            <NavLink
              key={to}
              to={to}
              end={to === '/'}
              className={({ isActive }) =>
                `flex flex-col items-center justify-center gap-1 flex-1 h-full transition-colors ${
                  isActive
                    ? 'text-[var(--color-accent)]'
                    : 'text-[var(--color-text-tertiary)]'
                }`
              }
            >
              <Icon size={22} />
              <span className="text-[10px] font-medium">{label}</span>
            </NavLink>
          );
        })}
      </div>
    </nav>
  );
}

// Mobile header
function MobileHeader() {
  return (
    <header className="md:hidden sticky top-0 z-30 bg-[var(--color-bg-elevated)] border-b border-[var(--color-border-primary)]">
      <div className="flex items-center justify-between px-4 h-14">
        <h1 className="text-lg font-bold text-[var(--color-accent)]">SixBTC</h1>
        <div className="flex items-center gap-2">
          <StatusIndicator />
          <ThemeToggle />
        </div>
      </div>
    </header>
  );
}

export default function Layout() {
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);
  const { data: status } = useStatus();
  const hasAlerts = (status?.alerts.length ?? 0) > 0;

  return (
    <div className="flex min-h-screen min-h-[100dvh] bg-[var(--color-bg-primary)]">
      {/* Desktop Sidebar */}
      <DesktopSidebar />

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Mobile Header */}
        <MobileHeader />

        {/* Alert Banner */}
        {hasAlerts && (
          <div className="bg-[var(--color-warning-bg)] border-b border-[var(--color-warning)]/20 px-4 py-3">
            <div className="flex items-center gap-2 text-[var(--color-warning)] text-sm">
              <span className="font-medium">{status?.alerts[0]?.message}</span>
              {(status?.alerts.length ?? 0) > 1 && (
                <span className="badge badge-warning">
                  +{(status?.alerts.length ?? 1) - 1}
                </span>
              )}
            </div>
          </div>
        )}

        {/* Page Content */}
        <main className="flex-1 overflow-auto p-[var(--spacing-page)] pb-24 md:pb-[var(--spacing-page)]">
          <Outlet />
        </main>
      </div>

      {/* Mobile Bottom Tab Bar */}
      <MobileTabBar onMenuOpen={() => setIsMobileMenuOpen(true)} />

      {/* Mobile Menu Overlay */}
      <MobileMenu
        isOpen={isMobileMenuOpen}
        onClose={() => setIsMobileMenuOpen(false)}
      />
    </div>
  );
}
