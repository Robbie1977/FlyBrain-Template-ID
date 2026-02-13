#!/usr/bin/env python3
"""Test to verify the 4D shape bug in apply_rotation.py"""
import tifffile
import numpy as np

data = tifffile.imread('Images/DeepanshuSingh/Brain_Fru11.12AD_FD6DBD_FB1.1_NC82_S1.tif')
print(f'Shape: {data.shape}, ndim: {data.ndim}')

if data.ndim == 4:
    ch_data = data[:, 0, :, :]
    print(f'Per-channel 3D shape: {ch_data.shape}')

    # Apply x=90
    rotated = np.rot90(ch_data, k=1, axes=(0,1))
    print(f'After X rotation: {rotated.shape}')
    # Apply z=90
    rotated = np.rot90(rotated, k=1, axes=(1,2))
    print(f'After Z rotation: {rotated.shape}')

    test_rotated = rotated

    # Bug: current code
    buggy_shape = (data.shape[0], data.shape[1]) + test_rotated.shape
    print(f'Buggy rotated_shape: {buggy_shape} (ndim={len(buggy_shape)})')

    # Fix
    correct_shape = (test_rotated.shape[0], data.shape[1]) + test_rotated.shape[1:]
    print(f'Correct rotated_shape: {correct_shape} (ndim={len(correct_shape)})')

    # Try the buggy assignment
    try:
        buggy_arr = np.empty(buggy_shape, dtype=data.dtype)
        buggy_arr[:, 0, :, :] = test_rotated
        print('Buggy assignment: SUCCEEDED (unexpected)')
    except Exception as e:
        print(f'Buggy assignment: FAILED with {type(e).__name__}: {e}')

    # Try the correct assignment
    try:
        correct_arr = np.empty(correct_shape, dtype=data.dtype)
        correct_arr[:, 0, :, :] = test_rotated
        print('Correct assignment: SUCCEEDED')
    except Exception as e:
        print(f'Correct assignment: FAILED with {type(e).__name__}: {e}')
