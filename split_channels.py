#!/usr/bin/env python3
"""
Split multi-channel NRRDs into separate background and signal files.
"""

import nrrd
from pathlib import Path

nrrd_dir = Path('nrrd_output')
channels_dir = Path('channels')
channels_dir.mkdir(exist_ok=True)

for nrrd_file in nrrd_dir.glob('*.nrrd'):
    data, header = nrrd.read(str(nrrd_file))
    if data.ndim == 4 and data.shape[3] == 2:
        base = nrrd_file.stem
        
        # Signal channel (0)
        signal_data = data[:, :, :, 0]
        signal_header = header.copy()
        signal_header['dimension'] = 3
        signal_header['space dimension'] = 3
        signal_header['sizes'] = signal_data.shape[::-1]  # NRRD expects X Y Z
        signal_header['space directions'] = header['space directions']
        signal_header['space units'] = header['space units']
        signal_header['space origin'] = header.get('space origin', [0, 0, 0])
        
        signal_file = channels_dir / f"{base}_signal.nrrd"
        nrrd.write(str(signal_file), signal_data, signal_header)
        print(f"Created {signal_file}")
        
        # Background channel (1)
        bg_data = data[:, :, :, 1]
        bg_header = signal_header.copy()
        bg_file = channels_dir / f"{base}_background.nrrd"
        nrrd.write(str(bg_file), bg_data, bg_header)
        print(f"Created {bg_file}")
    else:
        print(f"Skipping {nrrd_file}, not 4D with 2 channels")