#!/usr/bin/env python3
"""
Reset image orientation by re-generating channel NRRDs from the original TIFF.

The original TIFF is never modified, so resetting simply means re-running
convert_tiff_to_nrrd.py to regenerate fresh channel NRRDs and clearing
any rotation state in orientations.json.
"""

import sys
import json
from pathlib import Path


def main():
    if len(sys.argv) < 2:
        print("Usage: python reset_rotation.py <image_base>")
        sys.exit(1)

    image_base = sys.argv[1]

    # Re-generate channel NRRDs from original (unmodified) TIFF
    from convert_tiff_to_nrrd import convert_and_split
    try:
        sig_path, bg_path = convert_and_split(image_base)
        print(f"Re-generated channel NRRDs from original TIFF:")
        print(f"  Signal:     {sig_path}")
        print(f"  Background: {bg_path}")
    except FileNotFoundError as e:
        print(f"Error: {e}")
        sys.exit(1)

    # Clear rotation in orientations.json
    orientations_file = Path("orientations.json")
    if orientations_file.exists():
        data = json.loads(orientations_file.read_text())
        # Find the entry by image_base
        for key, val in data.items():
            if image_base in key:
                mc = val.get('manual_corrections', {})
                mc['rotations'] = {'x': 0, 'y': 0, 'z': 0}
                val['manual_corrections'] = mc
                print(f"  Cleared rotations for {key}")
                break
        orientations_file.write_text(json.dumps(data, indent=2))

    print("Rotation reset successfully")


if __name__ == "__main__":
    main()