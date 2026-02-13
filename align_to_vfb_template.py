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
    image_type = analysis.get('type', 'Unknown')
    physical_x, physical_y, physical_z = analysis.get('physical_extent', (0, 0, 0))
    
    print(f"\nApplying orientation correction to {nrrd_path.name}:")
    print(f"  Detected orientation: {orientation}")
    print(f"  Image type: {image_type}")
    print(f"  Physical extents: X={physical_x:.1f}, Y={physical_y:.1f}, Z={physical_z:.1f}")
    
    needs_rotation = False
    
    if image_type == 'Brain':
        # For brain, expect X (left-right) > Y (anterior-posterior)
        if physical_x < physical_y:
            needs_rotation = True
            print("  Brain image: X < Y, applying 90-degree counterclockwise rotation")
    elif image_type == 'VNC':
        # For VNC, expect Y (anterior-posterior) > X (left-right)
        if physical_y < physical_x:
            needs_rotation = True
            print("  VNC image: Y < X, applying 90-degree counterclockwise rotation")
    
    corrected_path = output_dir / nrrd_path.name
    
    if needs_rotation:
        # Load and rotate the NRRD
        data, header = nrrd.read(str(nrrd_path))
        
        # Rotate 90 degrees counterclockwise in XY plane
        rotated_data = np.rot90(data, k=1, axes=(0, 1))
        
        # Update space directions for rotation
        if 'space directions' in header:
            sd = header['space directions']
            # For 90 deg CCW: X becomes old Y, Y becomes -old X
            new_sd = [
                sd[1],  # new X = old Y
                [-x for x in sd[0]],  # new Y = -old X
                sd[2]   # Z unchanged
            ]
            header['space directions'] = new_sd
        
        # Save rotated data
        nrrd.write(str(corrected_path), rotated_data, header)
        print(f"  Rotated and saved to {corrected_path.name}")
    else:
        # Just copy
        import shutil
        shutil.copy2(nrrd_path, corrected_path)
        print(f"  Copied to {corrected_path.name} (no correction applied)")
    
    return corrected_path

