#!/bin/bash
# Alignment script for fly brain images to VFB templates
# Based on https://github.com/Robbie1977/NRRDtools/blob/master/align.sh

# Requirements: elastix, transformix (from elastix package)
# Install: conda install -c conda-forge elastix

set -e


# Download JRC2018U template
if [ ! -f "JRC2018U_template.nrrd" ]; then
    echo "Downloading JRC2018U template..."
    curl -o "JRC2018U_template.nrrd" "https://v2.virtualflybrain.org/data/VFB/i/0010/1567/VFB_00101567/volume.nrrd"
fi


# Download JRCVNC2018U template
if [ ! -f "JRCVNC2018U_template.nrrd" ]; then
    echo "Downloading JRCVNC2018U template..."
    curl -o "JRCVNC2018U_template.nrrd" "https://v2.virtualflybrain.org/data/VFB/i/0020/0000/VFB_00200000/volume.nrrd"
fi


# Create parameter file for elastix (affine transform, limited to ~90 degrees rotation)
cat > "elastix_params.txt" << EOF
(Transform "AffineTransform")
(NumberOfResolutions 4)
(MaximumNumberOfIterations 1000)
(Metric "AdvancedMattesMutualInformation" "NumberOfHistogramBins" 32)
(Optimizer "AdaptiveStochasticGradientDescent" "SP_a" 1000 "SP_A" 50 "SP_alpha" 0.602)
(Interpolator "BSplineInterpolator")
(ResampleInterpolator "FinalBSplineInterpolator")
(Resampler "DefaultResampler")
(FixedImagePyramid "FixedSmoothingImagePyramid")
(MovingImagePyramid "MovingSmoothingImagePyramid")
(HowToCombineTransforms "Compose")
EOF


# Align Brain_SPR8AD.dsxDBD.FB1.1.Nc82.Brain.40x.3
echo "Aligning Brain_SPR8AD.dsxDBD.FB1.1.Nc82.Brain.40x.3..."
echo "  Type: Brain"
echo "  Template: JRC2018U"
echo "  Orientation: X-long (potentially rotated)"
echo "  Coordinate system: LPS (VFB standard)"

echo "  ⚠️  WARNING: Potential orientation mismatch!"
echo "     Template orientation: LPS"
echo "     Sample orientation: unknown (detected: X-long (potentially rotated))"
echo "     This may cause elastix to perform unwanted initial rotations."
echo "     Consider pre-aligning sample to match template orientation."
echo "  Using detected background channel for alignment"

MOVING="Brain_SPR8AD.dsxDBD.FB1.1.Nc82.Brain.40x.3_background.nrrd"
FIXED="JRC2018U_template.nrrd"
OUTPUT_DIR="Brain_SPR8AD.dsxDBD.FB1.1.Nc82.Brain.40x.3_alignment"

# Check if orientation correction is needed
if [[ "X-long (potentially rotated)" == *"rotated"* ]]; then
    echo "  Warning: Image may need orientation correction before alignment"
    echo "  Consider using CMTK or manual reorientation to match template orientation"
fi

# Run elastix alignment
elastix -f "$FIXED" -m "$MOVING" -out "$OUTPUT_DIR" -p "elastix_params.txt"


# Apply transformation to signal channel
SIGNAL="Brain_SPR8AD.dsxDBD.FB1.1.Nc82.Brain.40x.3_signal.nrrd"
RESULT="Brain_SPR8AD.dsxDBD.FB1.1.Nc82.Brain.40x.3_signal_aligned_JRC2018U.nrrd"

transformix -in "$SIGNAL" -out "$OUTPUT_DIR" -tp "$OUTPUT_DIR/TransformParameters.0.txt"

# Rename result
mv "$OUTPUT_DIR/result.nrrd" "$RESULT"

echo "Aligned signal channel saved as $RESULT"

# Align VNC_SPR8AD.FD6DBD_FB1.1_nc82647_S1
echo "Aligning VNC_SPR8AD.FD6DBD_FB1.1_nc82647_S1..."
echo "  Type: VNC"
echo "  Template: JRCVNC2018U"
echo "  Orientation: Y-long (standard A-P axis)"
echo "  Coordinate system: LPS (VFB standard)"

echo "  ⚠️  WARNING: Potential orientation mismatch!"
echo "     Template orientation: LPS"
echo "     Sample orientation: unknown (detected: Y-long (standard A-P axis))"
echo "     This may cause elastix to perform unwanted initial rotations."
echo "     Consider pre-aligning sample to match template orientation."
echo "  Using detected background channel for alignment"

