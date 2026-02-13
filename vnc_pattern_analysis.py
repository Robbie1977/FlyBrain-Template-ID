#!/usr/bin/env python3
"""
VNC orientation analysis using histogram-based signal distribution matching.

This script provides a robust method for determining the correct orientation of
neuropil samples relative to anatomical templates, even when specific anatomical
features are unknown.

METHODOLOGY:
1. Calculate signal bounds by summing along each axis and finding where signal
   exceeds a threshold (30 for templates, 60 for samples).
2. Create histograms of summed signal in blocks of 5 slices along each axis.
3. Compare sample histograms against template histograms using cross-correlation.
4. Test both normal and flipped orientations to find the best match.
5. Interpret axis flips as physical 180° rotations around that axis.

IMPORTANT PHYSICAL INTERPRETATION:
- A "Z-axis flip" means 180° physical rotation around Z-axis (flips X and Y)
- A "Y-axis flip" means 180° physical rotation around Y-axis (flips X and Z)
- A "X-axis flip" means 180° physical rotation around X-axis (flips Y and Z)
- X-axis is often symmetrical and can be flipped independently if needed

USAGE:
- Run script with template and sample files to get orientation corrections
- Works for any neuropil type, not just VNC-specific anatomy
- Provides quantitative correlation scores for confidence assessment

OUTPUT:
- Identifies which axes need 180° flips to match template orientation
- Provides complete rotation sequence for correcting sample orientation
"""

import numpy as np
import nrrd
from pathlib import Path
import matplotlib.pyplot as plt

def calculate_signal_bounds(data, min_signal_threshold=30, is_template=False):
    """
    Calculate signal bounds by summing along each axis and finding where signal exceeds threshold.
    This gives more accurate bounds by considering cumulative signal strength.
    Uses different thresholds for templates vs samples.
    """
    # Use higher threshold for samples to avoid detecting noise
    if is_template:
        threshold = min_signal_threshold  # 30 for templates
    else:
        threshold = max(min_signal_threshold * 2, 50)  # Higher for samples to avoid noise

    bounds = {}
    axis_names = ['X', 'Y', 'Z']

    for axis in range(3):
        # Sum along the current axis
        axis_sum = np.sum(data, axis=tuple(i for i in range(3) if i != axis))

        # Find indices where sum exceeds threshold
        signal_indices = np.where(axis_sum > threshold)[0]

        if len(signal_indices) > 0:
            min_idx = signal_indices[0]
            max_idx = signal_indices[-1]
            bounds[axis_names[axis]] = (min_idx, max_idx, axis_sum)
        else:
            bounds[axis_names[axis]] = (0, data.shape[axis]-1, axis_sum)

    return bounds

