#!/usr/bin/env python3
"""Test Hyperliquid connection and list subaccounts."""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from src.subaccount.manager import SubaccountManager
from src.config import load_config

config = load_config()._raw_config
manager = SubaccountManager(config)

print('Connessione OK!')
print(f'Master address: {manager.master_address}')

subs = manager.list_subaccounts()
print(f'\nSubaccount trovati: {len(subs)}')
for i, sub in enumerate(subs, 1):
    print(f'  {i}. {sub["name"]} - {sub["address"][:10]}...')
