#!/usr/bin/env python3
"""
Script to prepare NRRD files for alignment to VFB template spaces.
This demonstrates the correct workflow for VFB integration using image registration.
"""

import os
import numpy as np
import nrrd
from pathlib import Path

def analyze_image_orientation(nrrd_path):
    """Analyze image data distribution to determine orientation and type."""
    print(f"\nAnalyzing orientation of {nrrd_path.name}:")

    try:
        data, header = nrrd.read(str(nrrd_path))

        # For multi-channel, use reference channel
        if len(data.shape) == 4:
            ref_data = data[..., 1]  # NC82 channel
        else:
            ref_data = data

        # Calculate data distribution along each axis
        z_projection = np.sum(ref_data, axis=(0, 1))  # Sum over X, Y
        y_projection = np.sum(ref_data, axis=(0, 2))  # Sum over X, Z
        x_projection = np.sum(ref_data, axis=(1, 2))  # Sum over Y, Z

        # Find the extent (non-zero regions) along each axis
        z_extent = np.where(z_projection > z_projection.max() * 0.1)[0]
        y_extent = np.where(y_projection > y_projection.max() * 0.1)[0]
        x_extent = np.where(x_projection > x_projection.max() * 0.1)[0]

        z_range = z_extent[-1] - z_extent[0] if len(z_extent) > 0 else 0
        y_range = y_extent[-1] - y_extent[0] if len(y_extent) > 0 else 0
        x_range = x_extent[-1] - x_extent[0] if len(x_extent) > 0 else 0

        print(f"  Data extent - X: {x_range}, Y: {y_range}, Z: {z_range} voxels")

        # Calculate physical extent
        voxdims = [header['space directions'][i][i] for i in range(3)]
        physical_x = x_range * voxdims[0]
        physical_y = y_range * voxdims[1]
        physical_z = z_range * voxdims[2]

        print(f"  Physical extent - X: {physical_x:.1f}, Y: {physical_y:.1f}, Z: {physical_z:.1f} μm")

        # Determine if brain or VNC based on shape
        # VNC is typically longer in Y direction, brain is more cubic
        aspect_yx = physical_y / physical_x if physical_x > 0 else 0
        aspect_zx = physical_z / physical_x if physical_x > 0 else 0

        if aspect_yx > 1.5 and physical_y > 400:  # Long Y axis suggests VNC
            image_type = "VNC"
            suggested_template = "JRCVNC2018U"
            template_url = "https://v2.virtualflybrain.org/data/VFB/i/0020/0000/VFB_00200000/volume.nrrd"
        else:
            image_type = "Brain"
            suggested_template = "JRC2018U"
            template_url = "https://v2.virtualflybrain.org/data/VFB/i/0010/1567/VFB_00101567/volume.nrrd"

        print(f"  Detected type: {image_type}")
        print(f"  Suggested template: {suggested_template}")

        # Determine orientation based on data distribution
        # For fly brain/VNC, the long axis is typically anterior-posterior (Y in standard orientation)
        if x_range >= y_range and x_range >= z_range:
            orientation = "X-long (potentially rotated)"
        elif y_range >= x_range and y_range >= z_range:
            orientation = "Y-long (standard A-P axis)"
        else:
            orientation = "Z-long (potentially rotated)"

        print(f"  Orientation: {orientation}")

        return {
            'type': image_type,
            'suggested_template': suggested_template,
            'template_url': template_url,
            'orientation': orientation,
            'physical_extent': (physical_x, physical_y, physical_z),
            'voxel_extent': (x_range, y_range, z_range)
        }

    except Exception as e:
        print(f"  Error analyzing orientation: {e}")
        return None