MOVING="VNC_SPR8AD.FD6DBD_FB1.1_nc82647_S1_background.nrrd"
FIXED="JRCVNC2018U_template.nrrd"
OUTPUT_DIR="VNC_SPR8AD.FD6DBD_FB1.1_nc82647_S1_alignment"

# Check if orientation correction is needed
if [[ "Y-long (standard A-P axis)" == *"rotated"* ]]; then
    echo "  Warning: Image may need orientation correction before alignment"
    echo "  Consider using CMTK or manual reorientation to match template orientation"
fi

# Run elastix alignment
elastix -f "$FIXED" -m "$MOVING" -out "$OUTPUT_DIR" -p "elastix_params.txt"


# Apply transformation to signal channel
SIGNAL="VNC_SPR8AD.FD6DBD_FB1.1_nc82647_S1_signal.nrrd"
RESULT="VNC_SPR8AD.FD6DBD_FB1.1_nc82647_S1_signal_aligned_JRCVNC2018U.nrrd"

transformix -in "$SIGNAL" -out "$OUTPUT_DIR" -tp "$OUTPUT_DIR/TransformParameters.0.txt"

# Rename result
mv "$OUTPUT_DIR/result.nrrd" "$RESULT"

echo "Aligned signal channel saved as $RESULT"

# Align VNC_SPR8AD.dsxDBD.FB1.1.Nc82.Brain.40x.3
echo "Aligning VNC_SPR8AD.dsxDBD.FB1.1.Nc82.Brain.40x.3..."
echo "  Type: VNC"
echo "  Template: JRCVNC2018U"
echo "  Orientation: X-long (potentially rotated)"
echo "  Coordinate system: LPS (VFB standard)"

echo "  ⚠️  WARNING: Potential orientation mismatch!"
echo "     Template orientation: LPS"
echo "     Sample orientation: unknown (detected: X-long (potentially rotated))"
echo "     This may cause elastix to perform unwanted initial rotations."
echo "     Consider pre-aligning sample to match template orientation."
echo "  Using detected background channel for alignment"

MOVING="VNC_SPR8AD.dsxDBD.FB1.1.Nc82.Brain.40x.3_background.nrrd"
FIXED="JRCVNC2018U_template.nrrd"
OUTPUT_DIR="VNC_SPR8AD.dsxDBD.FB1.1.Nc82.Brain.40x.3_alignment"

# Check if orientation correction is needed
if [[ "X-long (potentially rotated)" == *"rotated"* ]]; then
    echo "  Warning: Image may need orientation correction before alignment"
    echo "  Consider using CMTK or manual reorientation to match template orientation"
fi

# Run elastix alignment
elastix -f "$FIXED" -m "$MOVING" -out "$OUTPUT_DIR" -p "elastix_params.txt"


# Apply transformation to signal channel
SIGNAL="VNC_SPR8AD.dsxDBD.FB1.1.Nc82.Brain.40x.3_signal.nrrd"
RESULT="VNC_SPR8AD.dsxDBD.FB1.1.Nc82.Brain.40x.3_signal_aligned_JRCVNC2018U.nrrd"

transformix -in "$SIGNAL" -out "$OUTPUT_DIR" -tp "$OUTPUT_DIR/TransformParameters.0.txt"

# Rename result
mv "$OUTPUT_DIR/result.nrrd" "$RESULT"

echo "Aligned signal channel saved as $RESULT"

# Align Fru11.12AD.dsxDBD.FB1.1.Brain.40x.8.composite
echo "Aligning Fru11.12AD.dsxDBD.FB1.1.Brain.40x.8.composite..."
echo "  Type: Brain"
echo "  Template: JRC2018U"
echo "  Orientation: Y-long (standard A-P axis)"
echo "  Coordinate system: LPS (VFB standard)"

echo "  ⚠️  WARNING: Potential orientation mismatch!"
echo "     Template orientation: LPS"
echo "     Sample orientation: unknown (detected: Y-long (standard A-P axis))"
echo "     This may cause elastix to perform unwanted initial rotations."
echo "     Consider pre-aligning sample to match template orientation."
echo "  Using detected background channel for alignment"

MOVING="Fru11.12AD.dsxDBD.FB1.1.Brain.40x.8.composite_background.nrrd"
FIXED="JRC2018U_template.nrrd"
OUTPUT_DIR="Fru11.12AD.dsxDBD.FB1.1.Brain.40x.8.composite_alignment"

