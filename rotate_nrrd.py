#!/usr/bin/env python3
"""
Rotate NRRD files by various angles around different axes.
"""

import numpy as np
import nrrd

def rotate_nrrd_180_y_axis(input_path, output_path):
    """Rotate NRRD file 180 degrees around Y-axis."""
    # Read the NRRD file
    data, header = nrrd.read(input_path)

    # Rotate 180 degrees around Y-axis (flip X and Z axes)
    rotated_data = np.rot90(data, k=2, axes=(0, 2))  # 180° = 2 x 90°

    # Update space directions for 180° rotation around Y
    # For 180° around Y: negate X and Z directions
    if 'space directions' in header:
        sd = header['space directions']
        new_sd = [
            [-x for x in sd[0]],  # negate X
            sd[1],  # Y unchanged
            [-x for x in sd[2]]   # negate Z
        ]
        header['space directions'] = new_sd

    # Write the rotated data
    nrrd.write(output_path, rotated_data, header)
    print(f"Rotated {input_path} 180° around Y-axis and saved to {output_path}")

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

def rotate_nrrd_180_z_axis(input_path, output_path):
    """Rotate NRRD file 180 degrees around Z-axis."""
    # Read the NRRD file
    data, header = nrrd.read(input_path)

    # Rotate 180 degrees around Z-axis (flip X and Y axes)
    rotated_data = np.rot90(data, k=2, axes=(0, 1))  # 180° = 2 x 90°

    # Update space directions for 180° rotation around Z
    # For 180° around Z: negate X and Y directions
    if 'space directions' in header:
        sd = header['space directions']
        new_sd = [
            [-x for x in sd[0]],  # negate X
            [-x for x in sd[1]],  # negate Y
            sd[2]   # Z unchanged
        ]
        header['space directions'] = new_sd

    # Write the rotated data
    nrrd.write(output_path, rotated_data, header)
    print(f"Rotated {input_path} 180° around Z-axis and saved to {output_path}")

def flip_nrrd_axis(input_path, output_path, axis):
    """Flip NRRD file along specified axis (0=X, 1=Y, 2=Z)."""
    data, header = nrrd.read(input_path)
    
    flipped_data = np.flip(data, axis=axis)
    
    # Update space directions: negate the direction for the flipped axis
    if 'space directions' in header:
        sd = header['space directions']
        new_sd = sd.copy()
        new_sd[axis] = [-x for x in sd[axis]]
        header['space directions'] = new_sd
    
    nrrd.write(output_path, flipped_data, header)
    print(f"Flipped {input_path} along axis {axis} and saved to {output_path}")

def flip_xy(input_path, output_path):
    """Flip along X and Y axes."""
    temp1 = input_path + "_temp_x.nrrd"
    flip_nrrd_axis(input_path, temp1, 0)  # flip X
    flip_nrrd_axis(temp1, output_path, 1)  # flip Y on the X-flipped
    import os
    os.remove(temp1)

def flip_z(input_path, output_path):
    """Flip along Z axis."""
    flip_nrrd_axis(input_path, output_path, 2)

if __name__ == "__main__":
    # Test the 180° Z-axis rotation on the sample that needs it
    input_file = "channels/VNC_SPR8AD.Fru11.12DBD.FB1.1.NC82.Brain.40x.1.composite_channel1.nrrd"
    output_file = "channels/VNC_SPR8AD.Fru11.12DBD.FB1.1.NC82.Brain.40x.1.composite_channel1_rotated_180z.nrrd"
    rotate_nrrd_180_z_axis(input_file, output_file)