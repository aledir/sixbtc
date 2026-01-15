"""migrate_strategy_types_to_5_unified

Revision ID: 6d97260858eb
Revises: 0b44290a73b2
Create Date: 2026-01-14 14:23:25.313764

Migrates all strategy_type values to the unified 5-type system:
TRD (Trend), MOM (Momentum), REV (Reversal), VOL (Volume), CDL (Candlestick)
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '6d97260858eb'
down_revision: Union[str, Sequence[str], None] = '0b44290a73b2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Complete mapping from old types to unified 5 types
# This MUST match OLD_TYPE_TO_NEW in src/generator/strategy_types.py
OLD_TO_NEW = {
    # Already correct (5 unified types) - no migration needed
    # "TRD": "TRD",
    # "MOM": "MOM",
    # "REV": "REV",
    # "VOL": "VOL",
    # "CDL": "CDL",

    # VLM renamed to VOL
    "VLM": "VOL",

    # Unger legacy types
    "UNG": "TRD",
    "BRK": "TRD",

    # ----- Momentum types (oscillators, thresholds, divergences) -----
    "THR": "MOM",
    "DIV": "MOM",
    "APO": "MOM",
    "RSL": "MOM",
    "MEX": "MOM",
    "PPO": "MOM",
    "CMO": "MOM",
    "TSI": "MOM",
    "RVI": "MOM",
    "SMI": "MOM",
    "ULT": "MOM",
    "WLR": "MOM",
    "SRI": "MOM",
    "QQE": "MOM",
    "TVI": "MOM",
    "BOP": "MOM",
    "COP": "MOM",
    "PST": "MOM",
    "IMC": "MOM",
    "IMP": "MOM",
    "ELD": "MOM",
    "AWE": "MOM",
    "ACC": "MOM",

    # ----- Trend types (crossovers, trend-following, directional) -----
    "CRS": "TRD",
    "MAS": "TRD",
    "DMI": "TRD",
    "ADX": "TRD",
    "SAR": "TRD",
    "ICH": "TRD",
    "ARN": "TRD",
    "DON": "TRD",
    "KLT": "TRD",
    "TRX": "TRD",
    "KST": "TRD",
    "DPO": "TRD",
    "CHP": "TRD",
    "ATB": "TRD",
    "CNF": "TRD",
    "CHN": "TRD",
    "ADV": "TRD",
    "VTX": "TRD",
    "SWG": "TRD",
    "HLS": "TRD",
    "HLB": "TRD",
    "DBL": "TRD",
    "SQZ": "TRD",
    "TRN": "TRD",  # Old trend type

    # ----- Reversal types (mean reversion, volatility bands, statistical) -----
    "STA": "REV",
    "BBW": "REV",
    "ZLM": "REV",
    "STD": "REV",
    "PCE": "REV",
    "PCT": "REV",
    "MRV": "REV",

    # ----- Volume types -----
    "VFL": "VOL",
    "VPR": "VOL",
    "FRC": "VOL",
    "OBV": "VOL",
    "CMF": "VOL",
    "MFI": "VOL",
    "KLG": "VOL",
    "NVI": "VOL",
    "PVI": "VOL",
    "PVT": "VOL",
    "ADO": "VOL",
    "EMV": "VOL",
    "VWP": "VOL",
    "VWM": "VOL",
    "WAD": "VOL",
    "HVO": "VOL",

    # ----- Candlestick/Price Action types -----
    "PRC": "CDL",
    "GAP": "CDL",
    "INR": "CDL",
    "HAK": "CDL",
    "PIN": "CDL",
    "ENG": "CDL",

    # ----- Pattern gen specific -----
    "FLT": "TRD",
    "RNG": "REV",
    "RTR": "REV",
    "RCM": "REV",
    "RCE": "REV",
    "CNS": "REV",
    "CSZ": "REV",
    "CSQ": "REV",
    "MDI": "MOM",
    "MCH": "MOM",
    "MQU": "MOM",
    "MBR": "MOM",
    "NRX": "MOM",
    "DUM": "MOM",
    "PMD": "MOM",
    "LNR": "TRD",
    "KAM": "TRD",
    "MLT": "TRD",
    "MED": "REV",
    "PEX": "REV",
    "PVE": "VOL",
    "PVL": "VOL",
    "PRB": "REV",
    "PRJ": "TRD",
    "PRT": "REV",
    "PRO": "TRD",
    "SMB": "TRD",
    "SER": "REV",
    "SNT": "TRD",
    "SNR": "TRD",
    "SBN": "TRD",
    "RBW": "TRD",
    "RBN": "TRD",
    "RPS": "MOM",
    "RRJ": "REV",
    "RVC": "REV",
    "RCX": "REV",
    "TMA": "TRD",
    "TRP": "TRD",
    "TWR": "TRD",
    "TYP": "REV",
    "UOE": "MOM",
    "VAX": "REV",
    "VCX": "VOL",
    "VDY": "VOL",
    "VDS": "VOL",
    "VBK": "VOL",
    "VLR": "VOL",
    "VMM": "VOL",
    "VOO": "VOL",
    "VRE": "VOL",
    "VRG": "VOL",
    "VSQ": "VOL",
    "VSY": "VOL",
    "VTR": "VOL",
    "VPX": "VOL",
    "WCL": "TRD",
    "WVT": "VOL",
    "WAX": "VOL",
    "ZZG": "TRD",
    "ACH": "MOM",
    "ALM": "TRD",
    "ARS": "TRD",
    "ASI": "TRD",
    "AVG": "TRD",
    "BKC": "TRD",
    "BKF": "TRD",
    "BKS": "TRD",
    "BPX": "TRD",
    "BSN": "TRD",
    "BWR": "REV",
    "CDM": "CDL",
    "CHV": "REV",
    "CLX": "TRD",
    "CLP": "TRD",
    "CNP": "TRD",
    "COG": "TRD",
    "CRI": "REV",
    "CYC": "REV",
    "DMX": "TRD",
    "DPT": "TRD",
    "DTP": "REV",
    "DTV": "REV",
    "DVX": "MOM",
    "DYM": "MOM",
    "EFR": "VOL",
    "EHL": "TRD",
    "EIM": "MOM",
    "EMS": "TRD",
    "EMX": "TRD",
    "ETM": "TRD",
    "EXC": "TRD",
    "EXS": "TRD",
    "FSH": "MOM",
    "GAX": "CDL",
    "HLD": "TRD",
    "HMA": "TRD",
    "HPI": "TRD",
    "HRS": "TRD",
    "IDM": "TRD",
    "JMA": "TRD",
    "LAG": "TRD",
    "LIQ": "VOL",
    "MAC": "MOM",
    "MCG": "TRD",
    "MDV": "REV",
    "MFB": "VOL",
    "MFE": "VOL",
    "MFX": "VOL",
    "MPT": "TRD",
    "MRG": "REV",
    "MSH": "MOM",
    "MTF": "TRD",
    "NTR": "REV",
    "OCR": "TRD",
    "OCX": "MOM",
    "OEX": "MOM",
    "OFP": "TRD",
    "PAZ": "CDL",
    "PBE": "TRD",
    "PCR": "TRD",
    "PDN": "TRD",
    "PEF": "REV",
    "PLV": "REV",
    "PMM": "MOM",
    "PMO": "MOM",
    "POX": "MOM",
    "PPE": "MOM",
    "PPX": "MOM",
    "PTA": "TRD",  # pandas_ta based
    "PTC": "TRD",
    "PTR": "TRD",
    "PZO": "MOM",
    "RGB": "TRD",
    "RMI": "MOM",
    "SPK": "VOL",
    "SPT": "TRD",
    "STC": "MOM",
    "STB": "TRD",
    "STE": "TRD",
    "STW": "TRD",
    "SWI": "TRD",
    "TCF": "TRD",
    "TCH": "TRD",
    "TDM": "TRD",
    "TEX": "TRD",
    "TFL": "TRD",
    "THT": "MOM",
    "TIN": "TRD",
    "TQU": "TRD",
    "TSC": "MOM",
    "TSE": "MOM",
    "TSX": "MOM",
    "VWR": "VOL",
    "PSE": "MOM",
}


def upgrade() -> None:
    """Migrate strategy_type and name columns to unified 5-type system."""
    conn = op.get_bind()

    # Migrate each old type to the new unified type
    for old_type, new_type in OLD_TO_NEW.items():
        # Update strategy_type column
        conn.execute(
            sa.text("""
                UPDATE strategies
                SET strategy_type = :new_type
                WHERE strategy_type = :old_type
            """),
            {"old_type": old_type, "new_type": new_type}
        )

        # Update name column (replace old type with new type in name)
        # Pattern: PGnStrat_OLD_xxx -> PGnStrat_NEW_xxx
        conn.execute(
            sa.text("""
                UPDATE strategies
                SET name = REPLACE(name, :old_pattern, :new_pattern)
                WHERE strategy_type = :new_type
                AND name LIKE :like_pattern
            """),
            {
                "old_pattern": f"_{old_type}_",
                "new_pattern": f"_{new_type}_",
                "new_type": new_type,
                "like_pattern": f"%_{old_type}_%"
            }
        )

        # Update code column (replace class name in code)
        # Pattern: class PGnStrat_OLD_xxx -> class PGnStrat_NEW_xxx
        conn.execute(
            sa.text("""
                UPDATE strategies
                SET code = REPLACE(code, :old_class, :new_class)
                WHERE strategy_type = :new_type
                AND code LIKE :like_pattern
            """),
            {
                "old_class": f"Strat_{old_type}_",
                "new_class": f"Strat_{new_type}_",
                "new_type": new_type,
                "like_pattern": f"%Strat_{old_type}_%"
            }
        )

    print(f"Migrated {len(OLD_TO_NEW)} old types to unified 5-type system")


def downgrade() -> None:
    """
    Downgrade is not supported for this migration.

    The mapping is many-to-one (many old types map to 5 new types),
    so we cannot reconstruct the original types.
    """
    raise NotImplementedError(
        "Downgrade not supported: mapping is many-to-one. "
        "Original types cannot be reconstructed."
    )
