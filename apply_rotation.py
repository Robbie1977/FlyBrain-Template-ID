#!/usr/bin/env python3
"""
Apply rotation to image and update data.
Preserves all channels in multichannel TIFFs.
"""

import numpy as np
import tifffile
from pathlib import Path
import sys
import json


def apply_rotations(data_3d, rotations):
    """Apply rotations in degrees to a 3D volume using np.rot90 for exact 90° rotations."""
    rotated = data_3d.copy()

    # Data layout: [Z, Height, Width] (axes 0, 1, 2)
    # X rotation: rotate in plane (0, 1) — Z↔Height
    # Y rotation: rotate in plane (0, 2) — Z↔Width
    # Z rotation: rotate in plane (1, 2) — Height↔Width

    axis_mapping = {
        'x': (0, 1),  # Z-Height plane
        'y': (0, 2),  # Z-Width plane
        'z': (1, 2),  # Height-Width plane
    }

    for axis, degrees in rotations.items():
        if degrees == 0:
            continue

        if degrees not in [0, 90, 180, 270]:
            raise ValueError(f"Only 90° multiples supported, got {degrees}°")

        axes = axis_mapping[axis]
        k = degrees // 90  # Number of 90° rotations
        rotated = np.rot90(rotated, k=k, axes=axes)

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

    # Load data
    data = tifffile.imread(str(tiff_file))

    if data.ndim == 4:
        # Multichannel: rotate each channel independently, preserve 4D structure
        num_channels = data.shape[1]
        # Apply rotation to first channel to determine output shape
        test_rotated = apply_rotations(data[:, 0, :, :], rotations)
        rotated_shape = (data.shape[0], num_channels) + test_rotated.shape
        rotated = np.empty(rotated_shape, dtype=data.dtype)

        for ch in range(num_channels):
            rotated[:, ch, :, :] = apply_rotations(data[:, ch, :, :], rotations)
        tifffile.imwrite(str(tiff_file), rotated.astype(data.dtype))
    else:
        # Single channel 3D
        rotated = apply_rotations(data, rotations)
        tifffile.imwrite(str(tiff_file), rotated.astype(data.dtype))

    print("Rotation applied successfully")


if __name__ == "__main__":
    main()
