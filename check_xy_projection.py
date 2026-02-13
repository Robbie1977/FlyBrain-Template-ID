#!/usr/bin/env python3
"""
Check if XY projections are actually identical after 180° Z rotation.
"""

import numpy as np
import nrrd

def check_xy_projection():
    """Check if XY projections are identical."""
    print("Checking XY projections...")

    # Load both files
    original_file = "channels/VNC_SPR8AD.Fru11.12DBD.FB1.1.NC82.Brain.40x.1.composite_channel1.nrrd"
    rotated_file = "channels/VNC_SPR8AD.Fru11.12DBD.FB1.1.NC82.Brain.40x.1.composite_channel1_rotated_180z.nrrd"

    orig_data, _ = nrrd.read(original_file)
    rot_data, _ = nrrd.read(rotated_file)

    # Create binary masks
    threshold = 30
    orig_binary = (orig_data > threshold).astype(np.uint8)
    rot_binary = (rot_data > threshold).astype(np.uint8)

    # XY projections
    orig_xy = np.max(orig_binary, axis=2)
    rot_xy = np.max(rot_binary, axis=2)

    # Check if identical
    xy_identical = np.array_equal(orig_xy, rot_xy)
    print(f"XY projections identical: {xy_identical}")

    if not xy_identical:
        # Check if one is flipped version of the other
        rot_xy_flipped_lr = np.fliplr(rot_xy)
        rot_xy_flipped_ud = np.flipud(rot_xy)

        lr_identical = np.array_equal(orig_xy, rot_xy_flipped_lr)
        ud_identical = np.array_equal(orig_xy, rot_xy_flipped_ud)

        print(f"XY projection matches rotated flipped left-right: {lr_identical}")
        print(f"XY projection matches rotated flipped up-down: {ud_identical}")

        # Show some differences
        diff = np.sum(orig_xy != rot_xy)
        total_pixels = orig_xy.size
        print(f"Different pixels: {diff}/{total_pixels} ({100*diff/total_pixels:.1f}%)")

    # Let's also manually check what np.rot90 does to XY projection
    print("\nTesting what rotation should do to XY projection...")

    # For 180° rotation around Z, XY projection should be identical
    # Let's verify this with a simple test
    test_data = np.random.rand(10, 10, 5)
    test_rotated = np.rot90(test_data, k=2, axes=(0, 1))

    test_xy_orig = np.max(test_data, axis=2)
    test_xy_rot = np.max(test_rotated, axis=2)

    test_identical = np.array_equal(test_xy_orig, test_xy_rot)
    print(f"Test data XY projections identical after rot90: {test_identical}")

if __name__ == "__main__":
    check_xy_projection()