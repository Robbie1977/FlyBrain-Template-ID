#!/bin/bash
# CMTK-based alignment script for fly brain images to VFB templates
# Alternative to elastix - uses neuroscience-specific registration tools

# Requirements: CMTK (Computational Morphometry Toolkit)
# Download: https://www.nitrc.org/projects/cmtk
# Install: Copy bin directory to PATH or use full paths as below

set -e

# Path to CMTK binaries (adjust if installed elsewhere)
CMTK_BIN="./CMTK/bin"

echo "Using CMTK from: $CMTK_BIN"
echo "Testing CMTK installation..."

# Test CMTK installation
if ! "$CMTK_BIN/registration" --version >/dev/null 2>&1; then
    echo "ERROR: CMTK registration tool not found at $CMTK_BIN/registration"
    echo "Please install CMTK from https://www.nitrc.org/projects/cmtk"
    exit 1
fi

echo "CMTK installation verified ✓"

# Download and prepare templates with proper coordinate systems
echo "Preparing templates with LPS coordinate system..."

# Download JRC2018U template
if [ ! -f "JRC2018U_template.nrrd" ]; then
    echo "Downloading JRC2018U template..."
    curl -o "JRC2018U_template.nrrd" "https://v2.virtualflybrain.org/data/VFB/i/0010/1567/VFB_00101567/volume.nrrd"
fi

# Add LPS coordinate system to brain template (CMTK requires explicit orientation)
if [ ! -f "JRC2018U_template_lps.nrrd" ]; then
    echo "Adding LPS coordinate system to brain template..."
    python3 -c "
import nrrd
data, header = nrrd.read('JRC2018U_template.nrrd')
header['space'] = 'left-posterior-superior'
nrrd.write('JRC2018U_template_lps.nrrd', data, header)
"
fi

echo "Starting CMTK-based alignment..."

# Align Brain_SPR8AD.dsxDBD.FB1.1.Nc82.Brain.40x.3
echo "Aligning Brain_SPR8AD.dsxDBD.FB1.1.Nc82.Brain.40x.3..."
echo "  Type: Brain"
echo "  Template: JRC2018U"
echo "  Orientation: X-long (potentially rotated)"
echo "  Coordinate system: LPS (VFB standard)"

MOVING="channels/Brain_SPR8AD.dsxDBD.FB1.1.Nc82.Brain.40x.3_channel1.nrrd"
FIXED="JRC2018U_template_lps.nrrd"
OUTPUT_DIR="Brain_SPR8AD.dsxDBD.FB1.1.Nc82.Brain.40x.3_cmtk_alignment"

# Check if orientation correction is needed
if [[ "X-long (potentially rotated)" == *"rotated"* ]]; then
    echo "  Warning: Image may need orientation correction before alignment"
    echo "  Consider manual reorientation using ImageJ/FIJI"
fi

# Run CMTK affine registration
echo "  Running CMTK affine registration..."
"$CMTK_BIN/registration" \
    --auto-multi-levels 4 \
    --dofs 6,12 \
    --out-itk "$OUTPUT_DIR/registration.xform" \
    "$FIXED" "$MOVING"

# Apply transformation to signal channel (channel 0)
SIGNAL="channels/Brain_SPR8AD.dsxDBD.FB1.1.Nc82.Brain.40x.3_channel0.nrrd"
RESULT="Brain_SPR8AD.dsxDBD.FB1.1.Nc82.Brain.40x.3_cmtk_aligned.nrrd"

echo "  Applying transformation to signal channel..."
"$CMTK_BIN/reformatx" \
    --floating "$SIGNAL" \
    --output "$RESULT" \
    "$FIXED" "$OUTPUT_DIR/registration.xform"

echo "  Aligned Brain_SPR8AD.dsxDBD.FB1.1.Nc82.Brain.40x.3 saved as $RESULT"

# Add more alignment commands for other images here...
# (This is a template - would need to be expanded for all images)

echo ""
echo "CMTK alignment complete!"
echo "CMTK is particularly well-suited for neuroscience image registration"
echo "and handles NRRD coordinate systems properly."
echo ""
echo "Next steps:"
echo "1. Verify alignment quality using image viewers"
echo "2. Apply same process to remaining images"
echo "3. Upload aligned images to VFB"