def analyze_vnc_anatomy(filename, is_template=False):
    print(f"\n=== VNC Anatomical Pattern Analysis: {Path(filename).name} ===")
    if is_template:
        print("ANALYZING TEMPLATE - This shows the expected pattern")

    # Load data
    data, header = nrrd.read(filename)
    print(f"Shape: {data.shape}")

    # Get voxel sizes
    vox_sizes = [header['space directions'][i][i] for i in range(3)]
    print(f"Voxel sizes: X={vox_sizes[0]:.3f}, Y={vox_sizes[1]:.3f}, Z={vox_sizes[2]:.3f}")

    # Calculate physical dimensions
    phys_dims = [s * vs for s, vs in zip(data.shape, vox_sizes)]
    print(f"Physical dimensions: X={phys_dims[0]:.1f}, Y={phys_dims[1]:.1f}, Z={phys_dims[2]:.1f} μm")

    # Calculate signal bounds using summed projections
    signal_bounds = calculate_signal_bounds(data, min_signal_threshold=30, is_template=is_template)

    # Extract signal dimensions from bounds
    bbox_min = [signal_bounds[axis][0] for axis in ['X', 'Y', 'Z']]
    bbox_max = [signal_bounds[axis][1] for axis in ['X', 'Y', 'Z']]
    signal_dims = [(bbox_max[i] - bbox_min[i]) * vox_sizes[i] for i in range(3)]

    print(f"Signal bounds (voxels): X={bbox_min[0]}-{bbox_max[0]}, Y={bbox_min[1]}-{bbox_max[1]}, Z={bbox_min[2]}-{bbox_max[2]}")
    print(f"Actual signal dimensions: X={signal_dims[0]:.1f}, Y={signal_dims[1]:.1f}, Z={signal_dims[2]:.1f} μm")

    # Expected VNC dimensions (from JRCVNC2018U template signal with summed bounds method)
    expected_dims = [262.4, 489.2, 152.4]  # Updated based on summed bounds calculation
    print(f"Expected VNC signal dimensions: X={expected_dims[0]:.1f}, Y={expected_dims[1]:.1f}, Z={expected_dims[2]:.1f} μm")

    # Check if SIGNAL dimensions match expected VNC proportions
    # VNC should be much longer in Y than X (anterior-posterior > left-right)
    signal_y_to_x_ratio = signal_dims[1] / signal_dims[0]
    expected_y_to_x = expected_dims[1] / expected_dims[0]  # 489.2/260.8 ≈ 1.88

    print(f"Signal Y/X ratio: {signal_y_to_x_ratio:.2f} (expected: {expected_y_to_x:.2f})")

    if abs(signal_y_to_x_ratio - expected_y_to_x) < 0.5:  # Allow 50% tolerance for variations
        print("✓ CORRECT: Signal Y/X ratio matches expected VNC proportions")
    else:
        print("✗ INCORRECT: Signal Y/X ratio doesn't match VNC - may need 90° rotation around Z")

    # Check for clipping (signal touching image boundaries)
    check_clipping_from_bounds(signal_bounds, data.shape)

    # Create signal mask for projections (use the bounds we calculated)
    signal_mask = np.zeros_like(data, dtype=bool)
    signal_mask[bbox_min[0]:bbox_max[0]+1,
                bbox_min[1]:bbox_max[1]+1,
                bbox_min[2]:bbox_max[2]+1] = True

    # But we need to threshold within the bounds too
    signal_mask &= (data > 30)  # Apply threshold within bounds

    # Create maximum intensity projections from the bounded signal area
    # Apply threshold within the bounds
    bounded_data = data[bbox_min[0]:bbox_max[0]+1,
                       bbox_min[1]:bbox_max[1]+1,
                       bbox_min[2]:bbox_max[2]+1]
    bounded_mask = bounded_data > 30

    xy_proj = np.max(bounded_mask, axis=2)  # X-Y projection (dorsal view)
    xz_proj = np.max(bounded_mask, axis=1)  # X-Z projection (lateral view)
    yz_proj = np.max(bounded_mask, axis=0)  # Y-Z projection (anterior view)

    print(f"\nProjection shapes: XY={xy_proj.shape}, XZ={xz_proj.shape}, YZ={yz_proj.shape}")

    # Analyze XY projection (dorsal view) - should show leg spheres
    print("\n=== XY Projection Analysis (Dorsal View) ===")
    analyze_projection(xy_proj, "XY (Dorsal)", vox_sizes[0], vox_sizes[1], is_template)

    # Analyze XZ projection (lateral view) - should show superior/inferior distribution
    print("\n=== XZ Projection Analysis (Lateral View) ===")
    analyze_projection(xz_proj, "XZ (Lateral)", vox_sizes[0], vox_sizes[2], is_template)

    # Analyze YZ projection (anterior view)
    print("\n=== YZ Projection Analysis (Anterior View) ===")
    analyze_projection(yz_proj, "YZ (Anterior)", vox_sizes[1], vox_sizes[2], is_template)

    # Analyze orientation using summed signal strength along Z axis
    analyze_orientation_from_depth(signal_bounds)

    return signal_bounds

def check_clipping_from_bounds(signal_bounds, shape):
    """Check if signal touches image boundaries using the calculated bounds."""
    print("\n=== Clipping Analysis ===")

    clipping_detected = False

    # Get the summed signals for each axis
    x_sum = signal_bounds['X'][2]
    y_sum = signal_bounds['Y'][2]
    z_sum = signal_bounds['Z'][2]

    # Check if signal bounds actually reach the volume boundaries
    x_min, x_max, _ = signal_bounds['X']
    y_min, y_max, _ = signal_bounds['Y']
    z_min, z_max, _ = signal_bounds['Z']

    # Only flag clipping if signal actually touches the boundaries
    if x_min == 0 or x_max == shape[0] - 1:
        # Check if boundary signal is significant (>10% of max)
        boundary_signal = max(x_sum[0], x_sum[-1]) if len(x_sum) > 0 else 0
        max_signal = np.max(x_sum) if len(x_sum) > 0 else 1
        if boundary_signal > 0.1 * max_signal:
            print("⚠️  X-axis clipping detected (signal touches left/right boundaries)")
            clipping_detected = True

    if y_min == 0 or y_max == shape[1] - 1:
        boundary_signal = max(y_sum[0], y_sum[-1]) if len(y_sum) > 0 else 0
        max_signal = np.max(y_sum) if len(y_sum) > 0 else 1
        if boundary_signal > 0.1 * max_signal:
            print("⚠️  Y-axis clipping detected (signal touches anterior/posterior boundaries)")
            clipping_detected = True

    if z_min == 0 or z_max == shape[2] - 1:
        boundary_signal = max(z_sum[0], z_sum[-1]) if len(z_sum) > 0 else 0
        max_signal = np.max(z_sum) if len(z_sum) > 0 else 1
        if boundary_signal > 0.1 * max_signal:
            print("⚠️  Z-axis clipping detected (signal touches dorsal/ventral boundaries)")
            clipping_detected = True

    if not clipping_detected:
        print("✅ No clipping detected - signal contained within volume")

