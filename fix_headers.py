#!/usr/bin/env python3
import nrrd
from pathlib import Path

# Get all background files
channels_dir = Path('channels')
for bg_file in channels_dir.glob('*_background.nrrd'):
    base = bg_file.stem.replace('_background', '')
    orig_file = Path('nrrd_output') / (base + '.nrrd')
    
    if orig_file.exists():
        # Read original header
        _, orig_header = nrrd.read(str(orig_file))
        
        # Read background
        data_bg, header_bg = nrrd.read(str(bg_file))
        
        # Add space info
        header_bg['space directions'] = orig_header['space directions']
        header_bg['space units'] = orig_header['space units']
        header_bg['space origin'] = orig_header.get('space origin', [0, 0, 0])
        
        # Write back
        nrrd.write(str(bg_file), data_bg, header_bg)
        print(f'Fixed {bg_file}')
        
        # Same for signal
        sig_file = bg_file.with_name(base + '_signal.nrrd')
        if sig_file.exists():
            data_sig, header_sig = nrrd.read(str(sig_file))
            header_sig['space directions'] = orig_header['space directions']
            header_sig['space units'] = orig_header['space units']
            header_sig['space origin'] = orig_header.get('space origin', [0, 0, 0])
            nrrd.write(str(sig_file), data_sig, header_sig)
            print(f'Fixed {sig_file}')