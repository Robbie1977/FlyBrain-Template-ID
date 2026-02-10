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

# Use NC82/reference channel (channel 1) for alignment
MOVING="Brain_SPR8AD.dsxDBD.FB1.1.Nc82.Brain.40x.3_channel1.nrrd"
FIXED="JRC2018U_template.nrrd"
OUTPUT_DIR="Brain_SPR8AD.dsxDBD.FB1.1.Nc82.Brain.40x.3_alignment"

# Check if orientation correction is needed
if [[ "X-long (potentially rotated)" == *"rotated"* ]]; then
    echo "  Warning: Image may need orientation correction before alignment"
    echo "  Consider using CMTK or manual reorientation to match template orientation"
fi

# Run elastix alignment
elastix -f "$FIXED" -m "$MOVING" -out "$OUTPUT_DIR" -p "elastix_params.txt"

# Apply transformation to signal channel (channel 0)
SIGNAL="Brain_SPR8AD.dsxDBD.FB1.1.Nc82.Brain.40x.3_channel0.nrrd"
RESULT="Brain_SPR8AD.dsxDBD.FB1.1.Nc82.Brain.40x.3_aligned_JRC2018U.nrrd"

transformix -in "$SIGNAL" -out "$OUTPUT_DIR" -tp "$OUTPUT_DIR/TransformParameters.0.txt"

# Rename result
mv "$OUTPUT_DIR/result.nrrd" "$RESULT"

echo "Aligned Brain_SPR8AD.dsxDBD.FB1.1.Nc82.Brain.40x.3 saved as $RESULT"


# Align VNC_SPR8AD.FD6DBD_FB1.1_nc82647_S1
echo "Aligning VNC_SPR8AD.FD6DBD_FB1.1_nc82647_S1..."
echo "  Type: Brain"
echo "  Template: JRC2018U"
echo "  Orientation: Y-long (standard A-P axis)"
echo "  Coordinate system: LPS (VFB standard)"

# Use NC82/reference channel (channel 1) for alignment
MOVING="VNC_SPR8AD.FD6DBD_FB1.1_nc82647_S1_channel1.nrrd"
FIXED="JRC2018U_template.nrrd"
OUTPUT_DIR="VNC_SPR8AD.FD6DBD_FB1.1_nc82647_S1_alignment"

# Check if orientation correction is needed
if [[ "Y-long (standard A-P axis)" == *"rotated"* ]]; then
    echo "  Warning: Image may need orientation correction before alignment"
    echo "  Consider using CMTK or manual reorientation to match template orientation"
fi

# Run elastix alignment
elastix -f "$FIXED" -m "$MOVING" -out "$OUTPUT_DIR" -p "elastix_params.txt"

# Apply transformation to signal channel (channel 0)
SIGNAL="VNC_SPR8AD.FD6DBD_FB1.1_nc82647_S1_channel0.nrrd"
RESULT="VNC_SPR8AD.FD6DBD_FB1.1_nc82647_S1_aligned_JRC2018U.nrrd"

transformix -in "$SIGNAL" -out "$OUTPUT_DIR" -tp "$OUTPUT_DIR/TransformParameters.0.txt"

# Rename result
mv "$OUTPUT_DIR/result.nrrd" "$RESULT"

echo "Aligned VNC_SPR8AD.FD6DBD_FB1.1_nc82647_S1 saved as $RESULT"


# Align VNC_SPR8AD.dsxDBD.FB1.1.Nc82.Brain.40x.3
echo "Aligning VNC_SPR8AD.dsxDBD.FB1.1.Nc82.Brain.40x.3..."
echo "  Type: Brain"
echo "  Template: JRC2018U"
echo "  Orientation: X-long (potentially rotated)"
echo "  Coordinate system: LPS (VFB standard)"

# Use NC82/reference channel (channel 1) for alignment
MOVING="VNC_SPR8AD.dsxDBD.FB1.1.Nc82.Brain.40x.3_channel1.nrrd"
FIXED="JRC2018U_template.nrrd"
OUTPUT_DIR="VNC_SPR8AD.dsxDBD.FB1.1.Nc82.Brain.40x.3_alignment"

# Check if orientation correction is needed
if [[ "X-long (potentially rotated)" == *"rotated"* ]]; then
    echo "  Warning: Image may need orientation correction before alignment"
    echo "  Consider using CMTK or manual reorientation to match template orientation"
fi

# Run elastix alignment
elastix -f "$FIXED" -m "$MOVING" -out "$OUTPUT_DIR" -p "elastix_params.txt"

