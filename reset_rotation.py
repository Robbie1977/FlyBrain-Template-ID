#!/usr/bin/env python3
"""
Reset image to original orientation by restoring from backup.
"""

import sys
from pathlib import Path
import shutil


def main():
    if len(sys.argv) < 2:
        print("Usage: python reset_rotation.py <image_path>")
        sys.exit(1)

    image_path = sys.argv[1]

    tiff_file = Path("Images") / f"{image_path}.tif"
    if not tiff_file.exists():
        tiff_file = Path("Images") / f"{image_path}.tiff"
        if not tiff_file.exists():
            print("Error: Image not found")
            sys.exit(1)

    # Check for backup file
    backup_file = tiff_file.with_suffix('.original' + tiff_file.suffix)
    if not backup_file.exists():
        print("Error: No backup file found - image may not have been rotated yet")
        sys.exit(1)

    # Restore from backup
    print(f"Restoring {tiff_file.name} from backup...")
    shutil.copy2(str(backup_file), str(tiff_file))
    print("Rotation reset successfully")


if __name__ == "__main__":
    main()