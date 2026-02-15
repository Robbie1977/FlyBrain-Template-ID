#!/bin/bash
# Script to align a single image to VFB templates using CMTK and generate thumbnails
# Supports resume: skips stages whose output already exists.
# Writes per-stage timing to corrected/{IMAGE_BASE}_alignment_progress.json

set -e

# Use CMTK_BIN env var if set, else try ./CMTK/bin, else assume PATH
if [ -n "$CMTK_BIN" ]; then
    :
elif [ -d "./CMTK/bin" ]; then
    CMTK_BIN="./CMTK/bin"
else
    # Assume CMTK is on PATH — use directory of the registration binary
    # NeuroDebian installs to /usr/lib/cmtk/bin; manual builds often use /opt/cmtk/bin
    CMTK_BIN="$(dirname "$(command -v registration 2>/dev/null || echo /usr/lib/cmtk/bin/registration)")"
fi

echo "Using CMTK from: $CMTK_BIN"

# Test CMTK
if ! "$CMTK_BIN/registration" --version >/dev/null 2>&1; then
    echo "ERROR: CMTK not found at $CMTK_BIN"
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

# --- Progress tracking helpers ---
CURRENT_STAGE=""
update_progress() {
    source venv/bin/activate 2>/dev/null || true
    python3 update_alignment_progress.py "$IMAGE_BASE" "$@" 2>/dev/null || true
}

# On any error, record failure in progress JSON
trap 'update_progress fail "Script failed at stage: $CURRENT_STAGE"' ERR

# Mark alignment as started
update_progress start

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

# --- Resume detection ---
# Determine which stage to start from based on existing output files
START_STAGE=0
thumbnails_file="corrected/${base}_alignment_thumbnails.json"

if [ -f "$thumbnails_file" ] && [ -f "$output_signal_file" ] && [ -f "$output_bg_file" ]; then
    echo "  Alignment already complete for $IMAGE_BASE"
    update_progress complete
    exit 0
elif [ -f "$output_signal_file" ] && [ -f "$output_bg_file" ]; then
    START_STAGE=6
    echo "  Resuming from thumbnail generation (stage 6)"
elif [ -d "$xform_dir/warp.xform" ]; then
    START_STAGE=4
    echo "  Resuming from reformatx (stage 4)"
elif [ -d "$xform_dir/affine.xform" ]; then
    START_STAGE=3
    echo "  Resuming from warp (stage 3)"
elif [ -f "$xform_dir/initial.xform" ]; then
    START_STAGE=2
    echo "  Resuming from affine registration (stage 2)"
fi

# Set moving_bg to bg_file (no orientation correction needed as it's already done)
moving_bg="$bg_file"

# ────────────────────────────────────────────
# Stage 0: Set space to LPS for input files
# ────────────────────────────────────────────
if [ $START_STAGE -le 0 ]; then
    CURRENT_STAGE="set_lps"
    update_progress stage_start set_lps
    echo "  Setting space to left-posterior-superior for input files..."
    source venv/bin/activate && python3 -c "
import sys, nrrd

sig, bg = sys.argv[1], sys.argv[2]

data, header = nrrd.read(sig)
header['space'] = 'left-posterior-superior'
nrrd.write(sig, data, header)

data, header = nrrd.read(bg)
header['space'] = 'left-posterior-superior'
nrrd.write(bg, data, header)

print('Space set to LPS for input files')
" "$signal_file" "$bg_file"
    update_progress stage_end set_lps
fi

# ────────────────────────────────────────────
# Stage 1: Create initial affine transformation
# ────────────────────────────────────────────
if [ $START_STAGE -le 1 ]; then
    CURRENT_STAGE="initial_affine"
    update_progress stage_start initial_affine
    echo "  Creating initial affine transformation..."
    "$CMTK_BIN/make_initial_affine" \
        --principal-axes \
        "$template" "$moving_bg" \
        "$xform_dir/initial.xform"
    update_progress stage_end initial_affine
