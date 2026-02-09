#!/usr/bin/env python3
"""
Script to identify which Janelia template space the TIFF files align to.
Based on dimensions, voxel sizes, and metadata from the README.
"""

import numpy as np
from pathlib import Path

# Template specifications from README
TEMPLATES = {
    'JRC2018_FEMALE_40x': {
        'dims': [1427, 664, 413],
        'voxdims': [0.44, 0.44, 0.44],
        'extent': [628.4, 292.0, 182.0]
    },
    'JRC2018_UNISEX_38um_iso_16bit': {
        'dims': [1652, 773, 456],
        'voxdims': [0.38, 0.38, 0.38],
        'extent': [628.4, 294.0, 173.0]
    },
    'JRC2018U': {
        'dims': [1211, 567, 175],
        'voxdims': [0.5189161, 0.5189161, 1.0],
        'extent': [628.4, 294.0, 175.0]
    },
    'JRCVNC2018U': {
        'dims': [660, 1290, 382],
        'voxdims': [0.4, 0.4, 0.4],
        'extent': [264.0, 516.0, 152.8]
    }
}

def analyze_tiff_for_template(filepath):
    """Analyze TIFF file to determine likely template alignment."""
    print(f"\nAnalyzing {filepath.name} for template identification:")

    try:
        import tifffile
        with tifffile.TiffFile(filepath) as tif:
            page = tif.pages[0]

            # Get ImageJ metadata
            imagej_meta = page.tags.get('ImageDescription', None)
            if imagej_meta and hasattr(imagej_meta, 'value'):
                meta_value = imagej_meta.value
                if isinstance(meta_value, bytes):
                    meta_str = meta_value.decode('utf-8', errors='ignore')
                else:
                    meta_str = str(meta_value)

                # Parse metadata
                metadata = {}
                for line in meta_str.split('\n'):
                    if '=' in line:
                        key, value = line.split('=', 1)
                        try:
                            metadata[key] = float(value)
                        except ValueError:
                            metadata[key] = value

                # Get dimensions
                if 'slices' in metadata:
                    z_slices = int(metadata['slices'])
                else:
                    z_slices = len(tif.pages) // 2  # Assume 2 channels

                spacing = metadata.get('spacing', 1.0)
                unit = metadata.get('unit', 'pixel')

                # Get XY resolution
                x_res = page.tags.get('XResolution', None)
                y_res = page.tags.get('YResolution', None)

                if x_res and y_res:
                    x_pixels_per_unit = x_res.value[0] / x_res.value[1]
                    y_pixels_per_unit = y_res.value[0] / y_res.value[1]

                    if unit == 'micron':
                        xy_voxel_size = 1.0 / x_pixels_per_unit  # microns per pixel
                    else:
                        xy_voxel_size = 1.0  # assume pixels
                else:
                    xy_voxel_size = 1.0  # default

                print(f"  Dimensions: 1024 x 1024 x {z_slices} voxels")
                print(f"  XY voxel size: {xy_voxel_size:.3f} μm")
                print(f"  Z spacing: {spacing:.3f} μm")
                print(f"  Unit: {unit}")

                # Calculate physical extent
                physical_x = 1024 * xy_voxel_size
                physical_y = 1024 * xy_voxel_size
                physical_z = z_slices * spacing

                print(f"  Physical extent: {physical_x:.1f} x {physical_y:.1f} x {physical_z:.1f} μm")

                # Compare to known templates
                print("  Comparing to known templates:")
                best_match = None
                best_score = float('inf')

                for template_name, template_info in TEMPLATES.items():
                    # Compare physical extents
                    template_extent = template_info['extent']
                    extent_diff = np.sqrt(
                        (physical_x - template_extent[0])**2 +
                        (physical_y - template_extent[1])**2 +
                        (physical_z - template_extent[2])**2
                    )

                    # Compare voxel sizes (XY only, since Z may vary)
                    template_voxdims = template_info['voxdims']
                    vox_diff = np.sqrt(
                        (xy_voxel_size - template_voxdims[0])**2 +
                        (xy_voxel_size - template_voxdims[1])**2
                    )

                    score = extent_diff + vox_diff * 100  # Weight voxel size more

                    print(f"    {template_name}: extent diff={extent_diff:.1f}, vox diff={vox_diff:.3f}, score={score:.1f}")

                    if score < best_score:
                        best_score = score
                        best_match = template_name

                print(f"  Best match: {best_match} (score: {best_score:.1f})")

                return {
                    'filename': filepath.name,
                    'dims': [1024, 1024, z_slices],
                    'voxdims': [xy_voxel_size, xy_voxel_size, spacing],
                    'extent': [physical_x, physical_y, physical_z],
                    'best_match': best_match,
                    'score': best_score
                }

    except Exception as e:
        print(f"  Error: {e}")
        return None

def main():
    """Main function."""
    images_dir = Path("Images")

    if not images_dir.exists():
        print(f"Images directory not found: {images_dir}")
        return

    tiff_files = []
    for root, dirs, files in os.walk(images_dir):
        for file in files:
            if file.lower().endswith(('.tif', '.tiff')):
                tiff_files.append(Path(root) / file)

    print(f"Analyzing {len(tiff_files)} TIFF files for template identification...")

    results = []
    for tiff_file in tiff_files:
        result = analyze_tiff_for_template(tiff_file)
        if result:
            results.append(result)

    # Summary
    print("\n=== SUMMARY ===")
    for result in results:
        print(f"{result['filename']}: {result['best_match']} (extent: {result['extent'][0]:.0f}x{result['extent'][1]:.0f}x{result['extent'][2]:.0f} μm)")

if __name__ == "__main__":
    import os
    main()