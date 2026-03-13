#!/usr/bin/env python3
"""Domain Seller - Entry point."""

import sys
import os

# Add project root to path so 'core' package can be imported
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.cli_v2 import main

if __name__ == "__main__":
    main()
