# Hyperliquid Integration Guide

This document explains how SixBTC integrates with Hyperliquid exchange.

## Rule #4b: WebSocket First

**Principle**: WebSocket for ALL data reads. REST only for actions.

```
DATA READS (WebSocket):
- Prices: allMids
- Account balance: webData2
- Positions: webData2
- Fills: userFills
- Ledger updates: userNonFundingLedgerUpdates

ACTIONS (REST):
- Place order
- Cancel order
- Set leverage
- Bootstrap (initial snapshot)
```

## WebSocket Channels

### Market Data

| Channel | Data | Update Frequency |
|---------|------|------------------|
| `allMids` | All coin mid prices | ~100ms |
| `candle` | OHLCV candlesticks | Per bar close |

### User Data

| Channel | Data | Triggered By |
|---------|------|--------------|
| `webData2` | Account state (balance, positions) | Any change |
| `userFills` | Trade executions | Order fill |
| `orderUpdates` | Order status changes | Order event |
| `userNonFundingLedgerUpdates` | Deposits/withdrawals | Capital event |

### Subscription Example

```python
# Subscribe to user data
await ws.send(json.dumps({
    "method": "subscribe",
    "subscription": {"type": "webData2", "user": address}
}))

# Subscribe to ledger updates (for balance reconciliation)
await ws.send(json.dumps({
    "method": "subscribe",
    "subscription": {"type": "userNonFundingLedgerUpdates", "user": address}
}))
```

## Rate Limiting

Hyperliquid rate limits: **1200 requests/minute** (20/second).

**Best Practices**:
1. Use WebSocket for data reads (no rate limit)
2. Batch REST operations when possible
3. Implement exponential backoff on 429 errors
4. Use `_wait_rate_limit()` helper in client

```python
def _wait_rate_limit(self, min_interval: float = 0.2):
    """Enforce minimum 200ms between REST calls."""
    elapsed = time.time() - self._last_request_time
    if elapsed < min_interval:
        time.sleep(min_interval - elapsed)
    self._last_request_time = time.time()
```

## Ledger Updates

### Event Types

| Type | Description | Direction |
|------|-------------|-----------|
| `deposit` | Funds deposited to perp account | IN |
| `withdraw` | Funds withdrawn from perp account | OUT |
| `internalTransfer` | Transfer between spot/perp | IN/OUT |
| `subAccountTransfer` | Transfer between subaccounts | IN/OUT |
| `send` | Inter-account transfers | IN/OUT |
| `liquidation` | Position liquidated | OUT |

### HTTP Endpoint

```python
# Get ledger updates via HTTP (for catchup)
response = self.info.post("/info", {
    "type": "userNonFundingLedgerUpdates",
    "user": address,
    "startTime": start_ms,
    "endTime": end_ms
})
```

### WebSocket Format

```json
{
    "channel": "userNonFundingLedgerUpdates",
    "data": {
        "time": 1700000000000,
        "hash": "0x123...",
        "delta": {
            "type": "deposit",
            "usdc": "100.0"
        }
    }
}
```

## Address Architecture

```
Master Wallet (HL_MASTER_ADDRESS)
    |
    +-- Subaccount 1 (agent wallet)
    |       Address: derived from master
    |
    +-- Subaccount 2 (agent wallet)
    |       Address: derived from master
    |
    +-- Subaccount N (agent wallet)
            Address: derived from master
```

### Address Resolution

WebSocket subscriptions use the master address. To determine which subaccount an event belongs to:

```python
def _resolve_subaccount_id(self, update: LedgerUpdate) -> Optional[int]:
    """Map event destination to subaccount ID."""
    delta = update.raw_data.get('delta', {})
    destination = delta.get('destination', '').lower()

    for sub_id, creds in self.client._subaccount_credentials.items():
        if creds.get('address', '').lower() == destination:
            return sub_id

    return None
```

## Error Handling

### WebSocket Disconnection

```python
async def _connection_loop(self):
    while self.running:
        try:
            async with websockets.connect(self.ws_url) as ws:
                await self._subscribe_all()
                await self._message_handler()
        except websockets.ConnectionClosed:
            logger.warning("WebSocket disconnected, reconnecting...")
            await asyncio.sleep(self.reconnect_delay)
            self.reconnect_delay = min(self.reconnect_delay * 2, 60)
```

### REST API Errors

```python
try:
    result = exchange.order(...)
    if result and result.get("status") == "ok":
        # Success
    else:
        # Check for error in statuses
        statuses = result.get("response", {}).get("data", {}).get("statuses", [])
        if statuses and "error" in statuses[0]:
            logger.error(f"Order rejected: {statuses[0]['error']}")
except Exception as e:
    logger.error(f"API error: {e}")
```

## Testing with Testnet

Set in config:

```yaml
hyperliquid:
  testnet: true  # Uses testnet API
```

Or via environment:

```bash
export HL_TESTNET=true
```

## Key Files

| File | Purpose |
|------|---------|
| `src/executor/hyperliquid_client.py` | REST API client |
| `src/data/hyperliquid_websocket.py` | WebSocket data provider |
| `src/executor/balance_reconciliation.py` | Ledger event processing |
| `src/executor/balance_sync.py` | Startup balance initialization |

## Common Issues

### "Subaccount not configured"

**Cause**: Missing agent wallet credentials in database.

**Solution**: Run `python scripts/setup_hyperliquid.py`

### "Rate limit exceeded"

**Cause**: Too many REST API calls.

**Solution**:
1. Use WebSocket for data reads
2. Increase `min_interval` in `_wait_rate_limit()`

### "WebSocket has no price"

**Cause**: WebSocket not yet received `allMids` update.

**Solution**: Falls back to REST automatically. Wait for WebSocket to initialize.

### "No deposit events found"

**Cause**: Subaccount was never actually funded on Hyperliquid.

**Solution**: Reconciliation service will zero out phantom capital.

## SDK Reference

- Hyperliquid Python SDK: https://github.com/hyperliquid-dex/hyperliquid-python-sdk
- API Documentation: https://hyperliquid.gitbook.io/
