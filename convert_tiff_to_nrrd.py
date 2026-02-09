#!/usr/bin/env python3
"""
Script to convert TIFF files to NRRD format for use with navis and VFB tools.
This preserves the image data and metadata.
"""

import os
import numpy as np
import tifffile
from pathlib import Path
import nrrd

def convert_tiff_to_nrrd(tiff_path, output_dir=None):
    """Convert a TIFF file to NRRD format."""
    if output_dir is None:
        output_dir = tiff_path.parent

    output_path = output_dir / (tiff_path.stem + '.nrrd')

    print(f"Converting {tiff_path.name} to {output_path.name}")

    try:
        # Load the TIFF stack
        stack = tifffile.imread(tiff_path)
        print(f"  Loaded stack with shape: {stack.shape}")

        # Get metadata from first page
        with tifffile.TiffFile(tiff_path) as tif:
            page = tif.pages[0]

            # Parse ImageJ metadata
            imagej_meta = page.tags.get('ImageDescription', None)
            spacing = 1.0
            unit = 'pixel'

            if imagej_meta and hasattr(imagej_meta, 'value'):
                meta_value = imagej_meta.value
                if isinstance(meta_value, bytes):
                    meta_str = meta_value.decode('utf-8', errors='ignore')
                else:
                    meta_str = str(meta_value)

                # Parse metadata
                for line in meta_str.split('\n'):
                    if '=' in line:
                        key, value = line.split('=', 1)
                        if key == 'spacing':
                            try:
                                spacing = float(value)
                            except ValueError:
                                spacing = 1.0
                        elif key == 'unit':
                            unit = value

            # Get XY resolution
            x_res = page.tags.get('XResolution', None)
            y_res = page.tags.get('YResolution', None)

            if x_res and y_res and unit == 'micron':
                x_pixels_per_unit = x_res.value[0] / x_res.value[1]
                y_pixels_per_unit = y_res.value[0] / y_res.value[1]
                xy_spacing = 1.0 / x_pixels_per_unit  # microns per pixel
            else:
                xy_spacing = 1.0

            # Create NRRD header
            header = {
                'type': 'uint8',
                'dimension': len(stack.shape),
                'sizes': stack.shape[::-1],  # NRRD expects X Y Z order
                'space directions': [
                    [xy_spacing, 0, 0],
                    [0, xy_spacing, 0],
                    [0, 0, spacing]
                ],
                'space units': ['microns', 'microns', 'microns'],
                'space origin': [0, 0, 0],
                'endian': 'little',
                'encoding': 'gzip'
            }

            # Handle different stack shapes
            if len(stack.shape) == 4:  # Z, C, Y, X
                # For multi-channel, we might need to save channels separately
                # or combine them. For now, let's save as multi-component
                data_to_save = np.transpose(stack, (3, 2, 0, 1))  # X, Y, Z, C
                header['sizes'] = [stack.shape[3], stack.shape[2], stack.shape[0], stack.shape[1]]
                header['dimension'] = 4
                print(f"  Multi-channel data: {stack.shape[1]} channels")

            elif len(stack.shape) == 3:  # Z, Y, X
                data_to_save = np.transpose(stack, (2, 1, 0))  # X, Y, Z
                print("  Single channel data")

            else:  # 2D image
                data_to_save = stack.T  # X, Y
                header['dimension'] = 2
                header['sizes'] = stack.shape[::-1]
                header['space directions'] = [
                    [xy_spacing, 0],
                    [0, xy_spacing]
                ]
                print("  2D image")

            # Save as NRRD
            nrrd.write(str(output_path), data_to_save, header)
            print(f"  Saved to {output_path}")
            print(f"  NRRD shape: {data_to_save.shape}")
            print(f"  Voxel size: {xy_spacing:.3f} x {xy_spacing:.3f} x {spacing:.3f} μm")

            return output_path

    except Exception as e:
        print(f"  Error converting {tiff_path}: {e}")
        return None

def main():
    """Convert all TIFF files to NRRD format."""
    images_dir = Path("Images")
    output_dir = Path("nrrd_output")
    output_dir.mkdir(exist_ok=True)

    if not images_dir.exists():
        print(f"Images directory not found: {images_dir}")
        return

    tiff_files = []
    for root, dirs, files in os.walk(images_dir):
        for file in files:
            if file.lower().endswith(('.tif', '.tiff')):
                tiff_files.append(Path(root) / file)

    print(f"Converting {len(tiff_files)} TIFF files to NRRD format...")

    converted_files = []
    for tiff_file in tiff_files:
        nrrd_file = convert_tiff_to_nrrd(tiff_file, output_dir)
        if nrrd_file:
            converted_files.append(nrrd_file)

    print(f"\nConversion complete! {len(converted_files)} files converted.")
    print(f"NRRD files saved to: {output_dir}")

if __name__ == "__main__":
    main()