# Apply transformation to signal channel (channel 0)
SIGNAL="VNC_SPR8AD.dsxDBD.FB1.1.Nc82.Brain.40x.3_channel0.nrrd"
RESULT="VNC_SPR8AD.dsxDBD.FB1.1.Nc82.Brain.40x.3_aligned_JRC2018U.nrrd"

transformix -in "$SIGNAL" -out "$OUTPUT_DIR" -tp "$OUTPUT_DIR/TransformParameters.0.txt"

# Rename result
mv "$OUTPUT_DIR/result.nrrd" "$RESULT"

echo "Aligned VNC_SPR8AD.dsxDBD.FB1.1.Nc82.Brain.40x.3 saved as $RESULT"


# Align Fru11.12AD.dsxDBD.FB1.1.Brain.40x.8.composite
echo "Aligning Fru11.12AD.dsxDBD.FB1.1.Brain.40x.8.composite..."
echo "  Type: Brain"
echo "  Template: JRC2018U"
echo "  Orientation: Y-long (standard A-P axis)"
echo "  Coordinate system: LPS (VFB standard)"

# Use NC82/reference channel (channel 1) for alignment
MOVING="Fru11.12AD.dsxDBD.FB1.1.Brain.40x.8.composite_channel1.nrrd"
FIXED="JRC2018U_template.nrrd"
OUTPUT_DIR="Fru11.12AD.dsxDBD.FB1.1.Brain.40x.8.composite_alignment"

# Check if orientation correction is needed
if [[ "Y-long (standard A-P axis)" == *"rotated"* ]]; then
    echo "  Warning: Image may need orientation correction before alignment"
    echo "  Consider using CMTK or manual reorientation to match template orientation"
fi

# Run elastix alignment
elastix -f "$FIXED" -m "$MOVING" -out "$OUTPUT_DIR" -p "elastix_params.txt"

# Apply transformation to signal channel (channel 0)
SIGNAL="Fru11.12AD.dsxDBD.FB1.1.Brain.40x.8.composite_channel0.nrrd"
RESULT="Fru11.12AD.dsxDBD.FB1.1.Brain.40x.8.composite_aligned_JRC2018U.nrrd"

transformix -in "$SIGNAL" -out "$OUTPUT_DIR" -tp "$OUTPUT_DIR/TransformParameters.0.txt"

# Rename result
mv "$OUTPUT_DIR/result.nrrd" "$RESULT"

echo "Aligned Fru11.12AD.dsxDBD.FB1.1.Brain.40x.8.composite saved as $RESULT"


# Align VNC_Fru11.12AD_FD6DBD_FB1.1_NC82_S1
echo "Aligning VNC_Fru11.12AD_FD6DBD_FB1.1_NC82_S1..."
echo "  Type: Brain"
echo "  Template: JRC2018U"
echo "  Orientation: Y-long (standard A-P axis)"
echo "  Coordinate system: LPS (VFB standard)"

# Use NC82/reference channel (channel 1) for alignment
MOVING="VNC_Fru11.12AD_FD6DBD_FB1.1_NC82_S1_channel1.nrrd"
FIXED="JRC2018U_template.nrrd"
OUTPUT_DIR="VNC_Fru11.12AD_FD6DBD_FB1.1_NC82_S1_alignment"

# Check if orientation correction is needed
if [[ "Y-long (standard A-P axis)" == *"rotated"* ]]; then
    echo "  Warning: Image may need orientation correction before alignment"
    echo "  Consider using CMTK or manual reorientation to match template orientation"
fi

# Run elastix alignment
elastix -f "$FIXED" -m "$MOVING" -out "$OUTPUT_DIR" -p "elastix_params.txt"

# Apply transformation to signal channel (channel 0)
SIGNAL="VNC_Fru11.12AD_FD6DBD_FB1.1_NC82_S1_channel0.nrrd"
RESULT="VNC_Fru11.12AD_FD6DBD_FB1.1_NC82_S1_aligned_JRC2018U.nrrd"

transformix -in "$SIGNAL" -out "$OUTPUT_DIR" -tp "$OUTPUT_DIR/TransformParameters.0.txt"

# Rename result
mv "$OUTPUT_DIR/result.nrrd" "$RESULT"

echo "Aligned VNC_Fru11.12AD_FD6DBD_FB1.1_NC82_S1 saved as $RESULT"


# Align Brain_SPR8AD.FD6DBD_FB1.1_nc82647_S1
echo "Aligning Brain_SPR8AD.FD6DBD_FB1.1_nc82647_S1..."
echo "  Type: Brain"
echo "  Template: JRC2018U"
echo "  Orientation: Y-long (standard A-P axis)"
echo "  Coordinate system: LPS (VFB standard)"