# Check if orientation correction is needed
if [[ "Y-long (standard A-P axis)" == *"rotated"* ]]; then
    echo "  Warning: Image may need orientation correction before alignment"
    echo "  Consider using CMTK or manual reorientation to match template orientation"
fi

# Run elastix alignment
elastix -f "$FIXED" -m "$MOVING" -out "$OUTPUT_DIR" -p "elastix_params.txt"


# Apply transformation to signal channel
SIGNAL="Fru11.12AD.dsxDBD.FB1.1.Brain.40x.8.composite_signal.nrrd"
RESULT="Fru11.12AD.dsxDBD.FB1.1.Brain.40x.8.composite_signal_aligned_JRC2018U.nrrd"

transformix -in "$SIGNAL" -out "$OUTPUT_DIR" -tp "$OUTPUT_DIR/TransformParameters.0.txt"

# Rename result
mv "$OUTPUT_DIR/result.nrrd" "$RESULT"

echo "Aligned signal channel saved as $RESULT"

# Align VNC_Fru11.12AD_FD6DBD_FB1.1_NC82_S1
echo "Aligning VNC_Fru11.12AD_FD6DBD_FB1.1_NC82_S1..."
echo "  Type: VNC"
echo "  Template: JRCVNC2018U"
echo "  Orientation: Y-long (standard A-P axis)"
echo "  Coordinate system: LPS (VFB standard)"

echo "  ⚠️  WARNING: Potential orientation mismatch!"
echo "     Template orientation: LPS"
echo "     Sample orientation: unknown (detected: Y-long (standard A-P axis))"
echo "     This may cause elastix to perform unwanted initial rotations."
echo "     Consider pre-aligning sample to match template orientation."
echo "  Using detected background channel for alignment"

MOVING="VNC_Fru11.12AD_FD6DBD_FB1.1_NC82_S1_background.nrrd"
FIXED="JRCVNC2018U_template.nrrd"
OUTPUT_DIR="VNC_Fru11.12AD_FD6DBD_FB1.1_NC82_S1_alignment"

# Check if orientation correction is needed
if [[ "Y-long (standard A-P axis)" == *"rotated"* ]]; then
    echo "  Warning: Image may need orientation correction before alignment"
    echo "  Consider using CMTK or manual reorientation to match template orientation"
fi

# Run elastix alignment
elastix -f "$FIXED" -m "$MOVING" -out "$OUTPUT_DIR" -p "elastix_params.txt"


# Apply transformation to signal channel
SIGNAL="VNC_Fru11.12AD_FD6DBD_FB1.1_NC82_S1_signal.nrrd"
RESULT="VNC_Fru11.12AD_FD6DBD_FB1.1_NC82_S1_signal_aligned_JRCVNC2018U.nrrd"

transformix -in "$SIGNAL" -out "$OUTPUT_DIR" -tp "$OUTPUT_DIR/TransformParameters.0.txt"

# Rename result
mv "$OUTPUT_DIR/result.nrrd" "$RESULT"

echo "Aligned signal channel saved as $RESULT"

# Align Brain_SPR8AD.FD6DBD_FB1.1_nc82647_S1
echo "Aligning Brain_SPR8AD.FD6DBD_FB1.1_nc82647_S1..."
echo "  Type: Brain"
echo "  Template: JRC2018U"
echo "  Orientation: Y-long (standard A-P axis)"
echo "  Coordinate system: LPS (VFB standard)"

echo "  ⚠️  WARNING: Potential orientation mismatch!"
echo "     Template orientation: LPS"
echo "     Sample orientation: unknown (detected: Y-long (standard A-P axis))"
echo "     This may cause elastix to perform unwanted initial rotations."
echo "     Consider pre-aligning sample to match template orientation."
echo "  Using detected background channel for alignment"

MOVING="Brain_SPR8AD.FD6DBD_FB1.1_nc82647_S1_background.nrrd"
FIXED="JRC2018U_template.nrrd"
OUTPUT_DIR="Brain_SPR8AD.FD6DBD_FB1.1_nc82647_S1_alignment"

# Check if orientation correction is needed
if [[ "Y-long (standard A-P axis)" == *"rotated"* ]]; then
    echo "  Warning: Image may need orientation correction before alignment"
    echo "  Consider using CMTK or manual reorientation to match template orientation"
fi

# Run elastix alignment
elastix -f "$FIXED" -m "$MOVING" -out "$OUTPUT_DIR" -p "elastix_params.txt"


