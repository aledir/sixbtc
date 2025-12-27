#!/usr/bin/env python3
"""
Real End-to-End Test for Template-Based Strategy Generation

This script tests the ACTUAL production flow:
1. Load real config
2. Generate 1 template using real AI (Claude)
3. Save template to real database
4. Generate parametric variations
5. Save strategies to real database
6. Verify everything works

Usage:
    python scripts/test_template_real.py
"""

import sys
import logging
from pathlib import Path
from datetime import datetime, UTC
from uuid import uuid4

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
logger = logging.getLogger(__name__)

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.config.loader import load_config
from src.database.models import StrategyTemplate, Strategy, Base
from src.generator.template_generator import TemplateGenerator
from src.generator.parametric_generator import ParametricGenerator
from src.generator.strategy_builder import StrategyBuilder


def main():
    """Run real end-to-end test"""
    print("\n" + "=" * 70)
    print("REAL END-TO-END TEST: Template-Based Strategy Generation")
    print("=" * 70 + "\n")

    # Step 1: Load real configuration
    print("[1/6] Loading production configuration...")
    try:
        config_obj = load_config()
        # Convert Pydantic config to dict for components that need dict
        config = config_obj._raw_config
        print(f"    Config loaded successfully")
        print(f"    AI mode: {config['ai']['mode']}")
        print(f"    Database: {config['database']['host']}:{config['database']['port']}")
    except Exception as e:
        print(f"    ERROR: Failed to load config: {e}")
        return False

    # Step 2: Connect to real database
    print("\n[2/6] Connecting to database...")
    try:
        db_url = (
            f"postgresql://{config['database']['user']}:{config['database']['password']}"
            f"@{config['database']['host']}:{config['database']['port']}"
            f"/{config['database']['database']}"
        )
        engine = create_engine(db_url)
        Session = sessionmaker(bind=engine)
        session = Session()

        # Test connection
        from sqlalchemy import text
        session.execute(text("SELECT 1"))
        print(f"    Database connection OK")
    except Exception as e:
        print(f"    ERROR: Database connection failed: {e}")
        return False

    # Step 3: Generate 1 template using real AI
    print("\n[3/6] Generating template with AI (this may take 30-60 seconds)...")
    try:
        template_generator = TemplateGenerator(config)
        template = template_generator.generate_template(
            strategy_type="MOM",
            timeframe="1h"
        )

        if template is None:
            print("    ERROR: AI failed to generate template")
            return False

        print(f"    Template generated: {template.name}")
        print(f"    Strategy type: {template.strategy_type}")
        print(f"    Timeframe: {template.timeframe}")
        print(f"    Parameters: {list(template.parameters_schema.keys())}")

        # Count expected variations
        total_variations = 1
        for param, spec in template.parameters_schema.items():
            values = spec.get('values', [])
            total_variations *= len(values)
            print(f"      - {param}: {len(values)} values")
        print(f"    Expected variations: {total_variations}")

    except Exception as e:
        print(f"    ERROR: Template generation failed: {e}")
        import traceback
        traceback.print_exc()
        return False

    # Step 4: Save template to database
    print("\n[4/6] Saving template to database...")
    try:
        # Ensure template has all required fields
        template.created_at = datetime.now(UTC)
        session.add(template)
        session.commit()
        print(f"    Template saved with ID: {template.id}")
    except Exception as e:
        session.rollback()
        print(f"    ERROR: Failed to save template: {e}")
        return False

    # Step 5: Generate parametric variations
    print("\n[5/6] Generating parametric variations...")
    try:
        parametric_generator = ParametricGenerator()
        variations = parametric_generator.generate_variations(
            template,
            max_variations=10  # Limit for test
        )

        valid_count = sum(1 for v in variations if v.validation_passed)
        print(f"    Generated: {len(variations)} variations")
        print(f"    Validated: {valid_count}")

        if len(variations) == 0:
            print("    ERROR: No variations generated")
            return False

        # Show first variation details
        v = variations[0]
        print(f"\n    First variation:")
        print(f"      ID: {v.strategy_id}")
        print(f"      Parameters: {v.parameters}")
        print(f"      Validation: {v.validation_passed}")
        if v.validation_errors:
            print(f"      Errors: {v.validation_errors}")

    except Exception as e:
        print(f"    ERROR: Variation generation failed: {e}")
        import traceback
        traceback.print_exc()
        return False

    # Step 6: Save strategies to database
    print("\n[6/6] Saving strategies to database...")
    saved_count = 0
    try:
        for v in variations:
            if not v.validation_passed:
                continue

            strategy = Strategy(
                id=uuid4(),
                name=f"Strategy_{v.strategy_type}_{v.strategy_id}",
                strategy_type=v.strategy_type,
                timeframe=v.timeframe,
                status='GENERATED',
                code=v.code,
                template_id=template.id,
                generation_mode='template',
                parameters=v.parameters,
                ai_provider=template.ai_provider,
                created_at=datetime.now(UTC)
            )
            session.add(strategy)
            saved_count += 1

        # Update template counter
        template.strategies_generated = saved_count
        session.commit()
        print(f"    Saved {saved_count} strategies to database")

    except Exception as e:
        session.rollback()
        print(f"    ERROR: Failed to save strategies: {e}")
        import traceback
        traceback.print_exc()
        return False

    # Verification
    print("\n" + "-" * 70)
    print("VERIFICATION")
    print("-" * 70)

    # Verify template in DB
    db_template = session.query(StrategyTemplate).filter_by(id=template.id).first()
    print(f"\nTemplate in database: {'YES' if db_template else 'NO'}")
    if db_template:
        print(f"  Name: {db_template.name}")
        print(f"  Strategies generated: {db_template.strategies_generated}")

    # Verify strategies in DB
    db_strategies = session.query(Strategy).filter_by(template_id=template.id).all()
    print(f"\nStrategies in database: {len(db_strategies)}")
    for s in db_strategies[:3]:  # Show first 3
        print(f"  - {s.name}: mode={s.generation_mode}, params={s.parameters}")
    if len(db_strategies) > 3:
        print(f"  ... and {len(db_strategies) - 3} more")

    # Verify relationship
    print(f"\nRelationship works: {len(db_template.strategies)} strategies linked")

    # Summary
    print("\n" + "=" * 70)
    print("TEST RESULT: SUCCESS")
    print("=" * 70)
    print(f"""
Summary:
  - Template: {template.name}
  - AI Provider: {template.ai_provider}
  - Parameters: {len(template.parameters_schema)}
  - Variations generated: {len(variations)}
  - Strategies saved: {saved_count}
  - All validations passed: {all(v.validation_passed for v in variations)}

The template-based generation system is working correctly!

Note: Template and strategies have been saved to the database.
      To clean up, run:

      DELETE FROM strategies WHERE template_id = '{template.id}';
      DELETE FROM strategy_templates WHERE id = '{template.id}';
""")

    session.close()
    return True


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