fi

# ────────────────────────────────────────────
# Stage 2: Affine registration
# ────────────────────────────────────────────
if [ $START_STAGE -le 2 ]; then
    CURRENT_STAGE="affine_registration"
    update_progress stage_start affine_registration
    echo "  Running CMTK affine registration..."
    "$CMTK_BIN/registration" \
        --initial "$xform_dir/initial.xform" \
        --dofs 6,12 \
        --auto-multi-levels 4 \
        --outlist "$xform_dir/affine.xform" \
        "$template" "$moving_bg"
    update_progress stage_end affine_registration
fi

# ────────────────────────────────────────────
# Stage 3: Non-linear warping
# ────────────────────────────────────────────
if [ $START_STAGE -le 3 ]; then
    CURRENT_STAGE="warp"
    update_progress stage_start warp
    echo "  Running CMTK non-linear warping..."
    "$CMTK_BIN/warp" \
        --outlist "$xform_dir/warp.xform" \
        --grid-spacing 80 \
        --exploration 30 \
        --coarsest 4 \
        --accuracy 0.4 \
        --refine 4 \
        --energy-weight 1e-1 \
        "$template" "$moving_bg" "$xform_dir/affine.xform"
    update_progress stage_end warp
fi

# ────────────────────────────────────────────
# Stage 4: Apply transformation to signal
# ────────────────────────────────────────────
if [ $START_STAGE -le 4 ]; then
    CURRENT_STAGE="reformat_signal"
    update_progress stage_start reformat_signal
    echo "  Applying transformation to signal..."
    "$CMTK_BIN/reformatx" \
        --floating "$signal_file" \
        --outfile "$output_signal_file" \
        "$template" "$xform_dir/warp.xform"
    update_progress stage_end reformat_signal
fi

# ────────────────────────────────────────────
# Stage 5: Apply transformation to background
# ────────────────────────────────────────────
if [ $START_STAGE -le 5 ]; then
    CURRENT_STAGE="reformat_background"
    update_progress stage_start reformat_background
    echo "  Applying transformation to background..."
    "$CMTK_BIN/reformatx" \
        --floating "$moving_bg" \
        --outfile "$output_bg_file" \
        "$template" "$xform_dir/warp.xform"
    update_progress stage_end reformat_background
fi

# Clean up temp orientation-corrected file if different from original
if [[ $moving_bg != $bg_file ]]; then
    rm "$moving_bg"
fi

# ────────────────────────────────────────────
# Stage 6: Generate thumbnails
# ────────────────────────────────────────────
if [ $START_STAGE -le 6 ]; then
    CURRENT_STAGE="thumbnails"
    update_progress stage_start thumbnails
    echo "  Generating alignment thumbnails..."
    source venv/bin/activate && python3 -c "
import sys, json, base64, io
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import nrrd
import numpy as np

template_path = sys.argv[1]
output_bg_path = sys.argv[2]
image_base = sys.argv[3]
template_name = sys.argv[4]
ts = sys.argv[5]
output_json = sys.argv[6]
output_signal_path = sys.argv[7] if len(sys.argv) > 7 else None

def to_png_base64(fig):
    buf = io.BytesIO()
    fig.savefig(buf, format='png', bbox_inches='tight', pad_inches=0)
    plt.close(fig)
    buf.seek(0)
    return base64.b64encode(buf.read()).decode('utf-8')

def generate_thumbnail(data, title='', figsize=(4,4)):
    fig, ax = plt.subplots(figsize=figsize, dpi=100)
    ax.imshow(data, cmap='gray', aspect='auto')
    ax.set_title(title)
    ax.axis('off')
    return to_png_base64(fig)

def normalise(arr):
    mn, mx = arr.min(), arr.max()
    if mx == mn:
        return np.zeros_like(arr, dtype=np.float32)
    return (arr - mn).astype(np.float32) / (mx - mn)

