#!/usr/bin/env python3
"""
Apply rotation to NRRD channel files (signal + background).

The original TIFF is NEVER modified.  Rotations are applied to the NRRD
files in channels/ which are in [X, Y, Z] order with correct space
directions.

For each 90° rotation around an axis, we:
  1. np.rot90() on the data array
  2. Swap the corresponding rows of space directions so voxel sizes
     stay correct after the axis swap

Usage:
    python apply_rotation.py <image_base> '{"x":0,"y":0,"z":90}'
"""

import sys
import json
import os
import tempfile
from concurrent.futures import ProcessPoolExecutor, as_completed
import numpy as np
import nrrd
from pathlib import Path


ORIENTATIONS_FILE = Path("orientations.json")


def rotate_nrrd(nrrd_path, rotations):
    """Rotate an NRRD file in-place, updating data and space directions.

    Parameters
    ----------
    nrrd_path : str or Path
        Path to the NRRD file (will be overwritten).
    rotations : dict
        {'x': degrees, 'y': degrees, 'z': degrees}  — multiples of 90.
    """
    nrrd_path = Path(nrrd_path)
    if not nrrd_path.exists():
        raise FileNotFoundError(f"NRRD file not found: {nrrd_path}")

    data, header = nrrd.read(str(nrrd_path))
    sd = np.array(header['space directions'], dtype=float).copy()

    # NRRD data is [X, Y, Z] (axes 0, 1, 2)
    # X rotation: rotate in Y-Z plane → axes (1, 2)
    # Y rotation: rotate in X-Z plane → axes (0, 2)
    # Z rotation: rotate in X-Y plane → axes (0, 1)
    axis_map = {
        'x': (1, 2),
        'y': (0, 2),
        'z': (0, 1),
    }

    for axis_name in ['x', 'y', 'z']:
        degrees = rotations.get(axis_name, 0)
        if degrees == 0:
            continue
        if degrees % 90 != 0:
            raise ValueError(f"Only 90° multiples supported, got {degrees}°")

        k = (degrees // 90) % 4
        if k == 0:
            continue

        axes = axis_map[axis_name]
        data = np.rot90(data, k=k, axes=axes)

        # For 90° or 270° (odd k): axes are swapped → swap space directions
        if k % 2 == 1:
            sd[axes[0]], sd[axes[1]] = sd[axes[1]].copy(), sd[axes[0]].copy()
        # For 180°: axes stay in place, space directions unchanged

    # Update header
    header['space directions'] = sd.tolist()
    header['sizes'] = list(data.shape)

    # Atomic write: write to temp file then rename, so a killed process
    # cannot leave a half-written (corrupted) NRRD file
    fd, tmp_path = tempfile.mkstemp(suffix='.nrrd', dir=str(nrrd_path.parent))
    os.close(fd)
    try:
        nrrd.write(tmp_path, data, header)
        os.replace(tmp_path, str(nrrd_path))
    except Exception:
        # Clean up temp file on failure
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise
    return data.shape, sd.tolist()


def main():
    if len(sys.argv) < 3:
        print("Usage: python apply_rotation.py <image_base> '<rotations_json>'")
        sys.exit(1)

    image_base = sys.argv[1]
    rotations = json.loads(sys.argv[2])

    # Skip if no rotation needed
    if all(v % 360 == 0 for v in rotations.values()):
        print("No rotation needed (all 0°)")
        return

    channels_dir = Path("channels")
    signal_path = channels_dir / f"{image_base}_signal.nrrd"
    bg_path = channels_dir / f"{image_base}_background.nrrd"

    if not signal_path.exists() or not bg_path.exists():
        print(f"Error: Channel NRRDs not found in {channels_dir}/")
        print(f"  Expected: {signal_path.name} and {bg_path.name}")
        print("  Run convert_tiff_to_nrrd.py first to create them.")
        sys.exit(1)

    # Rotate both channel files in parallel
    print(f"Rotating {image_base} by {rotations}")

    with ProcessPoolExecutor(max_workers=2) as executor:
        futures = {
            executor.submit(rotate_nrrd, signal_path, rotations): "Signal",
            executor.submit(rotate_nrrd, bg_path, rotations): "Background",
        }
        for future in as_completed(futures):
            label = futures[future]
            shape, sd = future.result()
            print(f"  {label:12s} shape={shape}  space_dirs={sd}")

    print("Rotation applied successfully")


if __name__ == "__main__":
    main()
