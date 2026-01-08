#!/usr/bin/env python3
"""Test approve_agent API call for a subaccount."""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from eth_account import Account
from hyperliquid.exchange import Exchange
from hyperliquid.info import Info
from hyperliquid.utils import constants

# Load master wallet
master_key = os.environ.get('HL_MASTER_PRIVATE_KEY')
master_address = os.environ.get('HL_MASTER_ADDRESS')
master_wallet = Account.from_key(master_key)

print(f"Master wallet: {master_wallet.address}")

# Get first subaccount
info = Info(constants.MAINNET_API_URL, skip_ws=True)
subaccounts = info.query_sub_accounts(master_address)
first_sub = subaccounts[0]
print(f"First subaccount: {first_sub['name']} - {first_sub['subAccountUser']}")

# Create exchange client WITH vault_address (for subaccount)
vault_address = first_sub['subAccountUser']
exchange = Exchange(master_wallet, constants.MAINNET_API_URL, vault_address=vault_address)

# Try approve_agent for subaccount
print("\nCalling approve_agent for subaccount...")
try:
    result = exchange.approve_agent(name="test-sub-agent")
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
