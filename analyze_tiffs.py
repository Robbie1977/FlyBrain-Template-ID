#!/usr/bin/env python3
"""
Script to analyze TIFF files from fly brain imaging data.
This script loads TIFF stacks and extracts metadata to help identify
the template space they align to.
"""

import os
import numpy as np
import tifffile
from pathlib import Path

def analyze_tiff_file(filepath):
    """Analyze a single TIFF file and extract metadata."""
    print(f"\nAnalyzing: {filepath}")

    try:
        # Load the TIFF file
        with tifffile.TiffFile(filepath) as tif:
            # Get basic info
            print(f"  Number of pages: {len(tif.pages)}")

            # Get dimensions
            page = tif.pages[0]
            shape = page.shape
            print(f"  Shape: {shape}")

            # Get data type
            dtype = page.dtype
            print(f"  Data type: {dtype}")

            # Get metadata if available
            if hasattr(page, 'tags'):
                # Look for ImageJ metadata
                imagej_meta = page.tags.get('ImageDescription', None)
                if imagej_meta and hasattr(imagej_meta, 'value'):
                    meta_value = imagej_meta.value
                    if isinstance(meta_value, bytes):
                        meta_str = meta_value.decode('utf-8', errors='ignore')
                    else:
                        meta_str = str(meta_value)
                    print(f"  ImageJ metadata: {meta_str[:200]}...")

                # Look for resolution
                x_resolution = page.tags.get('XResolution', None)
                y_resolution = page.tags.get('YResolution', None)
                if x_resolution and y_resolution:
                    x_res = x_resolution.value[0] / x_resolution.value[1]
                    y_res = y_resolution.value[0] / y_resolution.value[1]
                    print(f"  Resolution: {x_res} x {y_res} pixels per unit")

            # Try to load the full stack
            try:
                stack = tifffile.imread(filepath)
                print(f"  Full stack shape: {stack.shape}")
                print(f"  Data range: {stack.min()} - {stack.max()}")
                print(f"  Data type: {stack.dtype}")

                # For multi-channel data, check if it's RGB or separate channels
                if len(stack.shape) == 4:  # Z, Y, X, C
                    print(f"  Multi-channel data with {stack.shape[3]} channels")
                elif len(stack.shape) == 3 and stack.shape[2] == 3:  # Y, X, RGB
                    print("  RGB image")

            except Exception as e:
                print(f"  Could not load full stack: {e}")

    except Exception as e:
        print(f"  Error analyzing file: {e}")

def main():
    """Main function to analyze all TIFF files in the Images directory."""
    images_dir = Path("Images")

    if not images_dir.exists():
        print(f"Images directory not found: {images_dir}")
        return

    tiff_files = []
    for root, dirs, files in os.walk(images_dir):
        for file in files:
            if file.lower().endswith(('.tif', '.tiff')):
                tiff_files.append(Path(root) / file)

    print(f"Found {len(tiff_files)} TIFF files")

    for tiff_file in tiff_files:
        analyze_tiff_file(tiff_file)

if __name__ == "__main__":
    main()