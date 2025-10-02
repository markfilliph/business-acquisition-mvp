#!/usr/bin/env python3
"""
Test the critical validation system to prevent configuration errors.
"""
import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from validation.config_validator import run_validation_check

async def main():
    """Run validation test."""
    success = await run_validation_check()
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    asyncio.run(main())