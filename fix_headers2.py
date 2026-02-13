#!/usr/bin/env python3
import nrrd
from pathlib import Path

channels_dir = Path('channels')
for bg_file in channels_dir.glob('*_background.nrrd'):
    base = bg_file.stem.replace('_background', '')
    orig_file = Path('nrrd_output') / (base + '.nrrd')
    if orig_file.exists():
        _, orig_header = nrrd.read(str(orig_file))
        data_bg, header_bg = nrrd.read(str(bg_file))
        if 'space directions' not in header_bg:
            header_bg['space directions'] = orig_header['space directions']
            header_bg['space units'] = orig_header['space units']
            header_bg['space origin'] = orig_header.get('space origin', [0, 0, 0])
            nrrd.write(str(bg_file), data_bg, header_bg)
            print('Fixed', bg_file.name)
        sig_file = channels_dir / (base + '_signal.nrrd')
        if sig_file.exists():
            data_sig, header_sig = nrrd.read(str(sig_file))
            if 'space directions' not in header_sig:
                header_sig['space directions'] = orig_header['space directions']
                header_sig['space units'] = orig_header['space units']
                header_sig['space origin'] = orig_header.get('space origin', [0, 0, 0])
                nrrd.write(str(sig_file), data_sig, header_sig)
                print('Fixed', sig_file.name)