def analyze_projection(proj, name, voxel_x, voxel_y, is_template=False):
    """Analyze a 2D projection for anatomical patterns."""
    # Find connected components in projection
    from scipy import ndimage
    labeled_proj, num_regions = ndimage.label(proj)

    print(f"{name}: {num_regions} connected regions")

    # Get region properties
    region_sizes = []
    region_centers = []

    for i in range(1, num_regions + 1):
        region_mask = labeled_proj == i
        size = np.sum(region_mask)
        region_sizes.append(size)

        center = ndimage.center_of_mass(region_mask)
        region_centers.append(center)

    # Sort by size
    sorted_indices = np.argsort(region_sizes)[::-1]
    region_sizes = [region_sizes[i] for i in sorted_indices]
    region_centers = [region_centers[i] for i in sorted_indices]

    print(f"Top 10 region sizes: {region_sizes[:10]}")

    # Convert centers to physical coordinates
    physical_centers = []
    for center in region_centers[:10]:
        phys_center = [center[0] * voxel_x, center[1] * voxel_y]
        physical_centers.append(phys_center)

    print("Top region centers (physical coordinates):")
    for i, center in enumerate(physical_centers):
        print(".1f")

    # For XY projection, look for circular/spherical patterns (leg neuropils)
    if name == "XY (Dorsal)":
        # Count regions that could be leg spheres (roughly circular, similar size)
        potential_spheres = 0
        min_sphere_size = 50  # Minimum size for a leg sphere

        for size in region_sizes:
            if size > min_sphere_size:
                potential_spheres += 1
            else:
                break  # Since sorted, can stop when we hit small regions

        print(f"Potential leg neuropil spheres: {potential_spheres}")
        if is_template:
            print(f"Template has {potential_spheres} major regions")
        elif potential_spheres >= 6:
            print("✓ GOOD: Found 6+ potential leg spheres")
        else:
            print("✗ FEW: Fewer than 6 potential spheres - may need rotation")

    # For XZ projection, look for superior/inferior distribution
    elif name == "XZ (Lateral)":
        # Analyze Y distribution (superior/inferior)
        y_coords = [center[1] for center in physical_centers[:10]]
        if len(y_coords) > 1:
            y_range = max(y_coords) - min(y_coords)
            y_median = np.median(y_coords)
            superior_count = sum(1 for y in y_coords if y > y_median)
            inferior_count = sum(1 for y in y_coords if y < y_median)

            print(f"Y distribution range: {y_range:.1f} μm")
            print(f"Superior regions: {superior_count}, Inferior regions: {inferior_count}")

            if is_template:
                print(f"Template distribution: {superior_count} superior, {inferior_count} inferior")
            elif superior_count >= inferior_count + 2:
                print("✓ GOOD: More regions superior (wings/back)")
            else:
                print("✗ BALANCED: Similar distribution - may need 180° rotation")

def get_histogram_blocks(axis_bounds):
    """Extract histogram block data from axis bounds."""
    min_idx, max_idx, axis_sum = axis_bounds

    # Create blocks of 5 slices
    block_size = 5
    n_blocks = len(axis_sum) // block_size
    if n_blocks == 0:
        return []

    block_sums = []
    for b in range(n_blocks):
        start_idx = b * block_size
        end_idx = min((b + 1) * block_size, len(axis_sum))
        block_sum = np.sum(axis_sum[start_idx:end_idx])
        block_sums.append(block_sum)

    # Handle remaining slices
    if len(axis_sum) % block_size != 0:
        start_idx = n_blocks * block_size
        block_sum = np.sum(axis_sum[start_idx:])
        block_sums.append(block_sum)

    return block_sums

