#!/usr/bin/env python3
"""
Get image data for web interface.
Loads sample TIFF, compares against NRRD template, generates thumbnails,
histograms, and orientation analysis matching the PDF report format.
Auto-saves analysis results to orientations.json.
"""

import numpy as np
import nrrd
import tifffile
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from pathlib import Path
from scipy.signal import find_peaks
import sys
import json
import base64
from io import BytesIO
import concurrent.futures

TEMPLATE_FILES = {
    "JRC2018U_template": Path("JRC2018U_template.nrrd"),
    "JRC2018U_template_lps": Path("JRC2018U_template_lps.nrrd"),
    "JRCVNC2018U_template": Path("JRCVNC2018U_template.nrrd"),
    "JRCVNC2018U_template_lps": Path("JRCVNC2018U_template_lps.nrrd"),
}

ORIENTATIONS_FILE = Path("orientations.json")

_template_cache = {}

DEFAULT_VOXEL_SIZE = 0.5  # µm – used when TIFF metadata has no resolution info


def _extract_voxel_sizes(tif):
    """Try to read voxel/pixel sizes from TIFF metadata.

    Checks ImageJ metadata, OME metadata, and standard TIFF resolution tags.
    Returns [vz, vy, vx] in µm.  Falls back to DEFAULT_VOXEL_SIZE if nothing
    is found.
    """
    vx = vy = vz = None

    # --- Try ImageJ metadata (most FlyBrain TIFFs) ---
    try:
        ij = tif.imagej_metadata
        if ij:
            # ImageJ stores spacing for Z in 'spacing'
            if 'spacing' in ij:
                vz = float(ij['spacing'])
            # XY resolution is in the TIFF page resolution tags
            page = tif.pages[0]
            tags = page.tags
            if 'XResolution' in tags:
                xr = tags['XResolution'].value
                if isinstance(xr, tuple) and xr[0] > 0:
                    vx = xr[1] / xr[0]  # (pixels_per_unit, unit_scale) → µm/pixel
            if 'YResolution' in tags:
                yr = tags['YResolution'].value
                if isinstance(yr, tuple) and yr[0] > 0:
                    vy = yr[1] / yr[0]
            # ImageJ unit tag – convert if not already µm
            unit = ij.get('unit', 'micron')
            if unit and unit.lower() in ('um', 'µm', 'micron', 'microns', 'micrometer'):
                pass  # already µm
            elif unit and unit.lower() in ('nm', 'nanometer', 'nanometers'):
                if vx: vx /= 1000.0
                if vy: vy /= 1000.0
                if vz: vz /= 1000.0
    except Exception:
        pass

    # --- Try OME-XML metadata ---
    if vx is None:
        try:
            if hasattr(tif, 'ome_metadata') and tif.ome_metadata:
                import xml.etree.ElementTree as ET
                root = ET.fromstring(tif.ome_metadata)
                ns = {'ome': root.tag.split('}')[0].strip('{')} if '}' in root.tag else {}
                pixels = root.find('.//ome:Pixels', ns) if ns else root.find('.//Pixels')
                if pixels is not None:
                    if pixels.get('PhysicalSizeX'):
                        vx = float(pixels.get('PhysicalSizeX'))
                    if pixels.get('PhysicalSizeY'):
                        vy = float(pixels.get('PhysicalSizeY'))
                    if pixels.get('PhysicalSizeZ'):
                        vz = float(pixels.get('PhysicalSizeZ'))
        except Exception:
            pass

    # Fill in defaults
    if vx is None: vx = DEFAULT_VOXEL_SIZE
    if vy is None: vy = vx  # assume isotropic XY
    if vz is None: vz = DEFAULT_VOXEL_SIZE

    return [vz, vy, vx]


