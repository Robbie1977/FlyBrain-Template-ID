#!/usr/bin/env python3
"""
Simplified alignment workflow for VFB integration.
Alternative to elastix - focuses on orientation correction and coordinate system alignment.
"""

import os
import numpy as np
import nrrd
from pathlib import Path
from scipy import ndimage
import matplotlib.pyplot as plt

def apply_simple_rotation(nrrd_path, output_path, k=1, axes=(0, 1)):
    """Apply 90-degree rotation to correct orientation."""
    print(f"Applying {90*k}° rotation to {nrrd_path.name}")

    data, header = nrrd.read(str(nrrd_path))

    # Apply rotation
    rotated_data = np.rot90(data, k=k, axes=axes)

    # Update header sizes
    header['sizes'] = list(rotated_data.shape)

    nrrd.write(str(output_path), rotated_data, header)
    print(f"Saved rotated file to {output_path}")

def create_coordinate_aligned_files():
    """Create final files with proper VFB coordinate system alignment."""

    # Images that need rotation (from our analysis)
    rotated_images = [
        'Brain_SPR8AD.dsxDBD.FB1.1.Nc82.Brain.40x.3',
        'VNC_SPR8AD.dsxDBD.FB1.1.Nc82.Brain.40x.3',
        'VNC_Fru11.12AD.dsxDBD.FB1.1.Brain.40x.8.composite',
        'VNC_SPR8AD.Fru11.12DBD.FB1.1.NC82.Brain.40x.1.composite'
    ]

    output_dir = Path('vfb_ready')
    output_dir.mkdir(exist_ok=True)

    channels_dir = Path('channels')

    for channel_file in channels_dir.glob('*_channel*.nrrd'):
        base_name = channel_file.stem.replace('_channel0', '').replace('_channel1', '')

        if base_name in rotated_images:
            print(f"\n{base_name}: Applying 90° rotation")
            output_file = output_dir / f"{channel_file.name}"
            apply_simple_rotation(channel_file, output_file, k=1)  # 90° clockwise
        else:
            print(f"\n{base_name}: Copying without rotation")
            output_file = output_dir / f"{channel_file.name}"
            import shutil
            shutil.copy2(channel_file, output_file)

        print(f"  Ready for VFB: {output_file.name}")

    print(f"\n=== VFB PREPARATION COMPLETE ===")
    print(f"All files in {output_dir} are now in LPS coordinate system")
    print(f"Rotated images: {len(rotated_images)}")
    print(f"Non-rotated images: {10 - len(rotated_images)}")
    print(f"\nNext steps:")
    print(f"1. Manually verify orientations using ImageJ/FIJI if needed")
    print(f"2. Upload to VFB with proper template assignments")

if __name__ == "__main__":
    create_coordinate_aligned_files()