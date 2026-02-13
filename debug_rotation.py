#!/usr/bin/env python3
"""
Debug the rotation to see what actually happened.
"""

import numpy as np
import nrrd

def debug_rotation():
    """Debug what the rotation actually did."""
    print("Debugging the rotation...")

    # Load both files
    original_file = "channels/VNC_SPR8AD.Fru11.12DBD.FB1.1.NC82.Brain.40x.1.composite_channel1.nrrd"
    rotated_file = "channels/VNC_SPR8AD.Fru11.12DBD.FB1.1.NC82.Brain.40x.1.composite_channel1_rotated_180z.nrrd"

    orig_data, orig_header = nrrd.read(original_file)
    rot_data, rot_header = nrrd.read(rotated_file)

    print(f"Original shape: {orig_data.shape}")
    print(f"Rotated shape: {rot_data.shape}")

    print(f"\nOriginal space directions:")
    for i, sd in enumerate(orig_header['space directions']):
        print(f"  Axis {i}: {sd}")

    print(f"\nRotated space directions:")
    for i, sd in enumerate(rot_header['space directions']):
        print(f"  Axis {i}: {sd}")

    # Check if data is actually different
    data_identical = np.array_equal(orig_data, rot_data)
    print(f"\nData arrays identical: {data_identical}")

    if not data_identical:
        # Check what kind of transformation it is
        # Test if it's a 180° rotation around Z
        test_rot90_z = np.rot90(orig_data, k=2, axes=(0, 1))
        rot90_identical = np.array_equal(test_rot90_z, rot_data)
        print(f"Matches np.rot90(k=2, axes=(0,1)): {rot90_identical}")

        # Test other possibilities
        test_rot90_x = np.rot90(orig_data, k=2, axes=(1, 2))
        rot90_x_identical = np.array_equal(test_rot90_x, rot_data)
        print(f"Matches np.rot90(k=2, axes=(1,2)): {rot90_x_identical}")

        test_rot90_y = np.rot90(orig_data, k=2, axes=(0, 2))
        rot90_y_identical = np.array_equal(test_rot90_y, rot_data)
        print(f"Matches np.rot90(k=2, axes=(0,2)): {rot90_y_identical}")

        # Check if it's flipped along axes
        test_flip_x = np.flip(orig_data, axis=0)
        flip_x_identical = np.array_equal(test_flip_x, rot_data)
        print(f"Matches flip along X (axis 0): {flip_x_identical}")

        test_flip_y = np.flip(orig_data, axis=1)
        flip_y_identical = np.array_equal(test_flip_y, rot_data)
        print(f"Matches flip along Y (axis 1): {flip_y_identical}")

        test_flip_z = np.flip(orig_data, axis=2)
        flip_z_identical = np.array_equal(test_flip_z, rot_data)
        print(f"Matches flip along Z (axis 2): {flip_z_identical}")

    # Check some sample values
    print("\nSample values:")
    print(f"Original [100,100,70]: {orig_data[100,100,70]}")
    print(f"Rotated [100,100,70]: {rot_data[100,100,70]}")

    # What should it be after 180° Z rotation?
    h, w, d = orig_data.shape
    expected_value = orig_data[h-100-1, w-100-1, 70]  # 180° rotation around Z
    print(f"Expected after 180° Z rotation: {expected_value}")

if __name__ == "__main__":
    debug_rotation()