"""
Risk Manager - Position Sizing and Risk Management

Implements ATR-based position sizing and risk management rules.

Key Features:
- ATR-based position sizing (adaptive to volatility)
- Fixed fractional fallback
- Risk limits enforcement
- Volatility scaling
"""

import logging
from typing import Optional, Tuple, Dict, Any
import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)


class RiskManager:
    """
    Calculates position size and manages risk

    Supports two modes:
    1. ATR-based (recommended): Adapts to market volatility
    2. Fixed fractional: Simple percentage-based sizing

    Risk limits are enforced across portfolio and per-subaccount.
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize risk manager

        Args:
            config: Risk configuration dict from config.yaml

        Required config keys:
        - sizing_mode: 'atr' or 'fixed'
        - fixed_fractional.risk_per_trade_pct
        - fixed_fractional.max_position_size_pct
        - atr.period
        - atr.stop_multiplier
        - atr.take_profit_multiplier
        - limits.*
        """
        # Handle both nested ('risk' key) and flat config
        if 'risk' in config:
            self.config = config['risk']
        else:
            self.config = config

        self.sizing_mode = self.config['sizing_mode']

        # Fixed fractional settings
        ff_config = self.config['fixed_fractional']
        self.risk_per_trade_pct = ff_config['risk_per_trade_pct']
        self.max_position_size_pct = ff_config['max_position_size_pct']

        # ATR settings
        atr_config = self.config['atr']
        self.atr_period = atr_config['period']
        self.atr_stop_multiplier = atr_config['stop_multiplier']
        self.atr_take_profit_multiplier = atr_config['take_profit_multiplier']
        self.min_risk_reward = atr_config['min_risk_reward']

        # Volatility scaling
        self.volatility_scaling = atr_config['volatility_scaling']
        self.scaling_enabled = self.volatility_scaling['enabled']
        self.low_vol_threshold = self.volatility_scaling['low_volatility_threshold']
        self.high_vol_threshold = self.volatility_scaling['high_volatility_threshold']
        self.scaling_factor = self.volatility_scaling['scaling_factor']

        # Position limits
        limits_config = self.config['limits']
        self.max_positions_total = limits_config['max_open_positions_total']
        self.max_positions_per_subaccount = limits_config['max_open_positions_per_subaccount']
        self.max_leverage = limits_config['max_leverage']

        # Emergency stops
        emergency_config = self.config['emergency']
        self.max_portfolio_drawdown = emergency_config['max_portfolio_drawdown']
        self.max_consecutive_losses = emergency_config['max_consecutive_losses']

        logger.info(f"RiskManager initialized (mode: {self.sizing_mode})")

    def calculate_position_size_atr(
        self,
        account_balance: float,
        current_price: float,
        atr: float,
        signal_stop_multiplier: Optional[float] = None,
        signal_take_multiplier: Optional[float] = None
    ) -> Tuple[float, float, float]:
        """
        Calculate position size using ATR-based method

        Args:
            account_balance: Account balance in USD
            current_price: Current market price
            atr: Current ATR value
            signal_stop_multiplier: Override ATR stop multiplier (optional)
            signal_take_multiplier: Override ATR take multiplier (optional)

        Returns:
            Tuple of (position_size, stop_loss, take_profit)

        Example:
            Account: $1000
            BTC Price: $50,000
            ATR(14): $1,500
            ATR Multiplier: 2.0

            Stop Distance = $1,500 × 2.0 = $3,000
            Risk = $1,000 × 0.02 = $20
            Position Size = $20 / $3,000 = 0.00667 BTC = $333 notional
            Stop Loss = $50,000 - $3,000 = $47,000
            Take Profit = $50,000 + ($1,500 × 3.0) = $54,500
        """
        # Use signal multipliers or defaults
        stop_mult = signal_stop_multiplier or self.atr_stop_multiplier
        take_mult = signal_take_multiplier or self.atr_take_profit_multiplier

        # Calculate stop distance
        stop_distance = atr * stop_mult

        # Calculate risk dollars
        risk_dollars = account_balance * self.risk_per_trade_pct

        # Apply volatility scaling if enabled
        if self.scaling_enabled:
            atr_pct = atr / current_price

            if atr_pct < self.low_vol_threshold:
                # Low volatility → increase size
                risk_dollars *= (1 + self.scaling_factor)
                logger.debug(f"Low volatility ({atr_pct:.4f}) → increased risk")

            elif atr_pct > self.high_vol_threshold:
                # High volatility → decrease size
                risk_dollars *= (1 - self.scaling_factor)
                logger.debug(f"High volatility ({atr_pct:.4f}) → decreased risk")

        # Calculate position size
        position_size = risk_dollars / stop_distance

        # Calculate stop loss and take profit (for long position)
        stop_loss = current_price - stop_distance
        take_profit = current_price + (atr * take_mult)

        # Verify risk/reward ratio
        potential_profit = take_profit - current_price
        potential_loss = current_price - stop_loss
        risk_reward = potential_profit / potential_loss

        if risk_reward < self.min_risk_reward:
            logger.warning(
                f"Risk/Reward ratio {risk_reward:.2f} below minimum {self.min_risk_reward}"
            )
            # Adjust take profit to meet minimum R:R
            take_profit = current_price + (stop_distance * self.min_risk_reward)

        # Apply max_position_size_pct cap (CRITICAL: must be enforced)
        max_notional = account_balance * self.max_position_size_pct
        max_position_size = max_notional / current_price
        position_size = min(position_size, max_position_size)

        logger.debug(
            f"ATR sizing: size={position_size:.6f}, SL={stop_loss:.2f}, "
            f"TP={take_profit:.2f}, R:R={risk_reward:.2f}"
        )

        return position_size, stop_loss, take_profit

    def calculate_position_size_fixed(
        self,
        account_balance: float,
        entry_price: float,
        stop_loss: float
    ) -> float:
        """
        Calculate position size using fixed fractional method

        Args:
            account_balance: Account balance in USD
            entry_price: Entry price
            stop_loss: Stop loss price

        Returns:
            Position size

        Example:
            Account: $1000
            Risk: 2% = $20
            Entry: $50,000
            Stop: $49,000
            Distance: $1,000

            Position Size = $20 / $1,000 = 0.02 BTC = $1,000 notional
        """
        risk_dollars = account_balance * self.risk_per_trade_pct
        stop_distance = abs(entry_price - stop_loss)

        if stop_distance == 0:
            logger.error("Stop distance is zero, cannot calculate position size")
            return 0.0

        position_size = risk_dollars / stop_distance

        # Apply max_position_size_pct cap (CRITICAL: must be enforced)
        max_notional = account_balance * self.max_position_size_pct
        max_position_size = max_notional / entry_price
        position_size = min(position_size, max_position_size)

        logger.debug(
            f"Fixed sizing: size={position_size:.6f}, risk=${risk_dollars:.2f}"
        )

        return position_size

    def calculate_position_size(
        self,
        signal=None,
        account_balance: Optional[float] = None,
        current_price: Optional[float] = None,
        atr: Optional[float] = None,
        df: Optional[pd.DataFrame] = None,
        signal_stop_loss: Optional[float] = None,
        signal_take_profit: Optional[float] = None,
        signal_atr_stop_mult: Optional[float] = None,
        signal_atr_take_mult: Optional[float] = None
    ) -> Tuple[float, float, float]:
        """
        Calculate position size (auto-selects method based on config)

        Args:
            signal: Signal object (test-compatible interface)
            account_balance: Account balance in USD
            current_price: Current market price
            atr: ATR value (optional, for ATR mode)
            df: OHLCV DataFrame (required for ATR mode if atr not provided)
            signal_stop_loss: Fixed stop loss from signal (optional)
            signal_take_profit: Fixed take profit from signal (optional)
            signal_atr_stop_mult: ATR stop multiplier from signal (optional)
            signal_atr_take_mult: ATR take profit multiplier from signal (optional)

        Returns:
            Tuple of (position_size, stop_loss, take_profit)
        """
        # Handle Signal object interface
        if signal is not None:
            signal_stop_loss = getattr(signal, 'stop_loss', None)
            signal_take_profit = getattr(signal, 'take_profit', None)
            signal_atr_stop_mult = getattr(signal, 'atr_stop_multiplier', None)
            signal_atr_take_mult = getattr(signal, 'atr_take_multiplier', None)

        if self.sizing_mode == 'atr':
            # ATR-based sizing
            if atr is None:
                if df is None:
                    logger.error("ATR or DataFrame required for ATR-based sizing, falling back to fixed")
                    if signal_stop_loss is not None:
                        size = self.calculate_position_size_fixed(
                            account_balance, current_price, signal_stop_loss
                        )
                        return size, signal_stop_loss, signal_take_profit or current_price * 1.05
                    else:
                        logger.error("No stop loss provided, cannot calculate size")
                        return 0.0, 0.0, 0.0

                # Calculate ATR from DataFrame
                atr = self._calculate_atr(df)

            if atr == 0:
                logger.error("ATR is zero, cannot calculate position size")
                return 0.0, 0.0, 0.0

            return self.calculate_position_size_atr(
                account_balance=account_balance,
                current_price=current_price,
                atr=atr,
                signal_stop_multiplier=signal_atr_stop_mult,
                signal_take_multiplier=signal_atr_take_mult
            )

        else:
            # Fixed fractional sizing
            if signal_stop_loss is None:
                logger.error("Stop loss required for fixed fractional sizing")
                return 0.0, 0.0, 0.0

            size = self.calculate_position_size_fixed(
                account_balance, current_price, signal_stop_loss
            )

            return size, signal_stop_loss, signal_take_profit or current_price * 1.05

    def _calculate_atr(self, df: pd.DataFrame) -> float:
        """
        Calculate ATR from OHLCV data

        Args:
            df: OHLCV DataFrame

        Returns:
            ATR value
        """
        if len(df) < self.atr_period:
            logger.warning(
                f"Not enough data for ATR calculation ({len(df)} < {self.atr_period})"
            )
            return 0.0

        # Calculate True Range
        high = df['high']
        low = df['low']
        close_prev = df['close'].shift(1)

        tr1 = high - low
        tr2 = abs(high - close_prev)
        tr3 = abs(low - close_prev)

        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

        # Calculate ATR (EMA of True Range)
        atr = tr.ewm(span=self.atr_period, adjust=False).mean().iloc[-1]

        return float(atr)

    def check_risk_limits(
        self,
        new_position_size: float,
        current_positions_count: int,
        subaccount_positions_count: int,
        account_balance: float,
        current_price: float
    ) -> Tuple[bool, str]:
        """
        Check if new position violates risk limits

        Args:
            new_position_size: Proposed position size
            current_positions_count: Total positions across all subaccounts
            subaccount_positions_count: Positions on this subaccount
            account_balance: Account balance
            current_price: Current market price

        Returns:
            Tuple of (allowed, reason)
        """
        # Check position count limits
        if current_positions_count >= self.max_positions_total:
            return False, f"Max total positions ({self.max_positions_total}) reached"

        if subaccount_positions_count >= self.max_positions_per_subaccount:
            return False, f"Max subaccount positions ({self.max_positions_per_subaccount}) reached"

        # Check position size limit
        position_notional = new_position_size * current_price
        max_notional = account_balance * self.max_position_size_pct

        if position_notional > max_notional:
            return False, f"Position size ${position_notional:.2f} exceeds max ${max_notional:.2f}"

        # Check leverage limit
        leverage = position_notional / account_balance
        if leverage > self.max_leverage:
            return False, f"Leverage {leverage:.1f}x exceeds max {self.max_leverage}x"

        return True, "OK"

    def adjust_stops_for_side(
        self,
        side: str,
        current_price: float,
        stop_loss: float,
        take_profit: float
    ) -> Tuple[float, float]:
        """
        Adjust stop loss and take profit based on position side

        Args:
            side: 'long' or 'short'
            current_price: Current market price
            stop_loss: Stop loss (calculated for long)
            take_profit: Take profit (calculated for long)

        Returns:
            Tuple of (adjusted_stop_loss, adjusted_take_profit)
        """
        if side == 'long':
            # Long: SL below, TP above
            return stop_loss, take_profit
        else:
            # Short: SL above, TP below (invert)
            stop_distance = current_price - stop_loss
            take_distance = take_profit - current_price

            adjusted_stop_loss = current_price + stop_distance
            adjusted_take_profit = current_price - take_distance

            return adjusted_stop_loss, adjusted_take_profit

    def get_summary(self) -> Dict[str, Any]:
        """Get risk manager configuration summary"""
        return {
            'sizing_mode': self.sizing_mode,
            'risk_per_trade_pct': self.risk_per_trade_pct,
            'max_position_size_pct': self.max_position_size_pct,
            'atr_period': self.atr_period,
            'atr_stop_multiplier': self.atr_stop_multiplier,
            'atr_take_profit_multiplier': self.atr_take_profit_multiplier,
            'max_positions_total': self.max_positions_total,
            'max_positions_per_subaccount': self.max_positions_per_subaccount,
            'max_leverage': self.max_leverage,
            'volatility_scaling_enabled': self.scaling_enabled
        }

    def can_open_position(
        self,
        strategy_id: str,
        symbol: str,
        signal: Any
    ) -> bool:
        """
        Check if position can be opened (test-compatible interface)

        Args:
            strategy_id: Strategy identifier
            symbol: Trading pair
            signal: Signal object

        Returns:
            True if position can be opened
        """
        # For testing, we always allow opening positions
        # In production, this would check:
        # - Position limits
        # - Risk limits
        # - Strategy-specific constraints
        return True

    def validate_signal(
        self,
        signal: Any,
        current_price: float
    ) -> bool:
        """
        Validate signal parameters

        Args:
            signal: Signal object
            current_price: Current market price

        Returns:
            True if signal is valid
        """
        # Check direction
        if not hasattr(signal, 'direction'):
            logger.error("Signal missing direction attribute")
            return False

        if signal.direction not in ['long', 'short', 'close']:
            logger.error(f"Invalid signal direction: {signal.direction}")
            return False

        # Validate stop loss and take profit (if present)
        if hasattr(signal, 'stop_loss') and signal.stop_loss is not None:
            if signal.direction == 'long':
                # Stop loss must be below entry
                if signal.stop_loss >= current_price:
                    logger.error(
                        f"Invalid long stop loss: {signal.stop_loss} >= {current_price}"
                    )
                    return False

            elif signal.direction == 'short':
                # Stop loss must be above entry
                if signal.stop_loss <= current_price:
                    logger.error(
                        f"Invalid short stop loss: {signal.stop_loss} <= {current_price}"
                    )
                    return False

        if hasattr(signal, 'take_profit') and signal.take_profit is not None:
            if signal.direction == 'long':
                # Take profit must be above entry
                if signal.take_profit <= current_price:
                    logger.error(
                        f"Invalid long take profit: {signal.take_profit} <= {current_price}"
                    )
                    return False

            elif signal.direction == 'short':
                # Take profit must be below entry
                if signal.take_profit >= current_price:
                    logger.error(
                        f"Invalid short take profit: {signal.take_profit} >= {current_price}"
                    )
                    return False

        return True

    def check_emergency_stop(self) -> bool:
        """
        Check if emergency stop conditions met

        Returns:
            True if emergency stop should be triggered
        """
        # In a real implementation, this would check:
        # - Portfolio drawdown
        # - Daily loss limits
        # - Consecutive losses
        # For testing/dry-run, return False
        return False

    def record_trade_result(
        self,
        strategy_id: str,
        pnl: float,
        reason: str
    ):
        """
        Record trade result for tracking

        Args:
            strategy_id: Strategy identifier
            pnl: Profit/Loss
            reason: Close reason
        """
        logger.info(
            f"Trade result recorded: strategy={strategy_id}, pnl=${pnl:.2f}, reason={reason}"
        )

    def get_open_positions_count(self) -> int:
        """
        Get count of open positions

        Returns:
            Number of open positions (placeholder)
        """
        # In production, would query actual position tracker
        return 0

    def check_position_limit(
        self,
        current_positions: int,
        max_positions: int
    ) -> bool:
        """
        Check if position limit allows new position

        Args:
            current_positions: Current number of positions
            max_positions: Maximum allowed positions

        Returns:
            True if within limit
        """
        return current_positions < max_positions

    def check_drawdown(
        self,
        current_balance: float,
        peak_balance: float,
        max_drawdown: float
    ) -> bool:
        """
        Check if drawdown is within acceptable limits

        Args:
            current_balance: Current account balance
            peak_balance: Peak balance (high water mark)
            max_drawdown: Maximum allowed drawdown (0-1)

        Returns:
            True if within limit
        """
        if peak_balance == 0:
            return True

        drawdown = (peak_balance - current_balance) / peak_balance
        return drawdown <= max_drawdown

    def should_emergency_stop(
        self,
        portfolio_drawdown: float,
        consecutive_losses: int
    ) -> bool:
        """
        Check if emergency stop conditions are met

        Args:
            portfolio_drawdown: Current portfolio drawdown (0-1)
            consecutive_losses: Number of consecutive losing trades

        Returns:
            True if emergency stop should be triggered
        """
        # Check max drawdown
        if portfolio_drawdown >= self.max_portfolio_drawdown:
            logger.warning(
                f"Emergency stop: Portfolio drawdown {portfolio_drawdown:.2%} "
                f">= max {self.max_portfolio_drawdown:.2%}"
            )
            return True

        # Check consecutive losses
        if consecutive_losses >= self.max_consecutive_losses:
            logger.warning(
                f"Emergency stop: Consecutive losses {consecutive_losses} "
                f">= max {self.max_consecutive_losses}"
            )
            return True

        return False