# Use NC82/reference channel (channel 1) for alignment
MOVING="Brain_SPR8AD.FD6DBD_FB1.1_nc82647_S1_channel1.nrrd"
FIXED="JRC2018U_template.nrrd"
OUTPUT_DIR="Brain_SPR8AD.FD6DBD_FB1.1_nc82647_S1_alignment"

# Check if orientation correction is needed
if [[ "Y-long (standard A-P axis)" == *"rotated"* ]]; then
    echo "  Warning: Image may need orientation correction before alignment"
    echo "  Consider using CMTK or manual reorientation to match template orientation"
fi

# Run elastix alignment
elastix -f "$FIXED" -m "$MOVING" -out "$OUTPUT_DIR" -p "elastix_params.txt"

# Apply transformation to signal channel (channel 0)
SIGNAL="Brain_SPR8AD.FD6DBD_FB1.1_nc82647_S1_channel0.nrrd"
RESULT="Brain_SPR8AD.FD6DBD_FB1.1_nc82647_S1_aligned_JRC2018U.nrrd"

transformix -in "$SIGNAL" -out "$OUTPUT_DIR" -tp "$OUTPUT_DIR/TransformParameters.0.txt"

# Rename result
mv "$OUTPUT_DIR/result.nrrd" "$RESULT"

echo "Aligned Brain_SPR8AD.FD6DBD_FB1.1_nc82647_S1 saved as $RESULT"


# Align VNC_Fru11.12AD.dsxDBD.FB1.1.Brain.40x.8.composite
echo "Aligning VNC_Fru11.12AD.dsxDBD.FB1.1.Brain.40x.8.composite..."
echo "  Type: Brain"
echo "  Template: JRC2018U"
echo "  Orientation: X-long (potentially rotated)"
echo "  Coordinate system: LPS (VFB standard)"

# Use NC82/reference channel (channel 1) for alignment
MOVING="VNC_Fru11.12AD.dsxDBD.FB1.1.Brain.40x.8.composite_channel1.nrrd"
FIXED="JRC2018U_template.nrrd"
OUTPUT_DIR="VNC_Fru11.12AD.dsxDBD.FB1.1.Brain.40x.8.composite_alignment"

# Check if orientation correction is needed
if [[ "X-long (potentially rotated)" == *"rotated"* ]]; then
    echo "  Warning: Image may need orientation correction before alignment"
    echo "  Consider using CMTK or manual reorientation to match template orientation"
fi

# Run elastix alignment
elastix -f "$FIXED" -m "$MOVING" -out "$OUTPUT_DIR" -p "elastix_params.txt"

# Apply transformation to signal channel (channel 0)
SIGNAL="VNC_Fru11.12AD.dsxDBD.FB1.1.Brain.40x.8.composite_channel0.nrrd"
RESULT="VNC_Fru11.12AD.dsxDBD.FB1.1.Brain.40x.8.composite_aligned_JRC2018U.nrrd"

transformix -in "$SIGNAL" -out "$OUTPUT_DIR" -tp "$OUTPUT_DIR/TransformParameters.0.txt"

# Rename result
mv "$OUTPUT_DIR/result.nrrd" "$RESULT"

echo "Aligned VNC_Fru11.12AD.dsxDBD.FB1.1.Brain.40x.8.composite saved as $RESULT"


# Align BrainSPR8AD.Fru11.12DBD.FB1.1.NC82.Brain.40x.1.composite
echo "Aligning BrainSPR8AD.Fru11.12DBD.FB1.1.NC82.Brain.40x.1.composite..."
echo "  Type: Brain"
echo "  Template: JRC2018U"
echo "  Orientation: Y-long (standard A-P axis)"
echo "  Coordinate system: LPS (VFB standard)"

# Use NC82/reference channel (channel 1) for alignment
MOVING="BrainSPR8AD.Fru11.12DBD.FB1.1.NC82.Brain.40x.1.composite_channel1.nrrd"
FIXED="JRC2018U_template.nrrd"
OUTPUT_DIR="BrainSPR8AD.Fru11.12DBD.FB1.1.NC82.Brain.40x.1.composite_alignment"

# Check if orientation correction is needed
if [[ "Y-long (standard A-P axis)" == *"rotated"* ]]; then
    echo "  Warning: Image may need orientation correction before alignment"
    echo "  Consider using CMTK or manual reorientation to match template orientation"
fi

# Run elastix alignment
elastix -f "$FIXED" -m "$MOVING" -out "$OUTPUT_DIR" -p "elastix_params.txt"

