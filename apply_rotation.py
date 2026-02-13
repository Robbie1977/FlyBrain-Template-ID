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

    # Load data and metadata
    with tifffile.TiffFile(str(tiff_file)) as tif:
        data = tif.asarray()
        metadata = {}
        
        # Preserve ImageJ metadata
        if hasattr(tif, 'imagej_metadata') and tif.imagej_metadata:
            metadata['imagej'] = tif.imagej_metadata
            
        # Preserve OME metadata
        if hasattr(tif, 'ome_metadata') and tif.ome_metadata:
            metadata['ome'] = tif.ome_metadata

    if data.ndim == 4:
        # Multichannel: [Z, Channels, Y, X] — rotate each channel independently
        num_channels = data.shape[1]
        # Rotate each channel and collect results
        rotated_channels = []
        for ch in range(num_channels):
            rotated_channels.append(apply_rotations(data[:, ch, :, :], rotations))
        # Reconstruct 4D array: [new_Z, Channels, new_Y, new_X]
        new_z, new_y, new_x = rotated_channels[0].shape
        rotated = np.empty((new_z, num_channels, new_y, new_x), dtype=data.dtype)
        for ch in range(num_channels):
            rotated[:, ch, :, :] = rotated_channels[ch]
        tifffile.imwrite(str(tiff_file), rotated.astype(data.dtype), metadata=metadata)
    else:
        # Single channel 3D
        rotated = apply_rotations(data, rotations)
        tifffile.imwrite(str(tiff_file), rotated.astype(data.dtype), metadata=metadata)

    # Update voxel sizes in orientations.json
    update_voxel_sizes_after_rotation(image_path, rotations)

def update_voxel_sizes_after_rotation(image_path, rotations):
    """Update voxel sizes in orientations.json to reflect axis permutations from rotations."""
    import json
    from pathlib import Path
    
    orientations_file = Path("orientations.json")
    if not orientations_file.exists():
        return
    
    # Load orientations
    with open(orientations_file, 'r') as f:
        data = json.load(f)
    
    if image_path not in data:
        return
    
    entry = data[image_path]
    voxel_sizes = entry.get('image_info', {}).get('voxel_sizes', [0.5, 0.5, 0.5])
    if voxel_sizes == [0.5, 0.5, 0.5]:
        # Don't update if we have default values (they might be wrong anyway)
        return
    
    # Data layout: [Z, Height, Width] (axes 0, 1, 2)
    # Voxel sizes correspond to [Z, Y, X] (voxel_sizes[0], voxel_sizes[1], voxel_sizes[2])
    
    axis_mapping = {
        'x': (0, 1),  # Z↔Height (Y axis)
        'y': (0, 2),  # Z↔Width (X axis)  
        'z': (1, 2),  # Height↔Width (Y↔X axes)
    }
    
    # Apply rotations in order (x, y, z)
    current_permutation = [0, 1, 2]  # [Z, Y, X]
    
    for axis_name, degrees in rotations.items():
        if degrees == 0:
            continue
        
        if degrees not in [90, 180, 270]:
            continue
            
        axes = axis_mapping[axis_name]
        k = degrees // 90
        
        # For each 90° rotation, swap the axes
        for _ in range(k):
            # Swap the two axes
            temp = current_permutation[axes[0]]
            current_permutation[axes[0]] = current_permutation[axes[1]]
            current_permutation[axes[1]] = temp
    
    # Reorder voxel sizes according to final permutation
    new_voxel_sizes = [voxel_sizes[i] for i in current_permutation]
    
    # Update orientations.json
    entry['image_info']['voxel_sizes'] = new_voxel_sizes
    with open(orientations_file, 'w') as f:
        json.dump(data, f, indent=2)
    
    print(f"Updated voxel sizes for {image_path}: {voxel_sizes} -> {new_voxel_sizes}")