def analyze_orientation_by_histogram_matching(template_bounds, sample_bounds, template_filename, sample_filename):
    """Analyze orientation by matching sample histograms against template histograms."""
    print(f"\n{'='*80}")
    print("ORIENTATION ANALYSIS: Template vs Sample Histogram Matching")
    print(f"{'='*80}")

    axis_names = ['X', 'Y', 'Z']
    axis_labels = ['Left-Right', 'Anterior-Posterior', 'Dorsal-Ventral']

    # First, determine which axis needs correction
    corrections_needed = {}

    for axis_name, axis_label in zip(axis_names, axis_labels):
        print(f"\n--- {axis_name}-axis ({axis_label}) Orientation Analysis ---")

        # Get template and sample histograms
        template_hist = get_histogram_blocks(template_bounds[axis_name])
        sample_hist = get_histogram_blocks(sample_bounds[axis_name])

        if not template_hist or not sample_hist:
            print(f"Insufficient data for {axis_name}-axis")
            continue

        # Normalize histograms for comparison
        template_norm = np.array(template_hist) / np.sum(template_hist)
        sample_norm = np.array(sample_hist) / np.sum(sample_hist)

        # Test different orientations
        orientations = [
            ("Normal", sample_norm),
            ("Flipped", np.flip(sample_norm))
        ]

        best_match = None
        best_score = -1
        best_orientation = None

        for orientation_name, oriented_sample in orientations:
            # Compute cross-correlation
            correlation = np.correlate(template_norm, oriented_sample, mode='full')
            max_corr = np.max(correlation)

            print(f"  {orientation_name}: correlation = {max_corr:.3f}")

            if max_corr > best_score:
                best_score = max_corr
                best_match = orientation_name
                best_orientation = oriented_sample

        print(f"  ✓ Best match: {best_match} (score: {best_score:.3f})")

        corrections_needed[axis_name] = best_match

        if best_match == "Flipped":
            print(f"  🔄 {axis_name}-axis histogram suggests flipping needed")
        else:
            print(f"  ✅ {axis_name}-axis histogram matches template")

    # Now interpret the corrections in terms of physical rotations
    print(f"\n{'='*80}")
    print("PHYSICAL ROTATION INTERPRETATION:")
    print(f"{'='*80}")

    # The axis that shows "Flipped" indicates the rotation axis
    rotation_axis = None
    for axis, correction in corrections_needed.items():
        if correction == "Flipped":
            rotation_axis = axis
            break

    if rotation_axis is None:
        print("✅ No rotations needed - sample is correctly oriented!")
        return {"rotation": None, "details": corrections_needed}

    # Determine the physical rotation needed
    if rotation_axis == 'Z':
        print("🔄 Z-axis needs flipping → 180° rotation around Z-axis")
        print("   This will flip both X and Y axes (Left↔Right, Anterior↔Posterior)")
        print("   Z-axis (Dorsal-Ventral) orientation remains correct")
        rotation_desc = "180° around Z-axis"

    elif rotation_axis == 'Y':
        print("🔄 Y-axis needs flipping → 180° rotation around Y-axis")
        print("   This will flip both X and Z axes (Left↔Right, Dorsal↔Ventral)")
        print("   Y-axis (Anterior-Posterior) orientation remains correct")
        rotation_desc = "180° around Y-axis"

    elif rotation_axis == 'X':
        print("🔄 X-axis needs flipping → 180° rotation around X-axis")
        print("   This will flip both Y and Z axes (Anterior↔Posterior, Dorsal↔Ventral)")
        print("   X-axis (Left-Right) orientation remains correct")
        print("   NOTE: X-axis is often symmetrical, so this may not be strictly required")
        rotation_desc = "180° around X-axis (symmetrical axis)"

    print(f"\n📋 Required physical rotation: {rotation_desc}")

    # Check for potential issues with symmetrical axis
    if rotation_axis != 'X' and corrections_needed['X'] == 'Flipped':
        print("⚠️  WARNING: X-axis (symmetrical) also shows flipping needed")
        print("   This suggests the sample may have additional orientation issues")
        print("   Consider if manual inspection is needed")

    return {
        "rotation": rotation_desc,
        "rotation_axis": rotation_axis,
        "details": corrections_needed
    }
    """
    Quick function to check orientation of a sample against a template.

    Args:
        template_file: Path to template NRRD file
        sample_file: Path to sample NRRD file

    Returns:
        dict: Required orientation corrections for each axis
    """
    print(f"Checking orientation: {Path(sample_file).name} vs {Path(template_file).name}")

    # Analyze both files
    template_bounds = analyze_vnc_anatomy(template_file, is_template=True)
    sample_bounds = analyze_vnc_anatomy(sample_file)

    # Perform orientation analysis
    corrections = analyze_orientation_by_histogram_matching(
        template_bounds, sample_bounds, template_file, sample_file
    )

    return corrections
    """Extract histogram block data from axis bounds."""
    min_idx, max_idx, axis_sum = axis_bounds

    # Create blocks of 5 slices
    block_size = 5
    n_blocks = len(axis_sum) // block_size
    if n_blocks == 0:
        return []

    block_sums = []
    for b in range(n_blocks):
        start_idx = b * block_size
        end_idx = min((b + 1) * block_size, len(axis_sum))
        block_sum = np.sum(axis_sum[start_idx:end_idx])
        block_sums.append(block_sum)

    # Handle remaining slices
    if len(axis_sum) % block_size != 0:
        start_idx = n_blocks * block_size
        block_sum = np.sum(axis_sum[start_idx:])
        block_sums.append(block_sum)

    return block_sums