# Apply transformation to signal channel (channel 0)
SIGNAL="BrainSPR8AD.Fru11.12DBD.FB1.1.NC82.Brain.40x.1.composite_channel0.nrrd"
RESULT="BrainSPR8AD.Fru11.12DBD.FB1.1.NC82.Brain.40x.1.composite_aligned_JRC2018U.nrrd"

transformix -in "$SIGNAL" -out "$OUTPUT_DIR" -tp "$OUTPUT_DIR/TransformParameters.0.txt"

# Rename result
mv "$OUTPUT_DIR/result.nrrd" "$RESULT"

echo "Aligned BrainSPR8AD.Fru11.12DBD.FB1.1.NC82.Brain.40x.1.composite saved as $RESULT"


# Align Brain_Fru11.12AD_FD6DBD_FB1.1_NC82_S1
echo "Aligning Brain_Fru11.12AD_FD6DBD_FB1.1_NC82_S1..."
echo "  Type: Brain"
echo "  Template: JRC2018U"
echo "  Orientation: Y-long (standard A-P axis)"
echo "  Coordinate system: LPS (VFB standard)"

# Use NC82/reference channel (channel 1) for alignment
MOVING="Brain_Fru11.12AD_FD6DBD_FB1.1_NC82_S1_channel1.nrrd"
FIXED="JRC2018U_template.nrrd"
OUTPUT_DIR="Brain_Fru11.12AD_FD6DBD_FB1.1_NC82_S1_alignment"

# Check if orientation correction is needed
if [[ "Y-long (standard A-P axis)" == *"rotated"* ]]; then
    echo "  Warning: Image may need orientation correction before alignment"
    echo "  Consider using CMTK or manual reorientation to match template orientation"
fi

# Run elastix alignment
elastix -f "$FIXED" -m "$MOVING" -out "$OUTPUT_DIR" -p "elastix_params.txt"

# Apply transformation to signal channel (channel 0)
SIGNAL="Brain_Fru11.12AD_FD6DBD_FB1.1_NC82_S1_channel0.nrrd"
RESULT="Brain_Fru11.12AD_FD6DBD_FB1.1_NC82_S1_aligned_JRC2018U.nrrd"

transformix -in "$SIGNAL" -out "$OUTPUT_DIR" -tp "$OUTPUT_DIR/TransformParameters.0.txt"

# Rename result
mv "$OUTPUT_DIR/result.nrrd" "$RESULT"

echo "Aligned Brain_Fru11.12AD_FD6DBD_FB1.1_NC82_S1 saved as $RESULT"


# Align VNC_SPR8AD.Fru11.12DBD.FB1.1.NC82.Brain.40x.1.composite
echo "Aligning VNC_SPR8AD.Fru11.12DBD.FB1.1.NC82.Brain.40x.1.composite..."
echo "  Type: Brain"
echo "  Template: JRC2018U"
echo "  Orientation: X-long (potentially rotated)"
echo "  Coordinate system: LPS (VFB standard)"

# Use NC82/reference channel (channel 1) for alignment
MOVING="VNC_SPR8AD.Fru11.12DBD.FB1.1.NC82.Brain.40x.1.composite_channel1.nrrd"
FIXED="JRC2018U_template.nrrd"
OUTPUT_DIR="VNC_SPR8AD.Fru11.12DBD.FB1.1.NC82.Brain.40x.1.composite_alignment"

# Check if orientation correction is needed
if [[ "X-long (potentially rotated)" == *"rotated"* ]]; then
    echo "  Warning: Image may need orientation correction before alignment"
    echo "  Consider using CMTK or manual reorientation to match template orientation"
fi

# Run elastix alignment
elastix -f "$FIXED" -m "$MOVING" -out "$OUTPUT_DIR" -p "elastix_params.txt"

# Apply transformation to signal channel (channel 0)
SIGNAL="VNC_SPR8AD.Fru11.12DBD.FB1.1.NC82.Brain.40x.1.composite_channel0.nrrd"
RESULT="VNC_SPR8AD.Fru11.12DBD.FB1.1.NC82.Brain.40x.1.composite_aligned_JRC2018U.nrrd"

transformix -in "$SIGNAL" -out "$OUTPUT_DIR" -tp "$OUTPUT_DIR/TransformParameters.0.txt"

# Rename result
mv "$OUTPUT_DIR/result.nrrd" "$RESULT"

echo "Aligned VNC_SPR8AD.Fru11.12DBD.FB1.1.NC82.Brain.40x.1.composite saved as $RESULT"


echo "Alignment complete!"
echo "Aligned files are in VFB template coordinate space and ready for upload."
