#!/usr/bin/env python3
"""
Insert Manual Strategy into Database

Reads a manual strategy file and inserts it into the database with status GENERATED.
The strategy will then go through the normal pipeline (validation, backtest, etc.).

Usage:
    python scripts/manual_strategy/insert_strategy.py strategies/manual/ManStrat_MOM_a1b2c3d4.py

The script will:
1. Validate the file name format (ManStrat_<TYPE>_<hash>.py)
2. Validate the class name matches the file name
3. Extract strategy type from the name
4. Extract timeframe from docstring or default to '15m'
5. Insert into database with status='GENERATED', generation_mode='manual'
"""

import argparse
import re
import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.database import get_session, Strategy
from src.utils import get_logger

logger = get_logger(__name__)

# Valid strategy types
VALID_TYPES = {'MOM', 'REV', 'TRN', 'BRE', 'SCA', 'VOL'}

# Name pattern: ManStrat_<TYPE>_<hash>
NAME_PATTERN = re.compile(r'^ManStrat_([A-Z]{3})_([a-f0-9]{8})$')


def validate_file_name(file_path: Path) -> tuple[str, str, str]:
    """
    Validate file name format and extract components.

    Args:
        file_path: Path to the strategy file

    Returns:
        (full_name, strategy_type, hash) tuple

    Raises:
        ValueError: If file name format is invalid
    """
    file_name = file_path.stem  # Remove .py extension

    match = NAME_PATTERN.match(file_name)
    if not match:
        raise ValueError(
            f"Invalid file name format: {file_name}\n"
            f"Expected: ManStrat_<TYPE>_<8char_hash>.py\n"
            f"Example: ManStrat_MOM_a1b2c3d4.py"
        )

    strategy_type = match.group(1)
    strategy_hash = match.group(2)

    if strategy_type not in VALID_TYPES:
        raise ValueError(
            f"Invalid strategy type: {strategy_type}\n"
            f"Valid types: {', '.join(sorted(VALID_TYPES))}"
        )

    return file_name, strategy_type, strategy_hash


def validate_class_name(code: str, expected_name: str) -> None:
    """
    Validate that the class name in the code matches the file name.

    Args:
        code: Strategy code
        expected_name: Expected class name (from file name)

    Raises:
        ValueError: If class name doesn't match
    """
    class_pattern = re.compile(rf'class\s+({expected_name})\s*\(')
    match = class_pattern.search(code)

    if not match:
        # Try to find any class name to give helpful error
        any_class = re.search(r'class\s+(ManStrat_\w+)\s*\(', code)
        if any_class:
            found_name = any_class.group(1)
            raise ValueError(
                f"Class name mismatch!\n"
                f"Expected: {expected_name}\n"
                f"Found: {found_name}\n"
                f"The class name must match the file name."
            )
        else:
            raise ValueError(
                f"No ManStrat class found in code.\n"
                f"Expected class: {expected_name}"
            )


def extract_timeframe(code: str) -> str:
    """
    Extract timeframe from strategy docstring.

    Looks for patterns like:
    - Timeframe: 15m
    - timeframe = '15m'

    Args:
        code: Strategy code

    Returns:
        Timeframe string or '15m' as default
    """
    # Try to find in docstring
    tf_pattern = re.compile(r'[Tt]imeframe[:\s]+([0-9]+[mhd])', re.IGNORECASE)
    match = tf_pattern.search(code)

    if match:
        return match.group(1).lower()

    # Default to 15m
    return '15m'


def check_duplicate(session, name: str) -> bool:
    """Check if a strategy with this name already exists."""
    existing = session.query(Strategy).filter(Strategy.name == name).first()
    return existing is not None


def insert_strategy(file_path: Path, force: bool = False) -> None:
    """
    Insert a manual strategy into the database.

    Args:
        file_path: Path to the strategy file
        force: If True, overwrite existing strategy with same name
    """
    # Validate file exists
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    # Validate file name format
    strategy_name, strategy_type, strategy_hash = validate_file_name(file_path)

    # Read code
    code = file_path.read_text()

    # Validate class name matches file name
    validate_class_name(code, strategy_name)

    # Extract timeframe
    timeframe = extract_timeframe(code)

    # Insert into database
    with get_session() as session:
        # Check for duplicate
        if check_duplicate(session, strategy_name):
            if force:
                logger.warning(f"Deleting existing strategy: {strategy_name}")
                session.query(Strategy).filter(Strategy.name == strategy_name).delete()
                session.commit()
            else:
                raise ValueError(
                    f"Strategy already exists: {strategy_name}\n"
                    f"Use --force to overwrite."
                )

        # Create strategy record
        strategy = Strategy(
            name=strategy_name,
            strategy_type=strategy_type,
            timeframe=timeframe,
            status='GENERATED',
            code=code,
            generation_mode='manual',
            pattern_based=False,
        )

        session.add(strategy)
        session.commit()

        logger.info(
            f"Inserted strategy: {strategy_name}\n"
            f"  Type: {strategy_type}\n"
            f"  Timeframe: {timeframe}\n"
            f"  Status: GENERATED\n"
            f"  ID: {strategy.id}"
        )

        print(f"\nStrategy inserted successfully!")
        print(f"  Name: {strategy_name}")
        print(f"  Type: {strategy_type}")
        print(f"  Timeframe: {timeframe}")
        print(f"  Status: GENERATED")
        print(f"\nThe strategy will now go through the normal pipeline:")
        print(f"  GENERATED -> VALIDATED -> TESTED -> SELECTED -> LIVE")


def main():
    parser = argparse.ArgumentParser(
        description='Insert a manual strategy into the database',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
    python scripts/manual_strategy/insert_strategy.py strategies/manual/ManStrat_MOM_a1b2c3d4.py
    python scripts/manual_strategy/insert_strategy.py strategies/manual/ManStrat_REV_12345678.py --force

Strategy Type Legend:
    MOM = Momentum (RSI, breakouts)
    REV = Mean Reversion (Bollinger, mean revert)
    TRN = Trend Following (EMA cross, ADX)
    BRE = Breakout (S/R breaks, range expansion)
    SCA = Scalping (short TF, quick trades)
    VOL = Volatility (ATR-based, squeeze)
        '''
    )

    parser.add_argument(
        'file',
        type=Path,
        help='Path to the strategy file (e.g., strategies/manual/ManStrat_MOM_a1b2c3d4.py)'
    )

    parser.add_argument(
        '--force',
        action='store_true',
        help='Overwrite existing strategy with same name'
    )

    args = parser.parse_args()

    try:
        insert_strategy(args.file, args.force)
    except (ValueError, FileNotFoundError) as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        logger.exception("Failed to insert strategy")
        sys.exit(1)


if __name__ == '__main__':
    main()
