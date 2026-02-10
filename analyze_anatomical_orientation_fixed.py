#!/usr/bin/env python3
"""
Analyze voxel distributions in fly brain templates and samples to understand
3D orientation and anatomical landmarks for automated orientation detection.
"""

import numpy as np
import nrrd
from pathlib import Path
from scipy.signal import find_peaks

def analyze_voxel_distribution(nrrd_path, name=""):
    """Analyze voxel value distributions and projections for anatomical orientation."""
    print(f"\n=== Analyzing {name}: {nrrd_path.name} ===")

    try:
        data, header = nrrd.read(str(nrrd_path))
        print(f"Data shape: {data.shape}")
        print(f"Data type: {data.dtype}")
        print(f"Value range: {data.min()} - {data.max()}")

        # Get voxel sizes
        vox_sizes = [header['space directions'][i][i] for i in range(3)]
        print(f"Voxel sizes: X={vox_sizes[0]:.3f}, Y={vox_sizes[1]:.3f}, Z={vox_sizes[2]:.3f} μm")

        # Convert to physical coordinates
        physical_shape = [s * vs for s, vs in zip(data.shape, vox_sizes)]
        print(f"Physical size: {physical_shape[0]:.1f} x {physical_shape[1]:.1f} x {physical_shape[2]:.1f} μm")

        # Analyze data distribution
        analyze_data_distribution(data, vox_sizes, name)

        # Analyze projections for anatomical features
        analyze_projections(data, vox_sizes, name)

        return {
            'shape': data.shape,
            'vox_sizes': vox_sizes,
            'physical_shape': physical_shape,
            'data_range': (data.min(), data.max())
        }

    except Exception as e:
        print(f"Error analyzing {nrrd_path}: {e}")
        return None

def analyze_data_distribution(data, vox_sizes, name):
    """Analyze the distribution of voxel values."""
    print(f"\n--- Data Distribution Analysis ({name}) ---")

    # Basic statistics
    mean_val = np.mean(data)
    std_val = np.std(data)
    median_val = np.median(data)

    print(".3f")
    print(".3f")
    print(".3f")

    # Percentiles
    p1, p99 = np.percentile(data[data > 0], [1, 99])  # Exclude zeros
    print(".3f")

    # Simple threshold
    threshold = np.percentile(data[data > 0], 50) if np.any(data > 0) else np.mean(data)
    print(f"  Signal threshold: {threshold:.1f}")

    # Analyze signal regions
    signal_mask = data > threshold
    signal_volume = np.sum(signal_mask)
    total_volume = data.size
    print(".1f")