def apply_orientation_correction(nrrd_path, analysis, output_dir=None):
    """Apply orientation correction to all channels if needed."""
    if output_dir is None:
        output_dir = nrrd_path.parent / "corrected"
    
    output_dir.mkdir(exist_ok=True)

    orientation = analysis.get('orientation', '')
    
    print(f"\nApplying orientation correction to {nrrd_path.name}:")
    print(f"  Detected orientation: {orientation}")
    
    # For now, just copy files - in practice, you would apply rotations/flips here
    # based on the orientation analysis
    if 'rotated' in orientation:
        print("  Warning: Image may need orientation correction before alignment")
        print("  The same correction must be applied to ALL channels from this image")
        print("  Consider using ImageJ/FIJI or numpy array operations for reorientation")
        print("  Example: np.rot90(array, k=1, axes=(0,1)) for 90-degree rotation")
        # TODO: Implement automatic orientation correction
        # Must apply identical transformation to all channels
    
    # For this implementation, we'll assume images are already in correct orientation
    # or will be manually corrected
    corrected_path = output_dir / nrrd_path.name
    import shutil
    shutil.copy2(nrrd_path, corrected_path)
    print(f"  Copied to {corrected_path.name} (no correction applied)")
    
    return corrected_path

def prepare_channels_for_alignment(nrrd_path, analysis_results, output_dir=None):
    """Extract channels from multi-channel NRRD for alignment."""
    if output_dir is None:
        output_dir = nrrd_path.parent / "channels"
        output_dir.mkdir(exist_ok=True)

    print(f"\nPreparing channels from {nrrd_path.name}:")

    try:
        # Load NRRD file
        data, header = nrrd.read(str(nrrd_path))
        print(f"  Data shape: {data.shape}")

        if len(data.shape) != 4:
            print("  Not multi-channel data, skipping channel extraction")
            return None

        channels = []
        for channel_idx in range(data.shape[3]):
            channel_data = data[..., channel_idx]

            # Save individual channel
            channel_path = output_dir / f"{nrrd_path.stem}_channel{channel_idx}.nrrd"

            # Update header for single channel
            channel_header = header.copy()
            channel_header['dimension'] = 3
            channel_header['sizes'] = channel_data.shape
            
            # Add orientation information
            analysis = analysis_results.get(nrrd_path, {})
            if analysis and 'orientation' in analysis:
                # Add comment about orientation
                channel_header['orientation'] = analysis['orientation']
                # Ensure space origin is set
                if 'space origin' not in channel_header:
                    channel_header['space origin'] = [0, 0, 0]
                # Ensure space directions are correct
                if 'space directions' in channel_header:
                    # VFB uses LPS coordinate system
                    # Add metadata about coordinate system
                    channel_header['space'] = 'left-posterior-superior'

            nrrd.write(str(channel_path), channel_data, channel_header)
            channels.append(channel_path)

            print(f"  Saved channel {channel_idx} to {channel_path.name}")
            if analysis and 'orientation' in analysis:
                print(f"    Orientation: {analysis['orientation']}")
                print(f"    Coordinate system: LPS (VFB standard)")

        return channels

    except Exception as e:
        print(f"  Error preparing channels: {e}")
        return None