def analyze_peaks(block_sums, axis_name, axis_label, filename):
    """Analyze peaks in the signal distribution for anatomical patterns."""
    if not block_sums:
        return

    print(f"\n=== {axis_name}-axis Signal Peaks Analysis ({axis_label}) ===")

    # Find significant peaks (local maxima above threshold)
    max_signal = max(block_sums)
    threshold = max_signal * 0.3  # Only consider peaks above 30% of max

    peaks = []
    peak_positions = []

    for i in range(1, len(block_sums) - 1):
        if (block_sums[i] > block_sums[i-1] and
            block_sums[i] > block_sums[i+1] and
            block_sums[i] > threshold):
            peaks.append(block_sums[i])
            peak_positions.append(i)

    # Also check endpoints if they're significant
    if len(block_sums) > 1:
        if block_sums[0] > block_sums[1] and block_sums[0] > threshold:
            peaks.append(block_sums[0])
            peak_positions.append(0)
        if block_sums[-1] > block_sums[-2] and block_sums[-1] > threshold:
            peaks.append(block_sums[-1])
            peak_positions.append(len(block_sums)-1)

    print(f"Found {len(peaks)} significant peaks at positions: {peak_positions}")
    print(f"Peak values: {[int(p) for p in peaks]}")

    # Sort peaks by value
    sorted_peaks = sorted(zip(peaks, peak_positions), reverse=True)
    top_peaks = sorted_peaks[:5]  # Top 5 peaks

    print("Top peaks (value, position):")
    for value, pos in top_peaks:
        print(".0f")

    # Analyze distribution patterns for VNC anatomy
    if axis_name == 'X':  # Left-Right axis
        if len(peaks) >= 2:
            print("✓ X-axis shows bilateral pattern (left/right leg neuropils)")
            # Check if peaks are roughly symmetric
            if len(peak_positions) == 2:
                left_peak, right_peak = sorted(peak_positions)
                center = len(block_sums) / 2
                symmetry = abs((left_peak - center) + (right_peak - center)) / center
                print(".2f")
        else:
            print("⚠️ X-axis: Expected 2 bilateral peaks not clearly detected")

    elif axis_name == 'Y':  # Anterior-Posterior axis
        if len(peaks) >= 3:
            print("✓ Y-axis shows multi-segment pattern (thoracic neuromeres)")
            # Sort positions to see spacing
            sorted_positions = sorted(peak_positions)
            if len(sorted_positions) >= 3:
                spacings = [sorted_positions[i+1] - sorted_positions[i] for i in range(len(sorted_positions)-1)]
                avg_spacing = sum(spacings) / len(spacings)
                print(".1f")
        else:
            print(f"⚠️ Y-axis: Expected 3+ thoracic segments, found {len(peaks)} peaks")

    elif axis_name == 'Z':  # Dorsal-Ventral axis
        # Analyze tail asymmetry
        max_pos = np.argmax(block_sums)
        left_tail = np.sum(block_sums[:max_pos])
        right_tail = np.sum(block_sums[max_pos+1:])
        total_tail = left_tail + right_tail
        tail_ratio = max(left_tail, right_tail) / min(left_tail, right_tail) if min(left_tail, right_tail) > 0 else float('inf')

        print(f"Z-axis tail analysis: left={left_tail:.0f}, right={right_tail:.0f}, ratio={tail_ratio:.1f}")
        if tail_ratio > 1.5:
            longer_side = "dorsal" if left_tail > right_tail else "ventral"
            print(f"✓ Z-axis shows asymmetric distribution with longer tail toward {longer_side}")
        elif 1.2 <= tail_ratio <= 1.5:
            print("✓ Z-axis shows moderately asymmetric distribution")
        else:
            print("✓ Z-axis shows relatively symmetric distribution")

    # Calculate spacing between major peaks
    if len(peak_positions) >= 2:
        sorted_positions = sorted(peak_positions)
        spacings = [sorted_positions[i+1] - sorted_positions[i] for i in range(len(sorted_positions)-1)]
        avg_spacing = sum(spacings) / len(spacings)
        print(f"Average peak spacing: {avg_spacing:.1f} blocks ({avg_spacing*5:.0f} slices)")

