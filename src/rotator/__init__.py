"""
ROTATOR Module - Strategy Selection and Deployment

Single Responsibility: Rotate strategies from ACTIVE pool to LIVE

Components:
- Selector: Select top N strategies from ACTIVE pool with diversification
- Deployer: Deploy selected strategies to Hyperliquid subaccounts

Flow:
1. Check for free LIVE slots (subaccounts without strategy)
2. Select top candidates from ACTIVE pool (score >= 50, diversified)
3. Deploy to subaccounts and update status to LIVE
"""

from src.rotator.selector import StrategySelector
from src.rotator.deployer import StrategyDeployer

__all__ = ['StrategySelector', 'StrategyDeployer']