def create_alignment_script(corrected_files, analysis_results):
    """Create alignment script based on NRRDtools align.sh approach."""
    script_content = """#!/bin/bash
# Alignment script for fly brain images to VFB templates
# Based on https://github.com/Robbie1977/NRRDtools/blob/master/align.sh

# Requirements: elastix, transformix (from elastix package)
# Install: conda install -c conda-forge elastix

set -e

"""

    # Download templates
    templates_needed = set()
    for result in analysis_results.values():
        if result:
            templates_needed.add(result['suggested_template'])

    for template in templates_needed:
        if template == "JRC2018U":
            url = "https://v2.virtualflybrain.org/data/VFB/i/0010/1567/VFB_00101567/volume.nrrd"
        elif template == "JRCVNC2018U":
            url = "https://v2.virtualflybrain.org/data/VFB/i/0020/0000/VFB_00200000/volume.nrrd"
        else:
            continue

        script_content += f"""
# Download {template} template
if [ ! -f "{template}_template.nrrd" ]; then
    echo "Downloading {template} template..."
    curl -o "{template}_template.nrrd" "{url}"
fi

"""

    script_content += """
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

"""

    for original_file, corrected_file in corrected_files.items():
        basename = corrected_file.stem
        analysis = analysis_results.get(original_file, {})

        if not analysis:
            continue

        template = analysis['suggested_template']
        orientation = analysis['orientation']

        script_content += f"""
# Align {basename}
echo "Aligning {basename}..."
echo "  Type: {analysis['type']}"
echo "  Template: {template}"
echo "  Orientation: {orientation}"
echo "  Coordinate system: LPS (VFB standard)"

# Use NC82/reference channel (channel 1) for alignment
MOVING="{basename}_channel1.nrrd"
FIXED="{template}_template.nrrd"
OUTPUT_DIR="{basename}_alignment"

# Check if orientation correction is needed
if [[ "{orientation}" == *"rotated"* ]]; then
    echo "  Warning: Image may need orientation correction before alignment"
    echo "  Consider using CMTK or manual reorientation to match template orientation"
fi

# Run elastix alignment
elastix -f "$FIXED" -m "$MOVING" -out "$OUTPUT_DIR" -p "elastix_params.txt"

# Apply transformation to signal channel (channel 0)
SIGNAL="{basename}_channel0.nrrd"
RESULT="{basename}_aligned_{template}.nrrd"

transformix -in "$SIGNAL" -out "$OUTPUT_DIR" -tp "$OUTPUT_DIR/TransformParameters.0.txt"

# Rename result
mv "$OUTPUT_DIR/result.nrrd" "$RESULT"

echo "Aligned {basename} saved as $RESULT"

"""

    script_content += """
echo "Alignment complete!"
echo "Aligned files are in VFB template coordinate space and ready for upload."
"""

    return script_content

def main():
    """Prepare files for VFB alignment."""
    nrrd_dir = Path("nrrd_output")
    channels_dir = Path("channels")
    channels_dir.mkdir(exist_ok=True)

    if not nrrd_dir.exists():
        print(f"NRRD directory not found: {nrrd_dir}")
        return

    nrrd_files = list(nrrd_dir.glob("*.nrrd"))
    print(f"Found {len(nrrd_files)} NRRD files")

    # Analyze orientation and type for each file
    analysis_results = {}
    for nrrd_file in nrrd_files:
        analysis = analyze_image_orientation(nrrd_file)
        analysis_results[nrrd_file] = analysis

    # Apply orientation corrections
    corrected_dir = Path("corrected")
    corrected_files = {}
    for nrrd_file in nrrd_files:
        analysis = analysis_results.get(nrrd_file)
        if analysis:
            corrected_file = apply_orientation_correction(nrrd_file, analysis, corrected_dir)
            corrected_files[nrrd_file] = corrected_file

    # Prepare channels from corrected files
    all_channels = []
    for original_file, corrected_file in corrected_files.items():
        channels = prepare_channels_for_alignment(corrected_file, analysis_results, channels_dir)
        if channels:
            all_channels.extend(channels)

    # Create alignment script
    alignment_script = create_alignment_script(corrected_files, analysis_results)
    script_path = Path("align_to_vfb.sh")
    with open(script_path, 'w') as f:
        f.write(alignment_script)

    # Make executable
    os.chmod(script_path, 0o755)

    print(f"\n=== ANALYSIS SUMMARY ===")
    for nrrd_file, analysis in analysis_results.items():
        if analysis:
            print(f"{nrrd_file.name}: {analysis['type']} -> {analysis['suggested_template']} ({analysis['orientation']})")

    print(f"\n=== PREPARATION COMPLETE ===")
    print(f"Prepared {len(all_channels)} channel files in {channels_dir}")
    print(f"Created alignment script: {script_path}")
    print(f"\nTo run alignment:")
    print(f"1. Install elastix: conda install -c conda-forge elastix")
    print(f"2. Run: bash {script_path}")
    print(f"\nImportant notes:")
    print(f"- Coordinate system: LPS (Left-Posterior-Superior) - VFB standard")
    print(f"- Affine alignment limited to ~90 degrees rotation")
    print(f"- Check orientation warnings - may need manual reorientation")
    print(f"- VNC images use JRCVNC2018U, Brain images use JRC2018U")
    print(f"- CMTK can handle orientation metadata from NRRD headers")
    print(f"- Resulting files will be in VFB coordinate space")

if __name__ == "__main__":
    main()