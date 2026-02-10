#!/usr/bin/env python3
"""
Rotate NRRD file 90 degrees counterclockwise in XY plane.
"""

import numpy as np
import nrrd

def rotate_nrrd_90_left(input_path, output_path):
    # Read the NRRD file
    data, header = nrrd.read(input_path)
    
    # Rotate 90 degrees counterclockwise in XY plane (axes 0 and 1)
    rotated_data = np.rot90(data, k=1, axes=(0, 1))
    
    # The space directions might need to be updated for rotation
    # For 90 deg CCW in XY: swap and negate space directions[0] and [1]
    if 'space directions' in header:
        sd = header['space directions']
        # Original: sd[0] is X, sd[1] is Y, sd[2] is Z
        # After rot90 CCW: X becomes old Y, Y becomes -old X
        new_sd = [
            sd[1],  # new X = old Y
            [-x for x in sd[0]],  # new Y = -old X
            sd[2]   # Z unchanged
        ]
        header['space directions'] = new_sd
    
    # Write the rotated data
    nrrd.write(output_path, rotated_data, header)
    print(f"Rotated {input_path} and saved to {output_path}")

if __name__ == "__main__":
    input_file = "nrrd_output/channels/Fru11.12AD.dsxDBD.FB1.1.Brain.40x.8.composite_channel1.nrrd"
    output_file = "nrrd_output/channels/Fru11.12AD.dsxDBD.FB1.1.Brain.40x.8.composite_channel1_rotated.nrrd"
    rotate_nrrd_90_left(input_file, output_file)