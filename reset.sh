#!/bin/bash
# Reset all logs, strategies, and database tables
# Usage: ./reset.sh

set -e

echo "Resetting SixBTC..."

# Stop all services first
echo "- Stopping services..."
supervisorctl stop sixbtc:* 2>/dev/null || true

# Clear ALL logs and recreate empty with correct permissions
rm -f logs/*.log logs/*.log.* 2>/dev/null || true
touch logs/api.log logs/backtester.log logs/classifier.log logs/executor.log \
      logs/frontend.log logs/generator.log logs/metrics.log logs/monitor.log \
      logs/rotator.log logs/scheduler.log logs/subaccount.log logs/validator.log
echo "- Logs cleared and recreated"

# Clear pending strategies
rm -rf strategies/pending/* 2>/dev/null || true
echo "- Pending strategies cleared"

# Reset database - truncate ALL relevant tables
PGPASSWORD="sixbtc_dev_password_2025" psql -h localhost -p 5435 -U sixbtc -d sixbtc -q -c "
TRUNCATE TABLE backtest_results CASCADE;
TRUNCATE TABLE strategies CASCADE;
TRUNCATE TABLE strategy_templates CASCADE;
TRUNCATE TABLE pipeline_metrics_snapshots CASCADE;
" 2>/dev/null
echo "- Database reset"

# Start all services
echo "- Starting services..."
supervisorctl start sixbtc:*

# Show status
echo ""
echo "Service status:"
supervisorctl status sixbtc:*

echo ""
echo "Done"
