#!/usr/bin/env python3
"""Clean up cascading .original backup files and move true originals to _backups/."""
from pathlib import Path
import shutil

images_dir = Path("Images")
backup_root = Path("_backups")

# Find all .original files grouped by base name
originals = {}
for f in images_dir.rglob("*.tif"):
    name = f.name
    if ".original" not in name:
        continue
    # Find the base name (strip all .original)
    base = name
    while ".original" in base:
        base = base.replace(".original", "", 1)
    key = str(f.parent / base)
    if key not in originals:
        originals[key] = []
    originals[key].append(f)

# For each base file, keep the deepest .original as the true backup
for base_key, files in originals.items():
    files.sort(key=lambda x: x.name.count(".original"), reverse=True)
    true_original = files[0]

    base_path = Path(base_key)
    rel = base_path.parent.relative_to(images_dir)
    backup_dir = backup_root / rel
    backup_dir.mkdir(parents=True, exist_ok=True)
    dest = backup_dir / base_path.name

    if not dest.exists():
        print(f"BACKUP: {true_original.name} -> {dest}")
        shutil.copy2(str(true_original), str(dest))
    else:
        print(f"SKIP (already backed up): {base_path.name}")

    for f in files:
        print(f"  DELETE: {f.name}")
        f.unlink()

print("Done")
