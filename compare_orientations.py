#!/usr/bin/env python3
"""
Compare original vs rotated sample orientation analysis.
"""

import sys
sys.path.append('/Users/rcourt/GIT/FlyBrain-Template-ID')

from vnc_pattern_analysis import analyze_vnc_anatomy, analyze_orientation_by_histogram_matching

def compare_orientations():
    """Compare original and rotated sample orientations."""
    print("Comparing original vs rotated sample orientations...")

    # Analyze template
    template_bounds = analyze_vnc_anatomy("JRCVNC2018U_template.nrrd", is_template=True)

    print("\n" + "="*100)
    print("ORIGINAL SAMPLE ANALYSIS:")
    print("="*100)

    # Analyze original sample
    original_file = "channels/VNC_SPR8AD.Fru11.12DBD.FB1.1.NC82.Brain.40x.1.composite_channel1.nrrd"
    original_bounds = analyze_vnc_anatomy(original_file)

    original_result = analyze_orientation_by_histogram_matching(
        template_bounds, original_bounds,
        "JRCVNC2018U_template.nrrd",
        original_file
    )

    print("\n" + "="*100)
    print("ROTATED SAMPLE ANALYSIS (180° around Z-axis):")
    print("="*100)

    # Analyze rotated sample
    rotated_file = "channels/VNC_SPR8AD.Fru11.12DBD.FB1.1.NC82.Brain.40x.1.composite_channel1_rotated_180z.nrrd"
    rotated_bounds = analyze_vnc_anatomy(rotated_file)

    rotated_result = analyze_orientation_by_histogram_matching(
        template_bounds, rotated_bounds,
        "JRCVNC2018U_template.nrrd",
        rotated_file
    )

    print("\n" + "="*100)
    print("COMPARISON SUMMARY:")
    print("="*100)
    print(f"Original sample needed: {original_result.get('rotation', 'None')}")
    print(f"Rotated sample needs: {rotated_result.get('rotation', 'None')}")

    return original_result, rotated_result

if __name__ == "__main__":
    compare_orientations()