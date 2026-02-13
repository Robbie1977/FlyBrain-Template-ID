#!/usr/bin/env python3
"""
Get image data for web interface.
"""

import numpy as np
import tifffile
import matplotlib.pyplot as plt
from pathlib import Path
from scipy.signal import find_peaks
import sys
import json
import base64
from io import BytesIO

def analyze_projections(data, vox_sizes):
    """Analyze projections and find peaks."""
    signal_threshold = np.percentile(data[data > 0], 75) if np.any(data > 0) else np.mean(data)

    projections = {}
    peaks_data = {}

    for axis in range(3):
        # Create max projection for 2D thumbnail
        proj = np.max(data, axis=axis)
        filtered_data = np.where(data > signal_threshold, data, 0)
        # For peaks, sum along the other two axes to get 1D
        filtered_proj = np.sum(filtered_data, axis=tuple(i for i in range(3) if i != axis))

        peaks, properties = find_peaks(filtered_proj,
                                     height=np.max(filtered_proj)*0.1,
                                     distance=len(filtered_proj)//20)

        projections[f'axis_{axis}'] = proj
        peaks_data[f'axis_{axis}'] = {
            'peaks': peaks.tolist(),
            'heights': properties['peak_heights'].tolist()
        }

    return projections, peaks_data

def check_orientation(peaks_data, template_key, projections):
    """Check if orientation matches template."""
    # Simplified: assume correct for now
    return True, {}
def generate_thumbnail(proj, axis_name):
    """Generate base64 thumbnail."""
    fig, ax = plt.subplots(figsize=(1, 1))
    ax.imshow(proj, cmap='gray')
    ax.axis('off')

    buf = BytesIO()
    fig.savefig(buf, format='png', dpi=50, bbox_inches='tight')
    plt.close(fig)
    buf.seek(0)
    return base64.b64encode(buf.read()).decode('utf-8')

def main():
    if len(sys.argv) < 2:
        print("Usage: python get_image_data.py <image_path>")
        sys.exit(1)

    image_path = sys.argv[1]
    tiff_file = Path("Images") / f"{image_path}.tif"

    if not tiff_file.exists():
        tiff_file = Path("Images") / f"{image_path}.tiff"
        if not tiff_file.exists():
            print(json.dumps({"error": "Image not found"}))
            sys.exit(1)

    # Load data
    data = tifffile.imread(str(tiff_file))
    if data.ndim == 4:  # (slices, channels, h, w)
        data = data[:, 0, :, :]  # Take first channel as background
    # Assume isotropic for now
    vox_sizes = [1.0] * data.ndim

    projections, peaks_data = analyze_projections(data, vox_sizes)

    # Determine template (simplified)
    if "VNC" in image_path:
        template_key = "JRCVNC2018U_template"
    else:
        template_key = "JRC2018U_template_lps"

    orientation_correct, changes_needed = check_orientation(peaks_data, template_key, projections)

    # Generate thumbnails
    original_thumbnails = {}
    suggested_thumbnails = {}  # For now, same as original
    axis_names = ['X', 'Y', 'Z']
    for i, axis in enumerate(['x', 'y', 'z']):
        original_thumbnails[axis] = generate_thumbnail(projections[f'axis_{i}'], f'Original {axis_names[i]}')
        suggested_thumbnails[axis] = generate_thumbnail(projections[f'axis_{i}'], f'Suggested {axis_names[i]}')

    result = {
        "name": image_path,
        "template": template_key,
        "template_correct": orientation_correct,
        "original_thumbnails": original_thumbnails,
        "suggested_thumbnails": suggested_thumbnails,
        "changes_needed": changes_needed
    }

    print(json.dumps(result))

if __name__ == "__main__":
    main()