#!/usr/bin/env python3
"""
Apply rotation to image and update data.
"""

import numpy as np
import tifffile
from pathlib import Path
import sys
import json
from scipy.ndimage import rotate

def apply_rotations(data, rotations):
    """Apply rotations in degrees."""
    rotated = data.copy()
    for axis, degrees in rotations.items():
        if degrees == 0:
            continue
        axis_num = {'x': 0, 'y': 1, 'z': 2}[axis]
        rotated = rotate(rotated, degrees, axes=(axis_num, (axis_num + 1) % 3), reshape=False, mode='constant', cval=0)
    return rotated

def main():
    if len(sys.argv) < 3:
        print("Usage: python apply_rotation.py <image_path> '<rotations_json>'")
        sys.exit(1)

    image_path = sys.argv[1]
    rotations = json.loads(sys.argv[2])

    tiff_file = Path("Images") / f"{image_path}.tif"
    if not tiff_file.exists():
        tiff_file = Path("Images") / f"{image_path}.tiff"
        if not tiff_file.exists():
            print("Error: Image not found")
            sys.exit(1)

    # Load and rotate
    data = tifffile.imread(str(tiff_file))
    if data.ndim == 4:  # (slices, channels, h, w)
        data = data[:, 0, :, :]  # Take first channel
    rotated = apply_rotations(data, rotations)
    # For saving, need to handle channels, but for now save as 3D
    tifffile.imwrite(str(tiff_file), rotated.astype(data.dtype))

    print("Rotation applied successfully")

if __name__ == "__main__":
    main()