def load_template(template_key):
    """Load and cache a template NRRD file."""
    if template_key in _template_cache:
        return _template_cache[template_key]

    template_file = TEMPLATE_FILES.get(template_key)
    if template_file is None or not template_file.exists():
        return None

    data, header = nrrd.read(str(template_file))
    # Extract voxel sizes from space directions using norm of each row
    # (consistent with sample NRRD extraction; handles rotations with off-diagonal entries)
    sd = np.array(header['space directions'], dtype=float)
    vox_sizes = [float(np.linalg.norm(sd[i])) for i in range(3)]

    _template_cache[template_key] = {
        'data': data,
        'header': header,
        'vox_sizes': vox_sizes,
        'shape': data.shape,
        'physical_size': [s * vs for s, vs in zip(data.shape, vox_sizes)]
    }
    return _template_cache[template_key]


def process_axis(data, signal_threshold, axis, vox_sizes, axes_names):
    proj_2d = np.max(data, axis=axis)
    filtered_data = np.where(data > signal_threshold, data, 0)
    filtered_proj = np.sum(filtered_data, axis=tuple(i for i in range(3) if i != axis))
    filtered_proj = np.asarray(filtered_proj).flatten()
    physical_coords = np.arange(len(filtered_proj)) * vox_sizes[axis]
    peaks, properties = find_peaks(
        filtered_proj,
        height=np.max(filtered_proj) * 0.1 if np.max(filtered_proj) > 0 else 0,
        distance=max(len(filtered_proj) // 20, 1)
    )
    return axis, proj_2d, {
        'filtered': filtered_proj,
        'physical_coords': physical_coords,
    }, {
        'peaks': peaks,
        'heights': properties['peak_heights'] if 'peak_heights' in properties else np.array([]),
        'num_peaks': len(peaks),
        'axis_name': axes_names[axis],
    }

def analyze_projections(data, vox_sizes):
    """Analyze projections and find peaks. Returns 2D max projections and 1D filtered profiles."""
    signal_threshold = np.percentile(data[data > 0], 75) if np.any(data > 0) else np.mean(data)

    projections_2d = {}
    projections_1d = {}
    peaks_data = {}

    axes_names = ['X (Left-Right)', 'Y (Anterior-Posterior)', 'Z (Dorsal-Ventral)']

    with concurrent.futures.ProcessPoolExecutor() as executor:
        futures = [executor.submit(process_axis, data, signal_threshold, axis, vox_sizes, axes_names) for axis in range(3)]
        for future in concurrent.futures.as_completed(futures):
            axis, proj_2d, proj_1d, peaks = future.result()
            projections_2d[axis] = proj_2d
            projections_1d[axis] = proj_1d
            peaks_data[axis] = peaks

    return projections_2d, projections_1d, peaks_data


def check_orientation(sample_peaks, sample_proj_1d, template_key, template_info):
    """Check if sample orientation matches template expectations."""
    if template_info is None:
        return False, ["Template not loaded"], {'x': 0, 'y': 0, 'z': 0}

    template_data = template_info['data']
    template_vox = template_info['vox_sizes']
    _, template_proj_1d, template_peaks = analyze_projections(template_data, template_vox)

    changes = []

    for axis in range(3):
        s_peaks = sample_peaks[axis]['num_peaks']
        t_peaks = template_peaks[axis]['num_peaks']

        if t_peaks > 0:
            ratio = s_peaks / t_peaks
            if ratio > 2.0:
                changes.append(f"Axis {axis}: too many peaks ({s_peaks} vs template {t_peaks}) - possible axis swap")
            elif ratio < 0.3:
                changes.append(f"Axis {axis}: too few peaks ({s_peaks} vs template {t_peaks}) - possible clipping or wrong template")

    if template_key.startswith('JRC2018U'):
        y_proj = sample_proj_1d[1]['filtered']
        center_idx = len(y_proj) // 2
        front_half = np.int64(np.sum(y_proj[:center_idx]))
        back_half = np.int64(np.sum(y_proj[center_idx:]))
        total = front_half + back_half
        if total > 0:
            asymmetry = (front_half - back_half) / total
            if asymmetry < -0.15:
                changes.append("180\u00b0 Y-axis rotation suggested (anterior-posterior flip)")

    if template_key.startswith('JRC2018U'):
        x_proj = sample_proj_1d[0]['filtered']
        center_idx = len(x_proj) // 2
        left_half = np.int64(np.sum(x_proj[:center_idx]))
        right_half = np.int64(np.sum(x_proj[center_idx:]))
        total = left_half + right_half
        if total > 0:
            x_asymmetry = abs(left_half - right_half) / total
            if x_asymmetry > 0.3:
                changes.append("X-axis highly asymmetric - possible 90\u00b0 rotation needed")

    # Z-axis (Dorsal-Ventral) mismatch: compare profile shape with template.
    # The brain has a distinct D-V profile; if flipped, cross-correlation with
    # the reversed template profile will be higher than with the normal one.
    if template_key.startswith('JRC2018U') and template_proj_1d is not None:
        z_sample = sample_proj_1d[2]['filtered']
        z_template = template_proj_1d[2]['filtered']
        if len(z_sample) > 10 and len(z_template) > 10:
            # Resample to common length for comparison
            common_len = min(len(z_sample), len(z_template))
            zs = np.interp(np.linspace(0, 1, common_len),
                           np.linspace(0, 1, len(z_sample)), z_sample)
            zt = np.interp(np.linspace(0, 1, common_len),
                           np.linspace(0, 1, len(z_template)), z_template)
            # Normalize
            zs_n = zs - np.mean(zs)
            zt_n = zt - np.mean(zt)
            denom = np.linalg.norm(zs_n) * np.linalg.norm(zt_n)
            if denom > 0:
                corr_normal = np.dot(zs_n, zt_n) / denom
                corr_flipped = np.dot(zs_n, zt_n[::-1]) / denom
                if corr_flipped > corr_normal + 0.2:
                    changes.append("Z-axis (dorsal-ventral) profile appears flipped vs template - 180\u00b0 X-axis rotation suggested")

    suggested_rotations = {'x': 0, 'y': 0, 'z': 0}
    for change in changes:
        if "180\u00b0 Y-axis" in change:
            suggested_rotations['y'] = 180
        if "90\u00b0 rotation" in change:
            suggested_rotations['z'] = 90
        if "180\u00b0 X-axis" in change:
            suggested_rotations['x'] = 180

    orientation_correct = len(changes) == 0
    return orientation_correct, changes, suggested_rotations


def generate_thumbnail(proj_2d, vox_sizes=None, axis=None, figsize=(4, 4), dpi=100):
    """Generate a base64 PNG thumbnail from a 2D max projection.

    Auto-crops to the bounding box of non-zero data (with a small margin)
    so the brain fills the thumbnail instead of being surrounded by black.
    The image is stretched to fill the full canvas for easy orientation
    comparison.
    """
    # Auto-crop to bounding box of signal
    img = proj_2d
    threshold = np.percentile(img[img > 0], 5) if np.any(img > 0) else 0
    mask = img > threshold
    rows = np.any(mask, axis=1)
    cols = np.any(mask, axis=0)
    if rows.any() and cols.any():
        rmin, rmax = np.where(rows)[0][[0, -1]]
        cmin, cmax = np.where(cols)[0][[0, -1]]
        # Add a small margin (5% of extent)
        margin_r = max(int((rmax - rmin) * 0.05), 2)
        margin_c = max(int((cmax - cmin) * 0.05), 2)
        rmin = max(rmin - margin_r, 0)
        rmax = min(rmax + margin_r, img.shape[0] - 1)
        cmin = max(cmin - margin_c, 0)
        cmax = min(cmax + margin_c, img.shape[1] - 1)
        img = img[rmin:rmax+1, cmin:cmax+1]

    fig, ax = plt.subplots(figsize=figsize)
    ax.imshow(img, cmap='gray', aspect='auto')
    ax.axis('off')

    buf = BytesIO()
    fig.savefig(buf, format='png', dpi=dpi, bbox_inches='tight', pad_inches=0.02)
    plt.close(fig)
    buf.seek(0)
    return base64.b64encode(buf.read()).decode('utf-8')


def generate_histogram(sample_proj_1d, sample_peaks, template_proj_1d, template_peaks, title=""):
    """Generate a base64 PNG histogram plot with 3 axis subplots."""
    fig, axes = plt.subplots(3, 1, figsize=(7, 5))
    axes_names = ['X (Left-Right)', 'Y (Anterior-Posterior)', 'Z (Dorsal-Ventral)']

    for axis in range(3):
        ax = axes[axis]
        s_coords = sample_proj_1d[axis]['physical_coords']
        s_filtered = sample_proj_1d[axis]['filtered']

        # Centre both profiles around 0 so midpoints align
        s_centre = s_coords[-1] / 2.0
        s_coords_c = s_coords - s_centre

        ax.plot(s_coords_c, s_filtered, 'b-', linewidth=1, label='Sample')

        if template_proj_1d is not None:
            t_coords = template_proj_1d[axis]['physical_coords']
            t_filtered = template_proj_1d[axis]['filtered']
            t_centre = t_coords[-1] / 2.0
            t_coords_c = t_coords - t_centre
            scale = np.max(s_filtered) / np.max(t_filtered) if np.max(t_filtered) > 0 else 1
            ax.plot(t_coords_c, t_filtered * scale, 'r--', linewidth=1, alpha=0.7, label='Template')

        s_peak_idx = sample_peaks[axis]['peaks']
        if len(s_peak_idx) > 0:
            ax.plot(s_coords_c[s_peak_idx], sample_peaks[axis]['heights'], 'go', markersize=4, label='Peaks')

        ax.set_title(f'{axes_names[axis]} - {sample_peaks[axis]["num_peaks"]} peaks', fontsize=8)
        ax.set_xlabel('Position (\u03bcm)' if axis == 2 else '', fontsize=7)
        ax.set_ylabel('Intensity', fontsize=7)
        ax.tick_params(axis='both', which='major', labelsize=6)
        if axis == 0:
            ax.legend(fontsize=6, loc='upper right')

    if title:
        fig.suptitle(title, fontsize=9, y=1.02)
    plt.tight_layout()

    buf = BytesIO()
    fig.savefig(buf, format='png', dpi=120, bbox_inches='tight')
    plt.close(fig)
    buf.seek(0)
    return base64.b64encode(buf.read()).decode('utf-8')


def save_to_orientations(image_path, image_info, automated_analysis):
    """Auto-save image info and automated analysis to orientations.json (merge, don't overwrite manual corrections)."""
    saved = {}
    if ORIENTATIONS_FILE.exists():
        saved = json.loads(ORIENTATIONS_FILE.read_text())

    entry = saved.get(image_path, {})

    # Merge image_info: preserve existing voxel_sizes if they exist and are not defaults
    existing_image_info = entry.get('image_info', {})
    if existing_image_info.get('voxel_sizes') and existing_image_info['voxel_sizes'] != [DEFAULT_VOXEL_SIZE, DEFAULT_VOXEL_SIZE, DEFAULT_VOXEL_SIZE]:
        # Preserve existing non-default voxel sizes
        image_info['voxel_sizes'] = existing_image_info['voxel_sizes']

    entry['image_info'] = image_info
    entry['automated_analysis'] = automated_analysis
    # Preserve existing manual_corrections, approved, etc.
    saved[image_path] = entry

    ORIENTATIONS_FILE.write_text(json.dumps(saved, indent=2))


def main():
    if len(sys.argv) < 2:
        print("Usage: python get_image_data.py <image_path> [bg_channel]")
        sys.exit(1)

    image_path = sys.argv[1]
    bg_channel = int(sys.argv[2]) if len(sys.argv) > 2 else 1

    # Load saved data to check for manual corrections
    saved_data = {}
    if ORIENTATIONS_FILE.exists():
        saved_data = json.loads(ORIENTATIONS_FILE.read_text())
    manual_corrections = saved_data.get(image_path, {}).get('manual_corrections', {})

    # --- Determine the image base name (last component without path) ---
    image_base = image_path.split('/')[-1]

    # --- Try loading from channel NRRDs first (authoritative after conversion) ---
    channels_dir = Path("channels")
    signal_nrrd = channels_dir / f"{image_base}_signal.nrrd"
    bg_nrrd = channels_dir / f"{image_base}_background.nrrd"
    loaded_from_nrrd = False

    if signal_nrrd.exists() and bg_nrrd.exists():
        try:
            print(f"Loading from channel NRRDs: {signal_nrrd.name}, {bg_nrrd.name}", file=sys.stderr)
            bg_data, bg_header = nrrd.read(str(bg_nrrd))
            sig_data_raw, _ = nrrd.read(str(signal_nrrd))

            # NRRD data is [X, Y, Z] — extract voxel sizes from space directions
            # Use norm of each row (not just diagonal) because 90° rotations
            # swap entire rows, creating off-diagonal entries
            sd = np.array(bg_header['space directions'], dtype=float)
            vx = float(np.linalg.norm(sd[0]))  # X spacing
            vy = float(np.linalg.norm(sd[1]))  # Y spacing
            vz = float(np.linalg.norm(sd[2]))  # Z spacing
            sample_vox = [vx, vy, vz]  # [X, Y, Z] matching data axes

            sig_data = sig_data_raw
            loaded_from_nrrd = True

            # Still need original shape from TIFF for metadata
            tiff_file = Path("Images") / f"{image_path}.tif"
            if not tiff_file.exists():
                tiff_file = Path("Images") / f"{image_path}.tiff"
            if tiff_file.exists():
                with tifffile.TiffFile(str(tiff_file)) as tif:
                    raw_data = tif.asarray(series=0)
                original_shape = list(raw_data.shape)
                num_channels = raw_data.shape[1] if raw_data.ndim == 4 else 1
            else:
                # Infer from NRRD
                original_shape = list(bg_data.shape)
                num_channels = 2  # we have signal + background

            print(f"  NRRD bg shape: {bg_data.shape}  voxel: {sample_vox}", file=sys.stderr)
        except Exception as nrrd_err:
            # Corrupted NRRD (e.g. partial write from a killed rotation) — fall through to TIFF
            print(f"  NRRD load failed ({nrrd_err}), removing corrupted files and falling back to TIFF", file=sys.stderr)
            loaded_from_nrrd = False
            for bad in (signal_nrrd, bg_nrrd):
                try:
                    bad.unlink()
                except OSError:
                    pass

    if not loaded_from_nrrd:
        # --- Fall back to loading from TIFF ---
        tiff_file = Path("Images") / f"{image_path}.tif"
        if not tiff_file.exists():
            tiff_file = Path("Images") / f"{image_path}.tiff"
            if not tiff_file.exists():
                print(json.dumps({"error": "Image not found"}))
                sys.exit(1)

        with tifffile.TiffFile(str(tiff_file)) as tif:
            raw_data = tif.asarray(series=0)
            tiff_vox = _extract_voxel_sizes(tif)  # [vz, vy, vx]
        original_shape = list(raw_data.shape)
        num_channels = raw_data.shape[1] if raw_data.ndim == 4 else 1

        # Create backup of original image if it doesn't exist
        backup_dir = Path("_backups") / tiff_file.parent.relative_to(Path("Images"))
        backup_file = backup_dir / tiff_file.name
        if not backup_file.exists():
            import shutil
            backup_dir.mkdir(parents=True, exist_ok=True)
            print(f"Creating backup: {backup_file}", file=sys.stderr)
            shutil.copy2(str(tiff_file), str(backup_file))

        # Extract channels from TIFF: data is [Z, C, Y, X] or [Z, Y, X]
        if raw_data.ndim == 4:
            sig_channel = 1 - bg_channel
            bg_raw = raw_data[:, bg_channel, :, :]   # [Z, Y, X]
            sig_raw = raw_data[:, sig_channel, :, :]  # [Z, Y, X]
        else:
            bg_raw = raw_data
            sig_raw = None

        # Ensure 3D
        if bg_raw.ndim != 3:
            print(f"Warning: bg_data has {bg_raw.ndim} dims, shape {bg_raw.shape}, fixing", file=sys.stderr)
            while bg_raw.ndim > 3:
                bg_raw = np.max(bg_raw, axis=0)

        # Transpose TIFF [Z, Y, X] → [X, Y, Z] to match NRRD convention
        bg_data = np.transpose(bg_raw, (2, 1, 0))
        sig_data = np.transpose(sig_raw, (2, 1, 0)) if sig_raw is not None else None

        # Voxel sizes: _extract_voxel_sizes returns [vz, vy, vx]
        # We need [vx, vy, vz] to match [X, Y, Z] data order
        sample_vox = [tiff_vox[2], tiff_vox[1], tiff_vox[0]]

        print(f"  TIFF shape: {raw_data.shape} → transposed bg: {bg_data.shape}  voxel: {sample_vox}", file=sys.stderr)

        # Auto-create channel NRRDs so they exist for future rotation / alignment
        try:
            from convert_tiff_to_nrrd import _make_nrrd_header
            channels_dir.mkdir(exist_ok=True)
            vx_w, vy_w, vz_w = sample_vox
            bg_hdr = _make_nrrd_header(bg_data, vx_w, vy_w, vz_w)
            nrrd.write(str(bg_nrrd), bg_data, bg_hdr)
            print(f"  Auto-created {bg_nrrd}  shape={bg_data.shape}", file=sys.stderr)
            if sig_data is not None:
                sig_hdr = _make_nrrd_header(sig_data, vx_w, vy_w, vz_w)
                nrrd.write(str(signal_nrrd), sig_data, sig_hdr)
                print(f"  Auto-created {signal_nrrd}  shape={sig_data.shape}", file=sys.stderr)
        except Exception as write_err:
            print(f"  Warning: could not auto-create channel NRRDs: {write_err}", file=sys.stderr)

    # --- From here, bg_data and sig_data are always [X, Y, Z] ---
    # --- sample_vox is [vx, vy, vz] matching axes ---

    # Thumbnails always use data-axis-order: key 'x' = projection along axis 0, etc.
    # The frontend's computeViewMapping handles any rotation-based reordering.
    # Do NOT reorder based on space_directions — that would undo rotations visually.
    proj_axis_for_anatomical = {'x': 0, 'y': 1, 'z': 2}

    # Determine template
    template_key = manual_corrections.get('template')
    if not template_key:
        if "VNC" in image_path:
            template_key = "JRCVNC2018U_template"
        else:
            template_key = "JRC2018U_template_lps"

    # Load template
    template_info = load_template(template_key)
    template_vox = template_info['vox_sizes'] if template_info else [0.5, 0.5, 0.5]

    # Analyze background channel
    sample_proj_2d, sample_proj_1d, sample_peaks = analyze_projections(bg_data, sample_vox)

    # Convert dict {0: proj, 1: proj, 2: proj} to list [proj0, proj1, proj2]
    sample_proj_2d = [sample_proj_2d[i] for i in range(3)]

    # Analyze template
    template_proj_2d = None
    template_proj_1d = None
    template_peaks_data = None
    if template_info is not None:
        template_proj_2d, template_proj_1d, template_peaks_data = analyze_projections(
            template_info['data'], template_vox
        )

    # Check orientation
    orientation_correct, changes, suggested_rotations = check_orientation(
        sample_peaks, sample_proj_1d, template_key, template_info
    )

    if 'template_correct' in manual_corrections:
        orientation_correct = manual_corrections['template_correct']

    # Generate thumbnails from [X, Y, Z] data — one per data axis
    # key 'x' = projection along axis 0, key 'y' = along axis 1, key 'z' = along axis 2
    original_thumbnails = {}
    with concurrent.futures.ProcessPoolExecutor() as executor:
        futures = {}
        for i, key in enumerate(['x', 'y', 'z']):
            futures[executor.submit(generate_thumbnail, sample_proj_2d[i], sample_vox, i)] = key
        for future in concurrent.futures.as_completed(futures):
            original_thumbnails[futures[future]] = future.result()

    template_thumbnails = {}
    if template_proj_2d is not None:
        with concurrent.futures.ProcessPoolExecutor() as executor:
            futures = {}
            for i, key in enumerate(['x', 'y', 'z']):
                futures[executor.submit(generate_thumbnail, template_proj_2d[i], template_vox, i)] = key
            for future in concurrent.futures.as_completed(futures):
                template_thumbnails[futures[future]] = future.result()

    signal_thumbnails = {}
    if sig_data is not None:
        sig_proj_2d, _, _ = analyze_projections(sig_data, sample_vox)
        sig_proj_2d = [sig_proj_2d[i] for i in range(3)]
        with concurrent.futures.ProcessPoolExecutor() as executor:
            futures = {}
            for i, key in enumerate(['x', 'y', 'z']):
                futures[executor.submit(generate_thumbnail, sig_proj_2d[i], sample_vox, i)] = key
            for future in concurrent.futures.as_completed(futures):
                signal_thumbnails[futures[future]] = future.result()

    # Generate histograms
    histogram = generate_histogram(
        sample_proj_1d, sample_peaks,
        template_proj_1d, template_peaks_data,
        title=f'{image_path} vs {template_key}'
    )

    # Summaries
    template_summary = {}
    if template_info is not None:
        template_summary = {
            "shape": list(template_info['shape']),
            "voxel_sizes": template_info['vox_sizes'],
            "physical_size": [round(s, 1) for s in template_info['physical_size']],
        }

    sample_summary = {
        "shape": original_shape,
        "num_channels": num_channels,
        "background_channel": bg_channel,
        "voxel_sizes": sample_vox,
        "physical_size": [round(s * v, 1) for s, v in zip(bg_data.shape, sample_vox)],
    }

    peak_summary = {}
    for axis in range(3):
        peak_summary[axis] = {
            'sample_peaks': sample_peaks[axis]['num_peaks'],
            'template_peaks': template_peaks_data[axis]['num_peaks'] if template_peaks_data else 0,
        }

    # Auto-save analysis to orientations.json
    image_info_for_json = {
        "shape": original_shape,
        "num_channels": num_channels,
        "background_channel": bg_channel,
        "voxel_sizes": sample_vox,
    }
    automated_analysis_for_json = {
        "detected_template": template_key,
        "orientation_correct": orientation_correct,
        "suggested_changes": changes,
        "suggested_rotations": suggested_rotations,
        "peak_summary": {str(k): v for k, v in peak_summary.items()},
        "template_info": template_summary,
    }
    save_to_orientations(image_path, image_info_for_json, automated_analysis_for_json)

    # Build response
    result = {
        "name": image_path,
        "template": template_key,
        "template_correct": orientation_correct,
        "original_thumbnails": original_thumbnails,
        "template_thumbnails": template_thumbnails,
        "signal_thumbnails": signal_thumbnails,
        "histogram": histogram,
        "changes_needed": changes,
        "suggested_rotations": suggested_rotations,
        "template_info": template_summary,
        "sample_info": sample_summary,
        "peak_summary": peak_summary,
        "background_channel": bg_channel,
        "num_channels": num_channels,
        "loaded_from_nrrd": loaded_from_nrrd,
    }

    print(json.dumps(result))


if __name__ == "__main__":
    main()
