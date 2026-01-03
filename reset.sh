#!/bin/bash
# Reset all logs, strategies, and database tables
# Usage: ./reset.sh

set -e

echo "Resetting SixBTC..."

# Clear logs and recreate with correct permissions
rm -f logs/*.log logs/*.log.* 2>/dev/null || true
touch logs/generator.log logs/validator.log logs/backtester.log logs/classifier.log \
      logs/executor.log logs/subaccount.log logs/monitor.log logs/scheduler.log \
      logs/api.log logs/frontend.log
echo "- Logs cleared"

# Clear pending strategies
rm -rf strategies/pending/* 2>/dev/null || true
echo "- Pending strategies cleared"

# Reset database
PGPASSWORD="sixbtc_dev_password_2025" psql -h localhost -p 5435 -U sixbtc -d sixbtc -q -c "
TRUNCATE TABLE backtest_results CASCADE;
TRUNCATE TABLE strategies CASCADE;
TRUNCATE TABLE strategy_templates CASCADE;
" 2>/dev/null
echo "- Database reset"

echo "Done"
