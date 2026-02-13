#!/bin/bash
# Script to align a single image to VFB templates using CMTK and generate thumbnails

set -e

CMTK_BIN="./CMTK/bin"

echo "Using CMTK from: $CMTK_BIN"

# Test CMTK
if ! "$CMTK_BIN/registration" --version >/dev/null 2>&1; then
    echo "ERROR: CMTK not found"
    exit 1
fi

if [ $# -ne 1 ]; then
    echo "Usage: $0 <image_base_name>"
    echo "Example: $0 Brain_Fru11.12AD_FD6DBD_FB1.1_NC82_S1"
    exit 1
fi

IMAGE_BASE="$1"
echo "Processing image: $IMAGE_BASE"

timestamp=$(date -u +"%Y-%m-%dT%H:%M:%S.%3NZ")

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

# Determine type
if [[ $IMAGE_BASE == *VNC* ]]; then
    template="JRCVNC2018U_template_lps.nrrd"
    echo "  Type: VNC"
else
    template="JRC2018U_template_lps.nrrd"
    echo "  Type: Brain"
fi

# Get base name
base="$IMAGE_BASE"
signal_file="channels/${base}_signal.nrrd"
bg_file="channels/${base}_background.nrrd"
output_signal_file="corrected/${base}_signal_aligned.nrrd"
output_bg_file="corrected/${base}_background_aligned.nrrd"
xform_dir="corrected/${base}_xform"

echo "  Template: $template"
echo "  Signal: $signal_file"
echo "  Background: $bg_file"
echo "  Output Signal: $output_signal_file"
echo "  Output Background: $output_bg_file"

# Check if files exist
if [ ! -f "$signal_file" ]; then
    echo "  ERROR: Signal file $signal_file not found"
    exit 1
fi

if [ ! -f "$bg_file" ]; then
    echo "  ERROR: Background file $bg_file not found"
    exit 1
fi

# Check if orientation correction is needed from orientations.json
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

# Generate thumbnails for aligned images
echo "  Generating alignment thumbnails..."
source venv/bin/activate && python3 -c "
import json
import base64
import io
import matplotlib.pyplot as plt
import nrrd
import numpy as np

def generate_thumbnail(data, title='', figsize=(4,4)):
    fig, ax = plt.subplots(figsize=figsize, dpi=100)
    ax.imshow(data, cmap='gray', aspect='auto')
    ax.set_title(title)
    ax.axis('off')
    
    buf = io.BytesIO()
    fig.savefig(buf, format='png', bbox_inches='tight', pad_inches=0)
    plt.close(fig)
    buf.seek(0)
    return base64.b64encode(buf.read()).decode('utf-8')

# Load template
template_data, _ = nrrd.read('$template')

# Load aligned background
aligned_bg_data, _ = nrrd.read('$output_bg_file')

# Generate projections
axes = [0, 1, 2]
template_projs = [np.max(template_data, axis=ax) for ax in axes]
aligned_projs = [np.max(aligned_bg_data, axis=ax) for ax in axes]

thumbnails = {}
for i, axis in enumerate(['x', 'y', 'z']):
    # Template thumbnail
    template_thumb = generate_thumbnail(template_projs[i], f'Template {axis.upper()}-axis')
    # Aligned thumbnail
    aligned_thumb = generate_thumbnail(aligned_projs[i], f'Aligned {axis.upper()}-axis')
    
    thumbnails[f'{axis}_template'] = template_thumb
    thumbnails[f'{axis}_aligned'] = aligned_thumb

# Save to JSON
result = {
    'image_base': '$IMAGE_BASE',
    'template': '$template',
    'thumbnails': thumbnails,
    'aligned_at': '$timestamp'
}

with open('corrected/${base}_alignment_thumbnails.json', 'w') as f:
    json.dump(result, f, indent=2)

print('Thumbnails generated')
"

echo "  Alignment complete for $IMAGE_BASE"