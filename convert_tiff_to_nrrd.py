#!/usr/bin/env python3
"""
Convert TIFF files directly to per-channel NRRD files (signal + background)
in [X, Y, Z] order with correct space directions and LPS space.

This replaces the old two-step convert + split_channels workflow.
The original TIFF is NEVER modified.

Output:
    channels/{base}_signal.nrrd      — signal channel in [X, Y, Z]
    channels/{base}_background.nrrd  — background channel in [X, Y, Z]

Space directions are set so that:
    axis 0 (X) → [vx, 0, 0]
    axis 1 (Y) → [0, vy, 0]
    axis 2 (Z) → [0, 0, vz]

where vx/vy come from TIFF XResolution/YResolution and vz from ImageJ
'spacing' metadata.
"""

import os
import sys
import json
import numpy as np
import tifffile
from pathlib import Path
import nrrd

ORIENTATIONS_FILE = Path("orientations.json")
DEFAULT_VOXEL_SIZE = 0.5  # µm fallback


def _extract_voxel_sizes(tif):
    """Extract [vx, vy, vz] in µm from TIFF metadata.

    Returns pixel sizes in the order [X-spacing, Y-spacing, Z-spacing].
    """
    vx = vy = vz = None

    try:
        ij = tif.imagej_metadata
        if ij:
            if 'spacing' in ij:
                vz = float(ij['spacing'])

            page = tif.pages[0]
            tags = page.tags
            if 'XResolution' in tags:
                xr = tags['XResolution'].value
                if isinstance(xr, tuple) and xr[0] > 0:
                    vx = xr[1] / xr[0]  # µm per pixel
            if 'YResolution' in tags:
                yr = tags['YResolution'].value
                if isinstance(yr, tuple) and yr[0] > 0:
                    vy = yr[1] / yr[0]

            unit = ij.get('unit', 'micron')
            if unit and unit.lower() in ('nm', 'nanometer', 'nanometers'):
                if vx: vx /= 1000.0
                if vy: vy /= 1000.0
                if vz: vz /= 1000.0
    except Exception:
        pass

    # OME fallback
    if vx is None:
        try:
            if hasattr(tif, 'ome_metadata') and tif.ome_metadata:
                import xml.etree.ElementTree as ET
                root = ET.fromstring(tif.ome_metadata)
                ns = {'ome': root.tag.split('}')[0].strip('{')} if '}' in root.tag else {}
                pixels = root.find('.//ome:Pixels', ns) if ns else root.find('.//Pixels')
                if pixels is not None:
                    if pixels.get('PhysicalSizeX'):
                        vx = float(pixels.get('PhysicalSizeX'))
                    if pixels.get('PhysicalSizeY'):
                        vy = float(pixels.get('PhysicalSizeY'))
                    if pixels.get('PhysicalSizeZ'):
                        vz = float(pixels.get('PhysicalSizeZ'))
        except Exception:
            pass

    if vx is None: vx = DEFAULT_VOXEL_SIZE
    if vy is None: vy = vx
    if vz is None: vz = DEFAULT_VOXEL_SIZE

    return [vx, vy, vz]


def _get_bg_channel(image_base):
    """Read background channel assignment from orientations.json (default 1)."""
    if ORIENTATIONS_FILE.exists():
        try:
            data = json.loads(ORIENTATIONS_FILE.read_text())
            for key, val in data.items():
                if image_base in key:
                    mc = val.get('manual_corrections', {})
                    if 'background_channel' in mc:
                        return int(mc['background_channel'])
                    return val.get('image_info', {}).get('background_channel', 1)
        except Exception:
            pass
    return 1


def _make_nrrd_header(data, vx, vy, vz):
    """Build a canonical NRRD header for 3D data in [X, Y, Z] with LPS space."""
    return {
        'type': str(data.dtype),
        'dimension': 3,
        'space': 'left-posterior-superior',
        'sizes': list(data.shape),
        'space directions': [
            [vx, 0, 0],
            [0, vy, 0],
            [0, 0, vz],
        ],
        'space units': ['microns', 'microns', 'microns'],
        'space origin': [0.0, 0.0, 0.0],
        'endian': 'little',
        'encoding': 'gzip',
    }