def detect_channel_types_histogram(data):
    """
    Detect signal vs background/reference channels using histogram analysis.
    
    Background channel characteristics:
    - Higher total signal volume (more voxels above threshold)
    - More uniform distribution across the volume
    - Higher maximum values
    - Larger continuous regions
    
    Signal channel characteristics:
    - More localized high-intensity regions
    - Lower total signal volume
    - May have bleed-through from background (low-level signal)
    """
    n_channels = data.shape[3]
    channel_stats = []
    
    print(f"\nAnalyzing {n_channels} channels for type detection:")
    
    for ch_idx in range(n_channels):
        channel_data = data[..., ch_idx]
        
        # Calculate histogram statistics
        hist, bin_edges = np.histogram(channel_data.flatten(), bins=256, range=(0, 255))
        
        # Find optimal threshold (Otsu-like method)
        total_pixels = channel_data.size
        best_threshold = 0
        best_variance = 0
        
        for threshold in range(1, 255):
            # Background pixels (above threshold)
            bg_pixels = channel_data[channel_data > threshold]
            fg_pixels = channel_data[channel_data <= threshold]
            
            if len(bg_pixels) == 0 or len(fg_pixels) == 0:
                continue
                
            # Calculate variances
            bg_variance = np.var(bg_pixels) if len(bg_pixels) > 1 else 0
            fg_variance = np.var(fg_pixels) if len(fg_pixels) > 1 else 0
            
            # Weight by pixel counts
            bg_weight = len(bg_pixels) / total_pixels
            fg_weight = len(fg_pixels) / total_pixels
            
            total_variance = bg_weight * bg_variance + fg_weight * fg_variance
            
            if total_variance > best_variance:
                best_variance = total_variance
                best_threshold = threshold
        
        # Apply threshold and analyze signal regions
        binary_mask = channel_data > best_threshold
        signal_volume = np.sum(binary_mask)
        signal_fraction = signal_volume / total_pixels
        
        # Analyze connected components to find largest continuous region
        from scipy import ndimage
        labeled_mask, num_regions = ndimage.label(binary_mask)
        if num_regions > 0:
            region_sizes = ndimage.sum(binary_mask, labeled_mask, range(1, num_regions + 1))
            largest_region_size = np.max(region_sizes)
            largest_region_fraction = largest_region_size / signal_volume if signal_volume > 0 else 0
        else:
            largest_region_size = 0
            largest_region_fraction = 0
        
        # Calculate signal distribution uniformity
        # More uniform = more like background/reference channel
        if signal_volume > 0:
            # Coefficient of variation of signal intensities
            signal_intensities = channel_data[binary_mask]
            cv_signal = np.std(signal_intensities) / np.mean(signal_intensities) if np.mean(signal_intensities) > 0 else float('inf')
            
            # Spatial uniformity (how evenly distributed across volume)
            # Divide volume into 8 octants and check signal distribution
            z_half = channel_data.shape[2] // 2
            y_half = channel_data.shape[1] // 2
            x_half = channel_data.shape[0] // 2
            
            octant_signals = [
                np.sum(binary_mask[:x_half, :y_half, :z_half]),
                np.sum(binary_mask[:x_half, :y_half, z_half:]),
                np.sum(binary_mask[:x_half, y_half:, :z_half]),
                np.sum(binary_mask[:x_half, y_half:, z_half:]),
                np.sum(binary_mask[x_half:, :y_half, :z_half]),
                np.sum(binary_mask[x_half:, :y_half, z_half:]),
                np.sum(binary_mask[x_half:, y_half:, :z_half]),
                np.sum(binary_mask[x_half:, y_half:, z_half:])
            ]
            
            octant_cv = np.std(octant_signals) / np.mean(octant_signals) if np.mean(octant_signals) > 0 else float('inf')
            uniformity_score = 1.0 / (1.0 + octant_cv)  # Higher = more uniform
        else:
            cv_signal = float('inf')
            uniformity_score = 0
        
        # Calculate bleed-through score
        # Background channels often appear as low-level signal in other channels
        low_signal = np.sum((channel_data > best_threshold * 0.1) & (channel_data <= best_threshold))
        bleed_through_fraction = low_signal / total_pixels
        
        stats = {
            'channel_idx': ch_idx,
            'threshold': best_threshold,
            'signal_volume': signal_volume,
            'signal_fraction': signal_fraction,
            'largest_region_size': largest_region_size,
            'largest_region_fraction': largest_region_fraction,
            'cv_signal': cv_signal,
            'uniformity_score': uniformity_score,
            'bleed_through_fraction': bleed_through_fraction,
            'max_value': np.max(channel_data),
            'mean_signal': np.mean(channel_data[binary_mask]) if signal_volume > 0 else 0
        }
        
        channel_stats.append(stats)
        
        print(f"  Channel {ch_idx}:")
        print(f"    Signal fraction: {signal_fraction:.1f}")
        print(f"    Largest region: {largest_region_fraction:.1f}")
        print(f"    Uniformity: {uniformity_score:.1f}")
        print(f"    Max value: {np.max(channel_data)}")
        print(f"    Mean signal: {np.mean(channel_data[binary_mask]) if signal_volume > 0 else 0:.1f}")
    
    # Classify channels based on statistics
    # Background/reference channel should have:
    # - Highest signal volume
    # - Most uniform distribution
    # - Largest continuous region
    # - Highest mean signal intensity
    
    if len(channel_stats) >= 2:
        # Sort by signal volume (primary criterion)
        sorted_by_volume = sorted(channel_stats, key=lambda x: x['signal_volume'], reverse=True)
        
        # Background is the one with highest signal volume
        background_channel = sorted_by_volume[0]['channel_idx']
        
        # Signal is the remaining channel(s) with lower volume
        signal_channels = [ch['channel_idx'] for ch in sorted_by_volume[1:]]
        
        # Validate classification using secondary criteria
        bg_stats = sorted_by_volume[0]
        signal_stats = sorted_by_volume[1] if len(sorted_by_volume) > 1 else None
        
        print("\nChannel Classification:")
        print(f"  Background/Reference: Channel {background_channel}")
        print(f"    Signal volume: {bg_stats['signal_volume']}")
        print(f"    Uniformity: {bg_stats['uniformity_score']:.1f}")
        
        if signal_stats:
            print(f"  Signal: Channel {signal_stats['channel_idx']}")
            print(f"    Signal volume: {signal_stats['signal_volume']}")
            print(f"    Uniformity: {signal_stats['uniformity_score']:.1f}")
            
            # Check if classification makes sense
            volume_ratio = bg_stats['signal_volume'] / signal_stats['signal_volume'] if signal_stats['signal_volume'] > 0 else float('inf')
            uniformity_ratio = bg_stats['uniformity_score'] / signal_stats['uniformity_score'] if signal_stats['uniformity_score'] > 0 else float('inf')
            
            print(f"    Volume ratio (BG/Signal): {volume_ratio:.1f}")
            print(f"    Uniformity ratio (BG/Signal): {uniformity_ratio:.1f}")
            
            if volume_ratio > 2 and uniformity_ratio > 1.2:
                print("  ✓ Classification appears correct")
            else:
                print("  ⚠️ Classification may need verification")
        
        return {
            'background_channel': background_channel,
            'signal_channels': signal_channels,
            'channel_stats': channel_stats
        }
    else:
        # Single channel - assume it's signal
        print("  Single channel detected - assuming signal channel")
        return {
            'background_channel': None,
            'signal_channels': [0],
            'channel_stats': channel_stats
        }