def generate_overlay(template_proj, aligned_proj, title='', figsize=(4,4)):
    # Magenta = template, Green = aligned (standard neuroscience overlay)
    t = normalise(template_proj)
    a = normalise(aligned_proj)
    h, w = t.shape[:2]
    # Resize aligned to match template if needed
    if a.shape != t.shape:
        from scipy.ndimage import zoom
        zoom_factors = (h / a.shape[0], w / a.shape[1])
        a = zoom(a, zoom_factors, order=1)
    rgb = np.zeros((h, w, 3), dtype=np.float32)
    rgb[..., 0] = t          # Red   ← template (magenta = R+B)
    rgb[..., 1] = a          # Green ← aligned
    rgb[..., 2] = t          # Blue  ← template (magenta = R+B)
    fig, ax = plt.subplots(figsize=figsize, dpi=100)
    ax.imshow(np.clip(rgb, 0, 1), aspect='auto')
    ax.set_title(title)
    ax.axis('off')
    return to_png_base64(fig)

# Load data
template_data, _ = nrrd.read(template_path)
aligned_bg_data, _ = nrrd.read(output_bg_path)

axes = [0, 1, 2]
template_projs = [np.max(template_data, axis=ax) for ax in axes]
aligned_projs  = [np.max(aligned_bg_data, axis=ax) for ax in axes]

thumbnails = {}
for i, axis in enumerate(['x', 'y', 'z']):
    thumbnails[f'{axis}_template'] = generate_thumbnail(template_projs[i], f'Template {axis.upper()}-axis')
    thumbnails[f'{axis}_aligned']  = generate_thumbnail(aligned_projs[i],  f'Aligned {axis.upper()}-axis')
    thumbnails[f'{axis}_overlay']  = generate_overlay(template_projs[i], aligned_projs[i], f'Overlay {axis.upper()}-axis')

# Also generate signal channel thumbnails if available
if output_signal_path:
    try:
        signal_data, _ = nrrd.read(output_signal_path)
        signal_projs = [np.max(signal_data, axis=ax) for ax in axes]
        for i, axis in enumerate(['x', 'y', 'z']):
            thumbnails[f'{axis}_signal'] = generate_thumbnail(signal_projs[i], f'Signal {axis.upper()}-axis')
        print('Signal thumbnails included')
    except Exception as e:
        print(f'Warning: could not load signal file: {e}')

result = {
    'image_base': image_base,
    'template': template_name,
    'thumbnails': thumbnails,
    'aligned_at': ts
}

with open(output_json, 'w') as f:
    json.dump(result, f, indent=2)

print('Thumbnails generated')
" "$template" "$output_bg_file" "$IMAGE_BASE" "$template" "$timestamp" "corrected/${base}_alignment_thumbnails.json" "$output_signal_file"
    update_progress stage_end thumbnails
fi

# ────────────────────────────────────────────
# Stage 7: Copy to output directory (if OUTPUT_DIR is set)
# ────────────────────────────────────────────
if [ -n "$OUTPUT_DIR" ] && [ -d "$OUTPUT_DIR" ]; then
    CURRENT_STAGE="copy_output"
    update_progress stage_start copy_output
    echo "  Copying final files to output directory..."
    mkdir -p "$OUTPUT_DIR"
    cp -f "$output_signal_file" "$OUTPUT_DIR/" 2>/dev/null || true
    cp -f "$output_bg_file" "$OUTPUT_DIR/" 2>/dev/null || true
    cp -f "corrected/${base}_alignment_thumbnails.json" "$OUTPUT_DIR/" 2>/dev/null || true
    cp -f "corrected/${base}_alignment_progress.json" "$OUTPUT_DIR/" 2>/dev/null || true
    update_progress stage_end copy_output
fi

# Mark complete
update_progress complete
echo "  Alignment complete for $IMAGE_BASE"