def analyze_orientation_from_depth(signal_bounds):
    """Analyze orientation using signal strength distribution along Z axis."""
    print("\n=== Orientation Analysis from Signal Depth ===")

    z_sum = signal_bounds['Z'][2]  # The summed signal along Z axis

    # Find the peak signal region
    peak_idx = np.argmax(z_sum)
    peak_value = z_sum[peak_idx]

    # Calculate distribution metrics
    total_signal = np.sum(z_sum)
    cumulative = np.cumsum(z_sum) / total_signal

    # Find where 25%, 50%, 75% of signal is reached
    q25_idx = np.where(cumulative >= 0.25)[0][0] if len(np.where(cumulative >= 0.25)[0]) > 0 else 0
    q50_idx = np.where(cumulative >= 0.50)[0][0] if len(np.where(cumulative >= 0.50)[0]) > 0 else len(cumulative)//2
    q75_idx = np.where(cumulative >= 0.75)[0][0] if len(np.where(cumulative >= 0.75)[0]) > 0 else len(cumulative)-1

    print(f"Z-axis signal distribution:")
    print(f"  Peak at slice {peak_idx} (value: {peak_value:.0f})")
    print(f"  25% signal at slice {q25_idx}")
    print(f"  50% signal at slice {q50_idx} (median)")
    print(f"  75% signal at slice {q75_idx}")

    # For VNC, the signal should be relatively evenly distributed
    # with the peak not too close to either end
    z_length = len(z_sum)
    peak_position_ratio = peak_idx / z_length

    print(f"  Peak position ratio: {peak_position_ratio:.2f} (0=start, 1=end)")

    if 0.3 <= peak_position_ratio <= 0.7:
        print("✓ GOOD: Signal peak is centrally located in Z")
    elif peak_position_ratio < 0.3:
        print("⚠️  Signal peak is near dorsal end - may indicate orientation issue")
    else:
        print("⚠️  Signal peak is near ventral end - may indicate orientation issue")

    # Check signal spread
    signal_spread = q75_idx - q25_idx
    spread_ratio = signal_spread / z_length
    print(f"  Signal spread (25%-75%): {signal_spread} slices ({spread_ratio:.2f} of total)")

    if spread_ratio > 0.5:
        print("✓ GOOD: Signal is well distributed through Z depth")
    else:
        print("⚠️  Signal is concentrated - may indicate thin section or orientation issue")

if __name__ == "__main__":
    # First analyze the VNC template to understand expected pattern
    print("FIRST: Analyzing VNC Template")
    template_bounds = analyze_vnc_anatomy("JRCVNC2018U_template.nrrd", is_template=True)

    print("\n" + "="*80)
    print("THEN: Analyzing Sample")
    sample_bounds = analyze_vnc_anatomy("channels/VNC_SPR8AD.Fru11.12DBD.FB1.1.NC82.Brain.40x.1.composite_channel1.nrrd")

    # Perform orientation analysis by histogram matching
    analyze_orientation_by_histogram_matching(
        template_bounds, sample_bounds,
        "JRCVNC2018U_template.nrrd",
        "channels/VNC_SPR8AD.Fru11.12DBD.FB1.1.NC82.Brain.40x.1.composite_channel1.nrrd"
    )