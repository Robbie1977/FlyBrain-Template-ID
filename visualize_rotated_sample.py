#!/usr/bin/env python3
"""
Visualize the rotated sample to understand why it doesn't match the VNC template.
"""

import numpy as np
import nrrd
import matplotlib.pyplot as plt
from pathlib import Path

def visualize_rotated_sample():
    """Create visualizations of the rotated sample."""
    print("Visualizing rotated sample...")

    # Load the rotated sample
    rotated_file = "channels/VNC_SPR8AD.Fru11.12DBD.FB1.1.NC82.Brain.40x.1.composite_channel1_rotated_180z.nrrd"
    data, header = nrrd.read(rotated_file)

    print(f"Rotated sample shape: {data.shape}")
    print(f"Rotated sample voxel sizes: X={header['space directions'][0][0]:.3f}, Y={header['space directions'][1][1]:.3f}, Z={header['space directions'][2][2]:.3f}")

    # Load VNC template for comparison
    template_data, template_header = nrrd.read("JRCVNC2018U_template.nrrd")
    print(f"VNC template shape: {template_data.shape}")
    print(f"VNC template voxel sizes: X={template_header['space directions'][0][0]:.3f}, Y={template_header['space directions'][1][1]:.3f}, Z={template_header['space directions'][2][2]:.3f}")

    # Create maximum intensity projections
    # Apply threshold
    threshold = 30
    sample_binary = (data > threshold).astype(np.uint8)
    template_binary = (template_data > threshold).astype(np.uint8)

    # XY projection (dorsal view)
    sample_xy = np.max(sample_binary, axis=2)
    template_xy = np.max(template_binary, axis=2)

    # XZ projection (lateral view)
    sample_xz = np.max(sample_binary, axis=1)
    template_xz = np.max(template_binary, axis=1)

    # YZ projection (anterior view)
    sample_yz = np.max(sample_binary, axis=0)
    template_yz = np.max(template_binary, axis=0)

    # Create comparison plots
    fig, axes = plt.subplots(2, 3, figsize=(15, 10))

    # Sample projections
    axes[0,0].imshow(sample_xy, cmap='gray')
    axes[0,0].set_title('Sample XY (Dorsal)')
    axes[0,0].set_xlabel('X (pixels)')
    axes[0,0].set_ylabel('Y (pixels)')

    axes[0,1].imshow(sample_xz, cmap='gray')
    axes[0,1].set_title('Sample XZ (Lateral)')
    axes[0,1].set_xlabel('X (pixels)')
    axes[0,1].set_ylabel('Z (pixels)')

    axes[0,2].imshow(sample_yz, cmap='gray')
    axes[0,2].set_title('Sample YZ (Anterior)')
    axes[0,2].set_xlabel('Y (pixels)')
    axes[0,2].set_ylabel('Z (pixels)')

    # Template projections
    axes[1,0].imshow(template_xy, cmap='gray')
    axes[1,0].set_title('VNC Template XY (Dorsal)')
    axes[1,0].set_xlabel('X (pixels)')
    axes[1,0].set_ylabel('Y (pixels)')

    axes[1,1].imshow(template_xz, cmap='gray')
    axes[1,1].set_title('VNC Template XZ (Lateral)')
    axes[1,1].set_xlabel('X (pixels)')
    axes[1,1].set_ylabel('Z (pixels)')

    axes[1,2].imshow(template_yz, cmap='gray')
    axes[1,2].set_title('VNC Template YZ (Anterior)')
    axes[1,2].set_xlabel('Y (pixels)')
    axes[1,2].set_ylabel('Z (pixels)')

    plt.tight_layout()
    plt.savefig('rotated_sample_vs_vnc_template_projections.png', dpi=150, bbox_inches='tight')
    print("Saved comparison plot to: rotated_sample_vs_vnc_template_projections.png")

    # Print some statistics
    print("\nSample statistics:")
    print(f"  XY projection shape: {sample_xy.shape}")
    print(f"  XZ projection shape: {sample_xz.shape}")
    print(f"  YZ projection shape: {sample_yz.shape}")
    print(f"  Total signal voxels: {np.sum(sample_binary)}")
    print(f"  Signal fraction: {np.sum(sample_binary) / np.prod(data.shape):.4f}")

    print("\nVNC Template statistics:")
    print(f"  XY projection shape: {template_xy.shape}")
    print(f"  XZ projection shape: {template_xz.shape}")
    print(f"  YZ projection shape: {template_yz.shape}")
    print(f"  Total signal voxels: {np.sum(template_binary)}")
    print(f"  Signal fraction: {np.sum(template_binary) / np.prod(template_data.shape):.4f}")

if __name__ == "__main__":
    visualize_rotated_sample()