#!/usr/bin/env python3
"""
Rotate all channel files 180° around Y-axis to correct orientation.
"""

import sys
sys.path.append('.')
from rotate_nrrd import rotate_nrrd_180_y_axis
from pathlib import Path

channels_dir = Path('channels')

for bg_file in channels_dir.glob('*_background.nrrd'):
    base = bg_file.stem.replace('_background', '')
    output_bg = channels_dir / f"{base}_background_rotated.nrrd"
    rotate_nrrd_180_y_axis(str(bg_file), str(output_bg))
    
    sig_file = channels_dir / f"{base}_signal.nrrd"
    if sig_file.exists():
        output_sig = channels_dir / f"{base}_signal_rotated.nrrd"
        rotate_nrrd_180_y_axis(str(sig_file), str(output_sig))