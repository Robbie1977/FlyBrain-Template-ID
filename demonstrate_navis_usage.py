#!/usr/bin/env python3
"""
Script to demonstrate loading and working with the converted NRRD files using navis.
This shows how to handle multi-channel microscopy data and prepare for VFB integration.
"""

import os
import numpy as np
import navis
import nrrd
from pathlib import Path

def load_nrrd_with_navis(nrrd_path):
    """Load NRRD file and demonstrate navis compatibility."""
    print(f"\nLoading {nrrd_path.name}:")

    try:
        # Load NRRD file
        data, header = nrrd.read(str(nrrd_path))
        print(f"  Data shape: {data.shape}")
        print(f"  Data type: {data.dtype}")
        print(f"  Voxel size: {header.get('space directions', 'unknown')}")

        # Handle different data shapes
        if len(data.shape) == 4:  # Multi-channel volume (X, Y, Z, C)
            print(f"  Multi-channel data with {data.shape[3]} channels")
            print("  Note: Multi-channel volumes require special handling in navis")
            print("  Typically, channels represent: 0=signal (e.g., Fru), 1=reference (e.g., NC82)")

            # Show channel info without creating navis objects
            for channel in range(data.shape[3]):
                channel_data = data[..., channel]
                print(f"    Channel {channel}: {channel_data.shape}, range: {channel_data.min()}-{channel_data.max()}")

        elif len(data.shape) == 3:  # Single channel volume (X, Y, Z)
            print("  Single channel volume")
            print(f"    Range: {data.min()}-{data.max()}")

            # Try to create navis volume
            try:
                volume = navis.Volume(data.astype(np.float32), name=nrrd_path.stem, units='microns')
                print("    Successfully created navis Volume object")
                return [volume]
            except Exception as e:
                print(f"    Could not create navis Volume: {e}")

        elif len(data.shape) == 2:  # 2D image
            print("  2D image (likely corrupted or single slice)")

        print("  NRRD file is ready for navis/flybrains processing")
        return []

    except Exception as e:
        print(f"  Error loading {nrrd_path}: {e}")
        return []

def demonstrate_template_alignment(volume, template_name='JRC2018U'):
    """Demonstrate how to align volume to template space."""
    print(f"\nDemonstrating template alignment for {volume.name}:")

    try:
        import flybrains

        # Get template info
        if template_name == 'JRC2018U':
            template = flybrains.JRC2018U
        elif template_name == 'JRCVNC2018U':
            template = flybrains.JRCVNC2018U
        else:
            print(f"  Unknown template: {template_name}")
            return

        print(f"  Target template: {template.name}")
        print(f"  Template dimensions: {template.dims}")
        print(f"  Template voxel size: {template.voxdims}")

        # Note: Actual transformation would require registration
        # This is just a demonstration of the workflow
        print("  Note: Actual registration would require landmark-based or intensity-based alignment")
        print("  For VFB integration, volumes should be transformed to match template coordinate system")

    except ImportError:
        print("  flybrains not available for template alignment demo")

def main():
    """Demonstrate loading and working with NRRD files."""
    nrrd_dir = Path("nrrd_output")

    if not nrrd_dir.exists():
        print(f"NRRD directory not found: {nrrd_dir}")
        return

    nrrd_files = list(nrrd_dir.glob("*.nrrd"))
    print(f"Found {len(nrrd_files)} NRRD files")

    all_volumes = []
    for nrrd_file in nrrd_files:
        volumes = load_nrrd_with_navis(nrrd_file)
        all_volumes.extend(volumes)

        # Demonstrate template alignment for first volume
        if volumes:
            if 'VNC' in nrrd_file.name.lower():
                demonstrate_template_alignment(volumes[0], 'JRCVNC2018U')
            else:
                demonstrate_template_alignment(volumes[0], 'JRC2018U')

    print(f"\n=== SUMMARY ===")
    print(f"Loaded {len(all_volumes)} volume objects total")
    for vol in all_volumes:
        print(f"  {vol.name}: {vol.shape} voxels")

    print("\n=== NEXT STEPS ===")
    print("1. Register volumes to template spaces using landmarks or image registration")
    print("2. Transform coordinates to match VFB template coordinate system")
    print("3. Export in VFB-compatible format (NRRD with proper headers)")
    print("4. Upload to VFB or use with navis analysis tools")

if __name__ == "__main__":
    main()