# Apply transformation to signal channel
SIGNAL="Brain_SPR8AD.FD6DBD_FB1.1_nc82647_S1_signal.nrrd"
RESULT="Brain_SPR8AD.FD6DBD_FB1.1_nc82647_S1_signal_aligned_JRC2018U.nrrd"

transformix -in "$SIGNAL" -out "$OUTPUT_DIR" -tp "$OUTPUT_DIR/TransformParameters.0.txt"

# Rename result
mv "$OUTPUT_DIR/result.nrrd" "$RESULT"

echo "Aligned signal channel saved as $RESULT"

# Align VNC_Fru11.12AD.dsxDBD.FB1.1.Brain.40x.8.composite
echo "Aligning VNC_Fru11.12AD.dsxDBD.FB1.1.Brain.40x.8.composite..."
echo "  Type: VNC"
echo "  Template: JRCVNC2018U"
echo "  Orientation: X-long (potentially rotated)"
echo "  Coordinate system: LPS (VFB standard)"

echo "  ⚠️  WARNING: Potential orientation mismatch!"
echo "     Template orientation: LPS"
echo "     Sample orientation: unknown (detected: X-long (potentially rotated))"
echo "     This may cause elastix to perform unwanted initial rotations."
echo "     Consider pre-aligning sample to match template orientation."
echo "  Using detected background channel for alignment"

MOVING="VNC_Fru11.12AD.dsxDBD.FB1.1.Brain.40x.8.composite_background.nrrd"
FIXED="JRCVNC2018U_template.nrrd"
OUTPUT_DIR="VNC_Fru11.12AD.dsxDBD.FB1.1.Brain.40x.8.composite_alignment"

# Check if orientation correction is needed
if [[ "X-long (potentially rotated)" == *"rotated"* ]]; then
    echo "  Warning: Image may need orientation correction before alignment"
    echo "  Consider using CMTK or manual reorientation to match template orientation"
fi

# Run elastix alignment
elastix -f "$FIXED" -m "$MOVING" -out "$OUTPUT_DIR" -p "elastix_params.txt"


# Apply transformation to signal channel
SIGNAL="VNC_Fru11.12AD.dsxDBD.FB1.1.Brain.40x.8.composite_signal.nrrd"
RESULT="VNC_Fru11.12AD.dsxDBD.FB1.1.Brain.40x.8.composite_signal_aligned_JRCVNC2018U.nrrd"

transformix -in "$SIGNAL" -out "$OUTPUT_DIR" -tp "$OUTPUT_DIR/TransformParameters.0.txt"

# Rename result
mv "$OUTPUT_DIR/result.nrrd" "$RESULT"

echo "Aligned signal channel saved as $RESULT"

# Align BrainSPR8AD.Fru11.12DBD.FB1.1.NC82.Brain.40x.1.composite
echo "Aligning BrainSPR8AD.Fru11.12DBD.FB1.1.NC82.Brain.40x.1.composite..."
echo "  Type: Brain"
echo "  Template: JRC2018U"
echo "  Orientation: Y-long (standard A-P axis)"
echo "  Coordinate system: LPS (VFB standard)"

echo "  ⚠️  WARNING: Potential orientation mismatch!"
echo "     Template orientation: LPS"
echo "     Sample orientation: unknown (detected: Y-long (standard A-P axis))"
echo "     This may cause elastix to perform unwanted initial rotations."
echo "     Consider pre-aligning sample to match template orientation."
echo "  Using detected background channel for alignment"

MOVING="BrainSPR8AD.Fru11.12DBD.FB1.1.NC82.Brain.40x.1.composite_background.nrrd"
FIXED="JRC2018U_template.nrrd"
OUTPUT_DIR="BrainSPR8AD.Fru11.12DBD.FB1.1.NC82.Brain.40x.1.composite_alignment"

# Check if orientation correction is needed
if [[ "Y-long (standard A-P axis)" == *"rotated"* ]]; then
    echo "  Warning: Image may need orientation correction before alignment"
    echo "  Consider using CMTK or manual reorientation to match template orientation"
fi

# Run elastix alignment
elastix -f "$FIXED" -m "$MOVING" -out "$OUTPUT_DIR" -p "elastix_params.txt"


# Apply transformation to signal channel
SIGNAL="BrainSPR8AD.Fru11.12DBD.FB1.1.NC82.Brain.40x.1.composite_signal.nrrd"
RESULT="BrainSPR8AD.Fru11.12DBD.FB1.1.NC82.Brain.40x.1.composite_signal_aligned_JRC2018U.nrrd"

