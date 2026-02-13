#!/usr/bin/env python3
"""
Quick VNC anatomical analysis for orientation detection.
Focuses on identifying major neuropil regions with higher threshold.
"""

import numpy as np
import nrrd
from scipy import ndimage
from pathlib import Path

def quick_vnc_analysis(filename):
    print(f"\n=== Quick VNC Analysis: {Path(filename).name} ===")

    # Load data
    data, header = nrrd.read(filename)
    print(f"Shape: {data.shape}")

    # Get voxel sizes
    vox_sizes = [header['space directions'][i][i] for i in range(3)]
    print(f"Voxel sizes: X={vox_sizes[0]:.3f}, Y={vox_sizes[1]:.3f}, Z={vox_sizes[2]:.3f}")

    # Use higher threshold to avoid noise (around 50 as suggested)
    threshold = 50  # Much higher than the 75th percentile
    print(f"Signal threshold: {threshold}")
    signal_mask = data > threshold

    # Sample every 4th voxel in each dimension to speed up processing
    sampled_mask = signal_mask[::4, ::4, ::4]
    print(f"Sampled shape: {sampled_mask.shape}")

    # Get connected components on sampled data
    labeled_mask, num_features = ndimage.label(sampled_mask)
    print(f"Number of connected components (sampled): {num_features}")

    if num_features == 0:
        print("No components found - try lower threshold")
        return None

    # Analyze component sizes and positions
    component_sizes = []
    component_centers = []

    for i in range(1, num_features + 1):
        component_mask = labeled_mask == i
        size = np.sum(component_mask)
        component_sizes.append(size)

        # Get center of mass (scale back to original coordinates)
        center = ndimage.center_of_mass(component_mask)
        # Scale back to original voxel coordinates
        original_center = [c * 4 for c in center]
        component_centers.append(original_center)

    # Sort by size (largest first)
    sorted_indices = np.argsort(component_sizes)[::-1]
    component_sizes = [component_sizes[i] for i in sorted_indices]
    component_centers = [component_centers[i] for i in sorted_indices]

    print(f"\nTop 10 component sizes: {component_sizes[:10]}")

    # Convert centers to physical coordinates
    physical_centers = []
    for center in component_centers[:10]:  # Top 10 components
        phys_center = [c * vs for c, vs in zip(center, vox_sizes)]
        physical_centers.append(phys_center)

    print("\nTop component centers (X, Y, Z μm):")
    for i, center in enumerate(physical_centers):
        print(".1f")

    # Analyze Z-distribution (dorsal-ventral)
    z_coords = [center[2] for center in physical_centers[:10]]
    if len(z_coords) > 1:
        z_range = max(z_coords) - min(z_coords)
        print(f"\nZ-coordinate range of top components: {z_range:.1f} μm")

        # Look for clustering patterns
        z_median = np.median(z_coords)
        components_superior = sum(1 for z in z_coords if z > z_median)
        components_inferior = sum(1 for z in z_coords if z < z_median)

        print(f"Components above median Z: {components_superior}")
        print(f"Components below median Z: {components_inferior}")

        # Expected pattern: 6 leg spheres + abdominal neuromere (7+ total major components)
        # With tight packing on superior side
        if num_features >= 5 and components_superior >= 3:
            print("✓ POTENTIAL CORRECT ORIENTATION: Multiple components with superior clustering")
        else:
            print("✗ LIKELY INCORRECT ORIENTATION: Different component pattern")

    return {
        'num_components': num_features,
        'top_sizes': component_sizes[:10],
        'z_range': z_range if len(z_coords) > 1 else 0,
        'superior_components': components_superior if len(z_coords) > 1 else 0,
        'inferior_components': components_inferior if len(z_coords) > 1 else 0
    }

if __name__ == "__main__":
    # Analyze the specific VNC sample
    result = quick_vnc_analysis("channels/VNC_SPR8AD.Fru11.12DBD.FB1.1.NC82.Brain.40x.1.composite_channel0.nrrd")

    if result:
        print("\n=== Analysis Summary ===")
        print(f"Components found: {result['num_components']}")
        print(f"Z distribution range: {result['z_range']:.1f} μm")
        print(f"Superior clustering: {result['superior_components']} components")
        print(f"Inferior components: {result['inferior_components']} components")