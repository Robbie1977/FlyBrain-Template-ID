#!/bin/bash
set -e

# ============================================================
# Docker entrypoint for FlyBrain Template ID
#
# Creates symlinks so all scripts see their expected directory
# names while actual data lives on the Docker volumes.
#
# Volume layout:
#   /data/input       → TIFF images (mounted read-write)
#   /data/processing  → intermediate files (channels, nrrd, xforms, backups)
#   /data/output      → final aligned files + thumbnails
# ============================================================

echo "=== FlyBrain Template ID — Docker Entrypoint ==="

# Ensure volume subdirectories exist
mkdir -p /data/input
mkdir -p /data/processing/channels
mkdir -p /data/processing/nrrd_output
mkdir -p /data/processing/corrected
mkdir -p /data/processing/_backups
mkdir -p /data/output

# Create symlinks from app working directory to volume paths
# (only if they don't already exist as real directories)
for link in Images:input channels:processing/channels nrrd_output:processing/nrrd_output \
            corrected:processing/corrected _backups:processing/_backups \
            aligned_output:output; do
    local_name="${link%%:*}"
    volume_path="/data/${link#*:}"
    target="/app/${local_name}"

    # Remove existing symlink or empty dir
    if [ -L "$target" ]; then
        rm "$target"
    elif [ -d "$target" ] && [ -z "$(ls -A "$target" 2>/dev/null)" ]; then
        rmdir "$target"
    fi

    # Create symlink if target doesn't exist as a populated directory
    if [ ! -d "$target" ]; then
        ln -s "$volume_path" "$target"
        echo "  ${local_name} → ${volume_path}"
    else
        echo "  ${local_name} already exists, skipping symlink"
    fi
done

# Generate LPS template variants if they don't exist yet
if [ ! -f /app/JRC2018U_template_lps.nrrd ]; then
    echo "  Generating JRC2018U_template_lps.nrrd ..."
    python3 -c "
import nrrd
data, header = nrrd.read('JRC2018U_template.nrrd')
header['space'] = 'left-posterior-superior'
nrrd.write('JRC2018U_template_lps.nrrd', data, header)
"
fi

if [ ! -f /app/JRCVNC2018U_template_lps.nrrd ]; then
    echo "  Generating JRCVNC2018U_template_lps.nrrd ..."
    python3 -c "
import nrrd
data, header = nrrd.read('JRCVNC2018U_template.nrrd')
header['space'] = 'left-posterior-superior'
nrrd.write('JRCVNC2018U_template_lps.nrrd', data, header)
"
fi

# Initialise orientations.json if missing (on the processing volume)
if [ ! -f /app/orientations.json ]; then
    echo "{}" > /app/orientations.json
fi

echo "=== Starting server ==="
exec "$@"
