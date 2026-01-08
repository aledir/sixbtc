#!/usr/bin/env python3
"""Test approve_agent API call to understand response format."""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from eth_account import Account
from hyperliquid.exchange import Exchange
from hyperliquid.utils import constants

# Load master wallet
master_key = os.environ.get('HL_MASTER_PRIVATE_KEY')
master_wallet = Account.from_key(master_key)

print(f"Master wallet: {master_wallet.address}")

# Create exchange client (no vault_address = master account)
exchange = Exchange(master_wallet, constants.MAINNET_API_URL)

# Try approve_agent
print("\nCalling approve_agent...")
try:
    result = exchange.approve_agent(name="test-debug-agent")
    print(f"\nResult type: {type(result)}")
    print(f"Result: {result}")

    if isinstance(result, tuple):
        print(f"\nTuple length: {len(result)}")
        for i, item in enumerate(result):
            print(f"  [{i}] type={type(item)}, value={item}")
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
