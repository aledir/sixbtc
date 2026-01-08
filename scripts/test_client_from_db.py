#!/usr/bin/env python3
"""Test HyperliquidClient loading credentials from database."""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from src.config import load_config
from src.executor.hyperliquid_client import HyperliquidClient

config = load_config()

print("Creating HyperliquidClient (dry_run=True)...")
client = HyperliquidClient(config._raw_config, dry_run=True)

print(f"\nClient info:")
print(f"  dry_run: {client.dry_run}")
print(f"  subaccount_count: {client.subaccount_count}")
print(f"  configured subaccounts: {list(client._subaccount_credentials.keys())}")

print("\nCredentials loaded from DB:")
for sub_id, creds in client._subaccount_credentials.items():
    addr = creds['address']
    agent = creds['agent_address']
    print(f"  Subaccount {sub_id}: addr={addr[:10]}..., agent={agent[:10]}...")

print("\nHealth check:")
print(f"  {client.health_check()}")