def convert_and_split(image_base):
    """Convert a TIFF to per-channel NRRDs in [X, Y, Z] order.

    Returns (signal_path, background_path) on success, raises on failure.
    """
    channels_dir = Path("channels")
    channels_dir.mkdir(exist_ok=True)

    # --- Locate TIFF ---
    images_dir = Path("Images")
    tiff_file = None
    for root, _dirs, files in os.walk(images_dir):
        for f in files:
            if f.lower().endswith(('.tif', '.tiff')) and image_base in f:
                tiff_file = Path(root) / f
                break
        if tiff_file:
            break

    if tiff_file is None or not tiff_file.exists():
        raise FileNotFoundError(f"TIFF not found for {image_base}")

    print(f"Converting {tiff_file.name} → channel NRRDs")

    # --- Load TIFF ---
    with tifffile.TiffFile(str(tiff_file)) as tif:
        stack = tif.asarray(series=0)
        vx, vy, vz = _extract_voxel_sizes(tif)

    print(f"  TIFF shape: {stack.shape}  voxel: vx={vx:.4f} vy={vy:.4f} vz={vz:.4f} µm")

    bg_channel = _get_bg_channel(image_base)

    # --- Extract channels ---
    if stack.ndim == 4:
        # Typical: [Z, C, Y, X]
        num_channels = stack.shape[1]
        sig_idx = 1 - bg_channel if num_channels == 2 else 0
        bg_3d = stack[:, bg_channel, :, :]   # [Z, Y, X]
        sig_3d = stack[:, sig_idx, :, :]     # [Z, Y, X]
        print(f"  Multi-channel ({num_channels}): bg={bg_channel} sig={sig_idx}")
    elif stack.ndim == 3:
        # Single channel: [Z, Y, X]
        bg_3d = stack
        sig_3d = stack
        print("  Single channel")
    else:
        raise ValueError(f"Unexpected TIFF shape: {stack.shape}")

    # --- Transpose from [Z, Y, X] → [X, Y, Z] for NRRD standard ---
    bg_xyz = np.transpose(bg_3d, (2, 1, 0))    # [X, Y, Z]
    sig_xyz = np.transpose(sig_3d, (2, 1, 0))  # [X, Y, Z]

    # Space directions: axis 0 = X → vx, axis 1 = Y → vy, axis 2 = Z → vz
    bg_header = _make_nrrd_header(bg_xyz, vx, vy, vz)
    sig_header = _make_nrrd_header(sig_xyz, vx, vy, vz)

    # --- Write channel NRRDs ---
    bg_path = channels_dir / f"{image_base}_background.nrrd"
    sig_path = channels_dir / f"{image_base}_signal.nrrd"

    nrrd.write(str(bg_path), bg_xyz, bg_header)
    print(f"  Wrote {bg_path}  shape={bg_xyz.shape}")

    nrrd.write(str(sig_path), sig_xyz, sig_header)
    print(f"  Wrote {sig_path}  shape={sig_xyz.shape}")

    print(f"  Space directions: [[{vx},0,0],[0,{vy},0],[0,0,{vz}]]")
    print(f"  Space: left-posterior-superior")

    return str(sig_path), str(bg_path)


def main():
    """Convert TIFF(s) to channel NRRDs.

    Usage:
        python convert_tiff_to_nrrd.py <image_base>   # single image
        python convert_tiff_to_nrrd.py                 # all images
    """
    specific_image = sys.argv[1] if len(sys.argv) > 1 else None

    if specific_image:
        try:
            sig, bg = convert_and_split(specific_image)
            print(f"\nConversion complete: {specific_image}")
            print(f"  Signal:     {sig}")
            print(f"  Background: {bg}")
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        images_dir = Path("Images")
        if not images_dir.exists():
            print("Images directory not found")
            sys.exit(1)

        tiff_files = []
        for root, _dirs, files in os.walk(images_dir):
            for f in files:
                if f.lower().endswith(('.tif', '.tiff')):
                    tiff_files.append(Path(root) / f)

        print(f"Converting {len(tiff_files)} TIFF files to channel NRRDs...")
        converted = 0
        for tiff_file in tiff_files:
            base = tiff_file.stem
            try:
                convert_and_split(base)
                converted += 1
            except Exception as e:
                print(f"  FAILED {base}: {e}")

        print(f"\nDone: {converted}/{len(tiff_files)} converted.")


if __name__ == "__main__":
    main()