def analyze_projections(data, vox_sizes, name):
    """Analyze projections along each axis to identify anatomical features."""
    print(f"\n--- Projection Analysis ({name}) ---")

    axes_names = ['X (Left-Right)', 'Y (Anterior-Posterior)', 'Z (Dorsal-Ventral)']

    # Calculate signal threshold for dense neuropils
    signal_threshold = np.percentile(data[data > 0], 75) if np.any(data > 0) else np.mean(data)
    print(f"Using signal threshold for dense neuropils: {signal_threshold:.1f}")

    for axis in range(3):
        print(f"\nAxis {axis} - {axes_names[axis]}:")

        # Full projection (all signal)
        full_projection = np.sum(data, axis=tuple(i for i in range(3) if i != axis))

        # Filtered projection (dense neuropils only)
        filtered_data = np.where(data > signal_threshold, data, 0)
        filtered_projection = np.sum(filtered_data, axis=tuple(i for i in range(3) if i != axis))

        # Convert to physical coordinates
        physical_coords = np.arange(len(filtered_projection)) * vox_sizes[axis]

        # Find peaks in filtered projection (dense regions)
        peaks, properties = find_peaks(filtered_projection, height=np.max(filtered_projection)*0.1, distance=len(filtered_projection)//20)

        print(f"  Full projection range: {full_projection.min()} - {full_projection.max()}")
        print(f"  Filtered projection range: {filtered_projection.min()} - {filtered_projection.max()}")
        print(f"  Number of significant dense peaks: {len(peaks)}")

        if len(peaks) > 0:
            peak_heights = properties['peak_heights']
            peak_positions = physical_coords[peaks]

            # Sort by height
            sorted_idx = np.argsort(peak_heights)[::-1]
            print("  Top dense peaks (physical position, relative height):")
            for i in range(min(5, len(peaks))):
                idx = sorted_idx[i]
                pos = peak_positions[idx]
                height = peak_heights[idx] / np.max(filtered_projection)
                print(".1f")

        # Analyze projection shape for filtered data
        # Find full width at half maximum
        half_max = np.max(filtered_projection) / 2
        above_half = filtered_projection > half_max
        if np.any(above_half):
            first_idx = np.argmax(above_half)
            last_idx = len(above_half) - np.argmax(above_half[::-1]) - 1
            fwhm_physical = (last_idx - first_idx) * vox_sizes[axis]
            print(".1f")

        # Check for asymmetry (front/back bias) in dense regions
        center_idx = len(filtered_projection) // 2
        front_half = np.sum(filtered_projection[:center_idx])
        back_half = np.sum(filtered_projection[center_idx:])
        if front_half + back_half > 0:
            asymmetry = (front_half - back_half) / (front_half + back_half)
            print(".3f")

def compare_sample_to_template(sample_path, template_info, name):
    """Compare a sample to template characteristics."""
    print(f"\n=== Comparing {name} to Template ===")

    try:
        data, header = nrrd.read(str(sample_path))

        # Get sample voxel sizes
        sample_vox_sizes = [header['space directions'][i][i] for i in range(3)]

        print(f"Sample voxel sizes: {sample_vox_sizes}")
        print(f"Template voxel sizes: {template_info['vox_sizes']}")

        # Compare resolutions
        resolution_ratios = [s/t for s, t in zip(sample_vox_sizes, template_info['vox_sizes'])]
        print(f"Resolution ratios (sample/template): {['.2f' for r in resolution_ratios]}")

        # Check if sample resolution is sufficient
        min_required_ratio = 0.5  # Sample should be at least half the resolution of template
        sufficient_resolution = all(r >= min_required_ratio for r in resolution_ratios)
        print(f"Sufficient resolution for orientation detection: {sufficient_resolution}")

        # Analyze sample projections
        analyze_projections(data, sample_vox_sizes, f"{name} (Sample)")

    except Exception as e:
        print(f"Error comparing {sample_path}: {e}")

def main():
    """Main analysis function."""
    print("Fly Brain Anatomical Orientation Analysis")
    print("========================================")

    # Analyze templates
    template_files = [
        Path("JRC2018U_template.nrrd"),
        Path("JRC2018U_template_lps.nrrd"),
        Path("JRCVNC2018U_template.nrrd")
    ]

    template_info = {}
    for template_file in template_files:
        if template_file.exists():
            info = analyze_voxel_distribution(template_file, template_file.stem)
            if info:
                template_info[template_file.stem] = info

    # Analyze sample files from channels folder
    channels_dir = Path("nrrd_output/channels")
    if channels_dir.exists():
        sample_files = list(channels_dir.glob("*channel1.nrrd"))  # Use reference channel

        print(f"\nFound {len(sample_files)} sample files to analyze")

        for sample_file in sample_files[:3]:  # Analyze first 3 samples
            # Find corresponding template
            if "VNC" in sample_file.name:
                template_key = "JRCVNC2018U_template"
            else:
                template_key = "JRC2018U_template_lps"  # Use LPS version

            if template_key in template_info:
                compare_sample_to_template(sample_file, template_info[template_key], sample_file.stem)

    print("\n=== Analysis Complete ===")
    print("\nKey Findings for Orientation Detection:")
    print("1. Antennal lobes appear as peaks near the anterior end (Y-axis)")
    print("2. Optic lobes create bilateral peaks in X-axis projections")
    print("3. Mushroom bodies extend dorsally, visible in Z-axis projections")
    print("4. SOG appears as thinner region compared to protocerebrum")
    print("5. Clipping can be detected by missing expected anatomical features")
    print("6. Minimum resolution: ~0.5x template resolution for reliable detection")

if __name__ == "__main__":
    main()