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
  DEBUG: 'text-gray-500',
  INFO: 'text-profit',
  WARNING: 'text-warning',
  ERROR: 'text-loss',
  CRITICAL: 'text-loss',
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
  const levelColor = LEVEL_COLORS[line.level] || 'text-muted';

  return (
    <div className="flex gap-3 py-1 hover:bg-white/5 font-mono text-xs">
      <span className="text-muted w-20 flex-shrink-0">
        {formatTimestamp(line.timestamp)}
      </span>
      <span className={`w-16 flex-shrink-0 ${levelColor}`}>{line.level}</span>
      <span className="text-muted flex-shrink-0 w-32 truncate">{line.logger}</span>
      <span className="flex-1 break-all">{line.message}</span>
    </div>
  );
}

// Main Logs Page
export function Logs() {
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
    <div className="space-y-6 h-full flex flex-col">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Logs</h1>
          <p className="text-sm text-muted mt-1">Real-time log viewer</p>
        </div>
      </div>

      {/* Service Tabs */}
      <div className="flex items-center gap-2 border-b border-terminal pb-3">
        {SERVICES.map((service) => (
          <button
            key={service}
            onClick={() => setSelectedService(service)}
            className={`px-3 py-1.5 rounded text-sm transition-colors ${
              selectedService === service
                ? 'bg-profit/20 text-profit'
                : 'text-muted hover:text-foreground hover:bg-white/5'
            }`}
          >
            {service}
          </button>
        ))}
      </div>

      {/* Filters */}
      <div className="flex items-center gap-4">
        {/* Level Filter */}
        <select
          value={logLevel}
          onChange={(e) => setLogLevel(e.target.value)}
          className="px-3 py-2 bg-card border border-terminal rounded text-sm focus:outline-none focus:border-profit"
        >
          <option value="">All Levels</option>
          {LOG_LEVELS.map((level) => (
            <option key={level} value={level}>
              {level}
            </option>
          ))}
        </select>

        {/* Search */}
        <div className="relative flex-1 max-w-xs">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted" />
          <input
            type="text"
            placeholder="Search logs..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-10 pr-4 py-2 bg-card border border-terminal rounded text-sm focus:outline-none focus:border-profit"
          />
        </div>

        <div className="flex-1" />

        {/* Auto-scroll toggle */}
        <button
          onClick={() => setAutoScroll(!autoScroll)}
          className={`flex items-center gap-2 px-3 py-2 rounded text-sm ${
            autoScroll
              ? 'bg-profit/20 text-profit'
              : 'bg-card text-muted hover:text-foreground'
          }`}
        >
          <RefreshCw className={`w-4 h-4 ${autoScroll ? 'animate-spin' : ''}`} />
          Auto-scroll
        </button>

        {/* Download */}
        <button
          onClick={handleDownload}
          className="flex items-center gap-2 px-3 py-2 bg-card border border-terminal rounded text-sm hover:bg-white/5"
        >
          <Download className="w-4 h-4" />
          Export
        </button>

        {/* Refresh */}
        <button
          onClick={() => refetch()}
          className="flex items-center gap-2 px-3 py-2 bg-card border border-terminal rounded text-sm hover:bg-white/5"
        >
          <RefreshCw className="w-4 h-4" />
        </button>
      </div>

      {/* Log Viewer */}
      <div className="flex-1 min-h-0">
        <div
          ref={scrollRef}
          onScroll={handleScroll}
          className="h-[600px] bg-card border border-terminal rounded-md p-4 overflow-auto"
        >
          {isLoading ? (
            <div className="flex items-center justify-center h-full">
              <Activity className="w-6 h-6 animate-spin text-muted" />
            </div>
          ) : error ? (
            <div className="text-loss text-center py-4">
              Error loading logs: {(error as Error).message}
            </div>
          ) : data?.lines && data.lines.length > 0 ? (
            <div className="space-y-0">
              {data.lines.map((line, idx) => (
                <LogLineRow key={idx} line={line} />
              ))}
            </div>
          ) : (
            <div className="text-muted text-center py-4">
              No logs available for {selectedService}
            </div>
          )}
        </div>
      </div>

      {/* Footer info */}
      <div className="text-xs text-muted">
        Showing {data?.total_lines || 0} log lines from {selectedService}
      </div>
    </div>
  );
}