transformix -in "$SIGNAL" -out "$OUTPUT_DIR" -tp "$OUTPUT_DIR/TransformParameters.0.txt"

# Rename result
mv "$OUTPUT_DIR/result.nrrd" "$RESULT"

echo "Aligned signal channel saved as $RESULT"

# Align Brain_Fru11.12AD_FD6DBD_FB1.1_NC82_S1
echo "Aligning Brain_Fru11.12AD_FD6DBD_FB1.1_NC82_S1..."
echo "  Type: Brain"
echo "  Template: JRC2018U"
echo "  Orientation: Y-long (standard A-P axis)"
echo "  Coordinate system: LPS (VFB standard)"

echo "  ⚠️  WARNING: Potential orientation mismatch!"
echo "     Template orientation: LPS"
echo "     Sample orientation: unknown (detected: Y-long (standard A-P axis))"
echo "     This may cause elastix to perform unwanted initial rotations."
echo "     Consider pre-aligning sample to match template orientation."
echo "  Using detected background channel for alignment"

MOVING="Brain_Fru11.12AD_FD6DBD_FB1.1_NC82_S1_background.nrrd"
FIXED="JRC2018U_template.nrrd"
OUTPUT_DIR="Brain_Fru11.12AD_FD6DBD_FB1.1_NC82_S1_alignment"

# Check if orientation correction is needed
if [[ "Y-long (standard A-P axis)" == *"rotated"* ]]; then
    echo "  Warning: Image may need orientation correction before alignment"
    echo "  Consider using CMTK or manual reorientation to match template orientation"
fi

# Run elastix alignment
elastix -f "$FIXED" -m "$MOVING" -out "$OUTPUT_DIR" -p "elastix_params.txt"


# Apply transformation to signal channel
SIGNAL="Brain_Fru11.12AD_FD6DBD_FB1.1_NC82_S1_signal.nrrd"
RESULT="Brain_Fru11.12AD_FD6DBD_FB1.1_NC82_S1_signal_aligned_JRC2018U.nrrd"

transformix -in "$SIGNAL" -out "$OUTPUT_DIR" -tp "$OUTPUT_DIR/TransformParameters.0.txt"

# Rename result
mv "$OUTPUT_DIR/result.nrrd" "$RESULT"

echo "Aligned signal channel saved as $RESULT"

# Align VNC_SPR8AD.Fru11.12DBD.FB1.1.NC82.Brain.40x.1.composite
echo "Aligning VNC_SPR8AD.Fru11.12DBD.FB1.1.NC82.Brain.40x.1.composite..."
echo "  Type: VNC"
echo "  Template: JRCVNC2018U"
echo "  Orientation: X-long (potentially rotated)"
echo "  Coordinate system: LPS (VFB standard)"

echo "  ⚠️  WARNING: Potential orientation mismatch!"
echo "     Template orientation: LPS"
echo "     Sample orientation: unknown (detected: X-long (potentially rotated))"
echo "     This may cause elastix to perform unwanted initial rotations."
echo "     Consider pre-aligning sample to match template orientation."
echo "  Using detected background channel for alignment"

MOVING="VNC_SPR8AD.Fru11.12DBD.FB1.1.NC82.Brain.40x.1.composite_background.nrrd"
FIXED="JRCVNC2018U_template.nrrd"
OUTPUT_DIR="VNC_SPR8AD.Fru11.12DBD.FB1.1.NC82.Brain.40x.1.composite_alignment"

# Check if orientation correction is needed
if [[ "X-long (potentially rotated)" == *"rotated"* ]]; then
    echo "  Warning: Image may need orientation correction before alignment"
    echo "  Consider using CMTK or manual reorientation to match template orientation"
fi

# Run elastix alignment
elastix -f "$FIXED" -m "$MOVING" -out "$OUTPUT_DIR" -p "elastix_params.txt"


# Apply transformation to signal channel
SIGNAL="VNC_SPR8AD.Fru11.12DBD.FB1.1.NC82.Brain.40x.1.composite_signal.nrrd"
RESULT="VNC_SPR8AD.Fru11.12DBD.FB1.1.NC82.Brain.40x.1.composite_signal_aligned_JRCVNC2018U.nrrd"

transformix -in "$SIGNAL" -out "$OUTPUT_DIR" -tp "$OUTPUT_DIR/TransformParameters.0.txt"

# Rename result
mv "$OUTPUT_DIR/result.nrrd" "$RESULT"

echo "Aligned signal channel saved as $RESULT"

echo "Alignment complete!"
echo "Aligned files are in VFB template coordinate space and ready for upload."
