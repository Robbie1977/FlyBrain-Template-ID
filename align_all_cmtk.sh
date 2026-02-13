#!/bin/bash
# Script to align all images in channels/ to VFB templates using CMTK

set -e

CMTK_BIN="./CMTK/bin"

echo "Using CMTK from: $CMTK_BIN"

# Test CMTK
if ! "$CMTK_BIN/registration" --version >/dev/null 2>&1; then
    echo "ERROR: CMTK not found"
    exit 1
fi

echo "CMTK verified"

# Ensure LPS templates exist
if [ ! -f "JRC2018U_template_lps.nrrd" ]; then
    echo "Creating JRC2018U_template_lps.nrrd"
    source venv/bin/activate && python3 -c "
import nrrd
data, header = nrrd.read('JRC2018U_template.nrrd')
header['space'] = 'left-posterior-superior'
nrrd.write('JRC2018U_template_lps.nrrd', data, header)
"
fi

if [ ! -f "JRCVNC2018U_template_lps.nrrd" ]; then
    echo "Creating JRCVNC2018U_template_lps.nrrd"
    source venv/bin/activate && python3 -c "
import nrrd
data, header = nrrd.read('JRCVNC2018U_template.nrrd')
header['space'] = 'left-posterior-superior'
nrrd.write('JRCVNC2018U_template_lps.nrrd', data, header)
"
fi

# Create output directory
mkdir -p corrected

# Loop over all background files
for bg_file in channels/*_background.nrrd; do
    echo "Processing $bg_file"

    # Determine type
    if [[ $bg_file == *VNC* ]]; then
        template="JRCVNC2018U_template_lps.nrrd"
        echo "  Type: VNC"
    else
        template="JRC2018U_template_lps.nrrd"
        echo "  Type: Brain"
    fi

    # Get base name
    base=$(basename "$bg_file" _background.nrrd)
    signal_file="channels/${base}_signal.nrrd"
    output_signal_file="corrected/${base}_signal_aligned.nrrd"
    output_bg_file="corrected/${base}_background_aligned.nrrd"
    xform_dir="corrected/${base}_xform"

    echo "  Template: $template"
    echo "  Signal: $signal_file"
    echo "  Output Signal: $output_signal_file"
    echo "  Output Background: $output_bg_file"

    # Check if signal exists
    if [ ! -f "$signal_file" ]; then
        echo "  ERROR: Signal file $signal_file not found"
        continue
    fi

    # Check if orientation correction is needed
    moving_bg="$bg_file"
    if [[ $base == "Brain_Fru11.12AD_FD6DBD_FB1.1_NC82_S1" ]]; then
        echo "  Applying XY flip for orientation correction"
        temp_bg="corrected/${base}_flipped_bg.nrrd"
        source venv/bin/activate && python3 -c "
from rotate_nrrd import flip_xy
flip_xy('$bg_file', '$temp_bg')
"
        moving_bg="$temp_bg"
    elif [[ $base == "Brain_SPR8AD.dsxDBD.FB1.1.Nc82.Brain.40x.3" ]]; then
        echo "  Applying Z flip for orientation correction"
        temp_bg="corrected/${base}_flipped_bg.nrrd"
        source venv/bin/activate && python3 -c "
from rotate_nrrd import flip_z
flip_z('$bg_file', '$temp_bg')
"
        moving_bg="$temp_bg"
    fi

    # Run registration
    echo "  Running CMTK registration..."
    "$CMTK_BIN/registration" \
        --auto-multi-levels 4 \
        --dofs 6,12 \
        --out-itk "$xform_dir/registration.xform" \
        "$template" "$moving_bg"

    # Apply to signal
    echo "  Applying transformation to signal..."
    "$CMTK_BIN/reformatx" \
        --floating "$signal_file" \
        --output "$output_signal_file" \
        "$template" "$xform_dir/registration.xform"

    # Apply to background
    echo "  Applying transformation to background..."
    "$CMTK_BIN/reformatx" \
        --floating "$moving_bg" \
        --output "$output_bg_file" \
        "$template" "$xform_dir/registration.xform"

    # Clean up temp
    if [[ $moving_bg != $bg_file ]]; then
        rm "$moving_bg"
    fi

    echo "  Aligned $base"
done

echo "All alignments complete!"