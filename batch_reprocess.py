#!/usr/bin/env python3
"""Batch reprocess all images to update orientations.json with correct voxel sizes and new analysis."""

import json
import subprocess
import sys
import time
from pathlib import Path

def main():
    # Get image list from server
    images_dir = Path("Images")
    tiffs = []
    for f in sorted(images_dir.rglob("*.tif")):
        rel = str(f.relative_to(images_dir)).replace('.tif', '')
        tiffs.append(rel)
    for f in sorted(images_dir.rglob("*.tiff")):
        rel = str(f.relative_to(images_dir)).replace('.tiff', '')
        tiffs.append(rel)

    print(f"Found {len(tiffs)} images to reprocess")

    success = 0
    failed = 0

    for i, img in enumerate(tiffs, 1):
        print(f"\n[{i}/{len(tiffs)}] Processing: {img}")
        start = time.time()
        try:
            result = subprocess.run(
                [sys.executable, "get_image_data.py", img],
                capture_output=True, text=True, timeout=180
            )
            elapsed = time.time() - start

            if result.returncode != 0:
                print(f"  FAILED ({elapsed:.1f}s): {result.stderr[:200]}")
                failed += 1
                continue

            # Parse to verify valid JSON
            data = json.loads(result.stdout)
            vox = data.get('sample_info', {}).get('voxel_sizes', [])
            print(f"  OK ({elapsed:.1f}s) voxel_sizes={vox}")
            success += 1

        except subprocess.TimeoutExpired:
            print(f"  TIMEOUT after 180s")
            failed += 1
        except json.JSONDecodeError as e:
            print(f"  JSON ERROR: {e}")
            failed += 1
        except Exception as e:
            print(f"  ERROR: {e}")
            failed += 1

    print(f"\n{'='*50}")
    print(f"Done: {success} succeeded, {failed} failed out of {len(tiffs)}")

if __name__ == "__main__":
    main()
