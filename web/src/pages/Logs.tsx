import { useState, useEffect, useRef } from 'react';
import { useLogs } from '../hooks/useApi';
import type { LogLine } from '../types';
import { Activity, Download, Search, RefreshCw } from 'lucide-react';

const SERVICES = [
  'generator',
  'backtester',
  'validator',
  'executor',
  'monitor',
  'scheduler',
  'data',
  'api',
];

const LOG_LEVELS = ['DEBUG', 'INFO', 'WARNING', 'ERROR'];

// Log level colors
const LEVEL_COLORS: Record<string, string> = {
  DEBUG: 'text-[var(--color-text-tertiary)]',
  INFO: 'text-[var(--color-profit)]',
  WARNING: 'text-[var(--color-warning)]',
  ERROR: 'text-[var(--color-loss)]',
  CRITICAL: 'text-[var(--color-loss)]',
};

function formatTimestamp(dateStr: string): string {
  const date = new Date(dateStr);
  return date.toLocaleTimeString('en-US', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  });
}

// Log Line Component
function LogLineRow({ line }: { line: LogLine }) {
  const levelColor = LEVEL_COLORS[line.level] || 'text-[var(--color-text-tertiary)]';

  return (
    <div className="flex gap-3 py-1 hover:bg-[var(--color-bg-secondary)] font-mono text-xs">
      <span className="text-[var(--color-text-tertiary)] w-16 sm:w-20 flex-shrink-0">
        {formatTimestamp(line.timestamp)}
      </span>
      <span className={`w-14 sm:w-16 flex-shrink-0 ${levelColor}`}>{line.level}</span>
      <span className="text-[var(--color-text-tertiary)] flex-shrink-0 w-24 sm:w-32 truncate hide-mobile">{line.logger}</span>
      <span className="flex-1 break-all text-[var(--color-text-secondary)]">{line.message}</span>
    </div>
  );
}

// Main Logs Page
export default function Logs() {
  const [selectedService, setSelectedService] = useState('executor');
  const [logLevel, setLogLevel] = useState('');
  const [search, setSearch] = useState('');
  const [autoScroll, setAutoScroll] = useState(true);
  const scrollRef = useRef<HTMLDivElement>(null);

  const { data, isLoading, error, refetch } = useLogs(selectedService, {
    lines: 500,
    level: logLevel || undefined,
    search: search || undefined,
  });

  // Auto-scroll to bottom when new logs arrive
  useEffect(() => {
    if (autoScroll && scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [data?.lines, autoScroll]);

  // Handle scroll - disable auto-scroll if user scrolls up
  const handleScroll = () => {
    if (scrollRef.current) {
      const { scrollTop, scrollHeight, clientHeight } = scrollRef.current;
      const isAtBottom = scrollHeight - scrollTop - clientHeight < 50;
      setAutoScroll(isAtBottom);
    }
  };

  // Download logs
  const handleDownload = () => {
    if (!data?.lines) return;

    const content = data.lines
      .map((l) => `${l.timestamp} ${l.level} ${l.logger}: ${l.message}`)
      .join('\n');

    const blob = new Blob([content], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${selectedService}-logs.txt`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="space-y-4 sm:space-y-6 h-full flex flex-col">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold text-[var(--color-text-primary)]">Logs</h1>
        <p className="text-sm text-[var(--color-text-secondary)] mt-1">Real-time log viewer</p>
      </div>

      {/* Service Tabs - Scrollable on mobile */}
      <div className="flex items-center gap-2 border-b border-[var(--color-border-primary)] pb-3 overflow-x-auto">
        {SERVICES.map((service) => (
          <button
            key={service}
            onClick={() => setSelectedService(service)}
            className={`px-3 py-1.5 rounded text-sm transition-colors whitespace-nowrap ${
              selectedService === service
                ? 'bg-[var(--color-accent)]/20 text-[var(--color-accent)]'
                : 'text-[var(--color-text-tertiary)] hover:text-[var(--color-text-primary)] hover:bg-[var(--color-bg-secondary)]'
            }`}
          >
            {service}
          </button>
        ))}
      </div>

      {/* Filters - Stack on mobile */}
      <div className="flex flex-col sm:flex-row items-stretch sm:items-center gap-3">
        <div className="flex gap-3">
          {/* Level Filter */}
          <select
            value={logLevel}
            onChange={(e) => setLogLevel(e.target.value)}
            className="input flex-1 sm:flex-none sm:w-auto"
          >
            <option value="">All Levels</option>
            {LOG_LEVELS.map((level) => (
              <option key={level} value={level}>
                {level}
              </option>
            ))}
          </select>

          {/* Search */}
          <div className="relative flex-1 sm:max-w-xs">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[var(--color-text-tertiary)]" />
            <input
              type="text"
              placeholder="Search logs..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="input pl-10"
            />
          </div>
        </div>

        <div className="flex-1 hide-mobile" />

        {/* Action Buttons */}
        <div className="flex gap-2">
          {/* Auto-scroll toggle */}
          <button
            onClick={() => setAutoScroll(!autoScroll)}
            className={`btn ${autoScroll ? 'btn-primary' : 'btn-ghost'} flex items-center gap-2`}
          >
            <RefreshCw className={`w-4 h-4 ${autoScroll ? 'animate-spin' : ''}`} />
            <span className="hide-mobile">Auto-scroll</span>
          </button>

          {/* Download */}
          <button
            onClick={handleDownload}
            className="btn btn-ghost flex items-center gap-2"
          >
            <Download className="w-4 h-4" />
            <span className="hide-mobile">Export</span>
          </button>

          {/* Refresh */}
          <button
            onClick={() => refetch()}
            className="btn btn-ghost"
          >
            <RefreshCw className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Log Viewer */}
      <div className="flex-1 min-h-0">
        <div
          ref={scrollRef}
          onScroll={handleScroll}
          className="h-[400px] sm:h-[600px] card p-4 overflow-auto"
        >
          {isLoading ? (
            <div className="flex items-center justify-center h-full">
              <Activity className="w-6 h-6 animate-spin text-[var(--color-text-tertiary)]" />
            </div>
          ) : error ? (
            <div className="text-[var(--color-loss)] text-center py-4">
              Error loading logs: {(error as Error).message}
            </div>
          ) : data?.lines && data.lines.length > 0 ? (
            <div className="space-y-0">
              {data.lines.map((line, idx) => (
                <LogLineRow key={idx} line={line} />
              ))}
            </div>
          ) : (
            <div className="text-[var(--color-text-tertiary)] text-center py-4">
              No logs available for {selectedService}
            </div>
          )}
        </div>
      </div>

      {/* Footer info */}
      <div className="text-xs text-[var(--color-text-tertiary)]">
        Showing {data?.total_lines || 0} log lines from {selectedService}
      </div>
    </div>
  );
}
