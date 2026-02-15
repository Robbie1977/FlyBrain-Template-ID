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

# ── Persistent state files ──
# These must live on mounted volumes so they survive container restarts.
# Store them in /data/processing/ which is a mounted volume.

# orientations.json — image review/approval state
if [ ! -f /data/processing/orientations.json ]; then
    # Migrate from old location if it exists in the container
    if [ -f /app/orientations.json ] && [ ! -L /app/orientations.json ]; then
        echo "  Migrating orientations.json to /data/processing/"
        cp /app/orientations.json /data/processing/orientations.json
        rm /app/orientations.json
    else
        echo "{}" > /data/processing/orientations.json
    fi
fi
# Create symlink so the app still reads /app/orientations.json
if [ -f /app/orientations.json ] && [ ! -L /app/orientations.json ]; then
    rm /app/orientations.json
fi
if [ ! -L /app/orientations.json ]; then
    ln -s /data/processing/orientations.json /app/orientations.json
    echo "  orientations.json → /data/processing/orientations.json"
fi

# alignment_progress.json — alignment queue/job state
if [ ! -f /data/processing/alignment_progress.json ]; then
    if [ -f /app/alignment_progress.json ] && [ ! -L /app/alignment_progress.json ]; then
        echo "  Migrating alignment_progress.json to /data/processing/"
        cp /app/alignment_progress.json /data/processing/alignment_progress.json
        rm /app/alignment_progress.json
    fi
fi
if [ -f /app/alignment_progress.json ] && [ ! -L /app/alignment_progress.json ]; then
    rm /app/alignment_progress.json
fi
if [ ! -L /app/alignment_progress.json ]; then
    ln -s /data/processing/alignment_progress.json /app/alignment_progress.json
    echo "  alignment_progress.json → /data/processing/alignment_progress.json"
fi

echo "=== Starting server ==="
exec "$@"
