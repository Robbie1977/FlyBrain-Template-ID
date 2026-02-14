#!/usr/bin/env python3
"""
Split multi-channel NRRDs into separate background and signal files.
Usage: python3 split_channels.py [image_base]
If image_base is provided, only process that specific image.
Otherwise, process all NRRD files in nrrd_output directory.
"""

import nrrd
from pathlib import Path
import sys

nrrd_dir = Path('nrrd_output')
channels_dir = Path('channels')
channels_dir.mkdir(exist_ok=True)

# Check if specific image base is provided
specific_image = sys.argv[1] if len(sys.argv) > 1 else None

files_to_process = []
if specific_image:
    # Process only the specific image
    nrrd_file = nrrd_dir / f"{specific_image}.nrrd"
    if nrrd_file.exists():
        files_to_process = [nrrd_file]
    else:
        print(f"NRRD file not found: {nrrd_file}")
        sys.exit(1)
else:
    # Process all NRRD files
    files_to_process = list(nrrd_dir.glob('*.nrrd'))

for nrrd_file in files_to_process:
    data, header = nrrd.read(str(nrrd_file))
    if data.ndim == 4 and data.shape[3] == 2:
        base = nrrd_file.stem
        
        # Signal channel (0)
        signal_data = data[:, :, :, 0].transpose(2, 1, 0)  # Transpose to X Y Z order
        signal_header = header.copy()
        signal_header['dimension'] = 3
        signal_header['space dimension'] = 3
        signal_header['sizes'] = signal_data.shape  # Now matches data shape
        signal_header['space directions'] = header['space directions']
        signal_header['space units'] = header['space units']
        signal_header['space origin'] = header.get('space origin', [0, 0, 0])
        
        signal_file = channels_dir / f"{base}_signal.nrrd"
        nrrd.write(str(signal_file), signal_data, signal_header)
        print(f"Created {signal_file}")
        
        # Background channel (1)
        bg_data = data[:, :, :, 1].transpose(2, 1, 0)  # Transpose to X Y Z order
        bg_header = signal_header.copy()
        bg_file = channels_dir / f"{base}_background.nrrd"
        nrrd.write(str(bg_file), bg_data, bg_header)
        print(f"Created {bg_file}")
    else:
        print(f"Skipping {nrrd_file}, not 4D with 2 channels")