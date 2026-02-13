#!/usr/bin/env python3
"""
Apply 180° rotation around Y-axis instead of Z-axis to see if that fixes the orientation.
"""

import numpy as np
import nrrd

def rotate_180_y_axis(input_path, output_path):
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
            sd[1],                # Y unchanged
            [-x for x in sd[2]]   # negate Z
        ]
        header['space directions'] = new_sd

    # Write the rotated data
    nrrd.write(output_path, rotated_data, header)
    print(f"Rotated {input_path} 180° around Y-axis and saved to {output_path}")

def test_y_rotation():
    """Test 180° Y-axis rotation on the original sample."""
    input_file = "channels/VNC_SPR8AD.Fru11.12DBD.FB1.1.NC82.Brain.40x.1.composite_channel1.nrrd"
    output_file = "channels/VNC_SPR8AD.Fru11.12DBD.FB1.1.NC82.Brain.40x.1.composite_channel1_rotated_180y.nrrd"

    rotate_180_y_axis(input_file, output_file)

    # Now test the orientation analysis on this new rotation
    import sys
    sys.path.append('/Users/rcourt/GIT/FlyBrain-Template-ID')

    from vnc_pattern_analysis import analyze_vnc_anatomy, analyze_orientation_by_histogram_matching

    print("\n" + "="*80)
    print("ANALYZING Y-AXIS ROTATED SAMPLE:")
    print("="*80)

    template_bounds = analyze_vnc_anatomy("JRCVNC2018U_template.nrrd", is_template=True)
    rotated_bounds = analyze_vnc_anatomy(output_file)

    result = analyze_orientation_by_histogram_matching(
        template_bounds, rotated_bounds,
        "JRCVNC2018U_template.nrrd",
        output_file
    )

    return result

if __name__ == "__main__":
    test_y_rotation()