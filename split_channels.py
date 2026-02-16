#!/usr/bin/env python3
"""
DEPRECATED: This script is no longer used.

Channel splitting is now handled directly by convert_tiff_to_nrrd.py,
which reads the original TIFF and outputs per-channel NRRDs in [X, Y, Z]
order with correct space directions and LPS space in a single step.

This file is kept for reference only. Do not use it.
"""

import sys
print("WARNING: split_channels.py is deprecated. Use convert_tiff_to_nrrd.py instead.", file=sys.stderr)
print("  convert_tiff_to_nrrd.py now outputs channel NRRDs directly from TIFF.")
print("  Run: python3 convert_tiff_to_nrrd.py <image_base>")
sys.exit(1)