def prepare_channels_for_alignment(nrrd_path, analysis_results, output_dir=None):
    """Extract and classify channels from multi-channel NRRD for alignment."""
    if output_dir is None:
        output_dir = nrrd_path.parent / "channels"
    
    output_dir = Path(output_dir)
    output_dir.mkdir(exist_ok=True)

    print(f"\nPreparing channels from {nrrd_path.name}:")

    try:
        # Load NRRD file
        data, header = nrrd.read(str(nrrd_path))
        print(f"  Data shape: {data.shape}")

        if len(data.shape) != 4:
            print("  Not multi-channel data, skipping channel extraction")
            return None

        # Detect channel types using histogram analysis
        channel_classification = detect_channel_types_histogram(data)
        background_channel = channel_classification['background_channel']
        signal_channels = channel_classification['signal_channels']

        channels = []
        for channel_idx in range(data.shape[3]):
            channel_data = data[..., channel_idx]

            # Determine channel type and naming
            if channel_idx == background_channel:
                channel_type = "background"
                channel_name = f"{nrrd_path.stem}_background.nrrd"
            elif channel_idx in signal_channels:
                channel_type = "signal"
                channel_name = f"{nrrd_path.stem}_signal.nrrd"
            else:
                channel_type = "unknown"
                channel_name = f"{nrrd_path.stem}_channel{channel_idx}.nrrd"

            # Save individual channel
            channel_path = output_dir / channel_name

            # Update header for single channel
            channel_header = {
                'type': 'uint8',
                'dimension': 3,
                'sizes': channel_data.shape,
                # 'space directions': header['space directions'],
                'encoding': 'gzip'
                # 'space units': header.get('space units', ['microns', 'microns', 'microns'])
                # 'space origin': header.get('space origin', [0.0, 0.0, 0.0]),
                # 'space': header.get('space', 'left-posterior-superior')
            }

            nrrd.write(str(channel_path), channel_data, channel_header)
            channels.append(channel_path)

            print(f"  Saved {channel_type} channel {channel_idx} to {channel_name}")
            # if analysis and 'orientation' in analysis:
            #     print(f"    Orientation: {analysis['orientation']}")
            #     print(f"    Coordinate system: LPS (VFB standard)")

        # Return channel information for alignment pipeline
        result = {
            'channels': channels,
            'background_channel': background_channel,
            'signal_channels': signal_channels,
            'channel_classification': channel_classification
        }
        
        return result

    except Exception as e:
        print(f"  Error preparing channels: {e}")
        return None

def create_alignment_script(corrected_files, analysis_results, channel_info=None):
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
        
        # Get channel information for this file
        file_channel_info = channel_info.get(original_file, {}) if channel_info else {}
        background_channel = file_channel_info.get('background_channel')
        signal_channels = file_channel_info.get('signal_channels', [])

        script_content += f"""
# Align {basename}
echo "Aligning {basename}..."
echo "  Type: {analysis['type']}"
echo "  Template: {template}"
echo "  Orientation: {orientation}"
echo "  Coordinate system: LPS (VFB standard)"
"""

        # Use detected background channel for alignment, fallback to channel 1
        if background_channel is not None:
            moving_channel = f"{basename}_background.nrrd"
            script_content += f'echo "  Using detected background channel for alignment"\n'
        else:
            moving_channel = f"{basename}_channel1.nrrd"
            script_content += f'echo "  Using channel 1 (NC82) for alignment (fallback)"\n'

        script_content += f"""
MOVING="{moving_channel}"
FIXED="{template}_template.nrrd"
OUTPUT_DIR="{basename}_alignment"

# Check if orientation correction is needed
if [[ "{orientation}" == *"rotated"* ]]; then
    echo "  Warning: Image may need orientation correction before alignment"
    echo "  Consider using CMTK or manual reorientation to match template orientation"
fi

# Run elastix alignment
elastix -f "$FIXED" -m "$MOVING" -out "$OUTPUT_DIR" -p "elastix_params.txt"

"""

        # Apply transformation to signal channel(s)
        if signal_channels:
            for sig_ch in signal_channels:
                signal_file = f"{basename}_signal.nrrd"
                result_file = f"{basename}_signal_aligned_{template}.nrrd"
                script_content += f"""
# Apply transformation to signal channel
SIGNAL="{signal_file}"
RESULT="{basename}_signal_aligned_{template}.nrrd"

transformix -in "$SIGNAL" -out "$OUTPUT_DIR" -tp "$OUTPUT_DIR/TransformParameters.0.txt"

# Rename result
mv "$OUTPUT_DIR/result.nrrd" "$RESULT"

echo "Aligned signal channel saved as $RESULT"
"""
        else:
            # Fallback to channel 0
            script_content += f"""
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
    channel_info = {}
    for original_file, corrected_file in corrected_files.items():
        channels_result = prepare_channels_for_alignment(corrected_file, analysis_results, channels_dir)
        if channels_result:
            all_channels.extend(channels_result.get('channels', []))
            channel_info[original_file] = channels_result

    # Create alignment script
    alignment_script = create_alignment_script(corrected_files, analysis_results, channel_info)
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