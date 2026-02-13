#!/usr/bin/env python3
"""
Compare original vs rotated sample projections to see what the rotation did.
"""

import numpy as np
import nrrd
import matplotlib.pyplot as plt

def compare_original_vs_rotated():
    """Compare projections of original and rotated samples."""
    print("Comparing original vs rotated sample projections...")

    # Load both samples
    original_file = "channels/VNC_SPR8AD.Fru11.12DBD.FB1.1.NC82.Brain.40x.1.composite_channel1.nrrd"
    rotated_file = "channels/VNC_SPR8AD.Fru11.12DBD.FB1.1.NC82.Brain.40x.1.composite_channel1_rotated_180z.nrrd"

    original_data, _ = nrrd.read(original_file)
    rotated_data, _ = nrrd.read(rotated_file)

    print(f"Original shape: {original_data.shape}")
    print(f"Rotated shape: {rotated_data.shape}")

    # Create binary masks
    threshold = 30
    orig_binary = (original_data > threshold).astype(np.uint8)
    rot_binary = (rotated_data > threshold).astype(np.uint8)

    # Create projections
    orig_xy = np.max(orig_binary, axis=2)
    orig_xz = np.max(orig_binary, axis=1)
    orig_yz = np.max(orig_binary, axis=0)

    rot_xy = np.max(rot_binary, axis=2)
    rot_xz = np.max(rot_binary, axis=1)
    rot_yz = np.max(rot_binary, axis=0)

    # Create comparison plot
    fig, axes = plt.subplots(2, 3, figsize=(15, 10))

    # Original projections
    axes[0,0].imshow(orig_xy, cmap='gray')
    axes[0,0].set_title('Original XY (Dorsal)')
    axes[0,1].imshow(orig_xz, cmap='gray')
    axes[0,1].set_title('Original XZ (Lateral)')
    axes[0,2].imshow(orig_yz, cmap='gray')
    axes[0,2].set_title('Original YZ (Anterior)')

    # Rotated projections
    axes[1,0].imshow(rot_xy, cmap='gray')
    axes[1,0].set_title('Rotated XY (Dorsal)')
    axes[1,1].imshow(rot_xz, cmap='gray')
    axes[1,1].set_title('Rotated XZ (Lateral)')
    axes[1,2].imshow(rot_yz, cmap='gray')
    axes[1,2].set_title('Rotated YZ (Anterior)')

    plt.tight_layout()
    plt.savefig('original_vs_rotated_projections.png', dpi=150, bbox_inches='tight')
    print("Saved comparison to: original_vs_rotated_projections.png")

    # Check if projections are identical (they should be for 180° Z rotation)
    xy_identical = np.array_equal(orig_xy, rot_xy)
    xz_identical = np.array_equal(orig_xz, rot_xz)
    yz_identical = np.array_equal(orig_yz, rot_yz)

    print("\nProjection comparison:")
    print(f"XY projections identical: {xy_identical}")
    print(f"XZ projections identical: {xz_identical}")
    print(f"YZ projections identical: {yz_identical}")

    # For 180° rotation around Z-axis, XY should be identical, XZ and YZ should be flipped
    print("\nExpected for 180° Z-axis rotation:")
    print("- XY (dorsal view): should be identical")
    print("- XZ (lateral view): should be flipped left-right")
    print("- YZ (anterior view): should be flipped left-right")

if __name__ == "__main__":
    compare_original_vs_rotated()