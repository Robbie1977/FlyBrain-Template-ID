# FlyBrain-Template-ID — Technical Documentation

> **Last updated:** 2026-02-14
> **Repository:** [Robbie1977/FlyBrain-Template-ID](https://github.com/Robbie1977/FlyBrain-Template-ID)

## 1. System Overview

This is a web application for reviewing and correcting the anatomical orientation of fly brain microscopy images against standard reference templates. A researcher loads a TIFF sample image, compares its maximum-intensity projections (MIPs) with a template, interactively adjusts orientation if needed, then approves it for downstream CMTK alignment.

### Architecture Diagram

```
┌──────────────────────────────────────────────────────────┐
│  Browser                                                  │
│  ┌─ public/index.html ─────────────────────────────────┐  │
│  │  Image selector / navigation                         │  │
│  │  Thumbnail cards (3 axes) · Rotation toolbar         │  │
│  │  Histograms · Manual corrections · Approve           │  │
│  └──────────────────────────────────────────────────────┘  │
│  ┌─ public/alignment-status.html ───────────────────────┐  │
│  │  Alignment queue overview · Queue/Preparing/Processing│  │
│  │  Completed/Failed jobs · Queue All Approved           │  │
│  └──────────────────────────────────────────────────────┘  │
│              ▲ JSON over HTTP ▼                            │
├───────────────────────────────────────────────────────────┤
│  Express server (server.js:3000)                          │
│  ┌─ Orientation Review API ────────────────────────────┐  │
│  │  GET  /api/images        → list TIFFs               │  │
│  │  GET  /api/image?name=   → exec get_image_data.py   │  │
│  │  POST /api/rotate        → exec apply_rotation.py   │  │
│  │  POST /api/reset         → exec reset_rotation.py   │  │
│  │  POST /api/save          → write orientations.json  │  │
│  │  POST /api/approve       → write orientations.json  │  │
│  │  GET  /api/saved         → read orientations.json   │  │
│  └─────────────────────────────────────────────────────┘  │
│  ┌─ Alignment Queue API ──────────────────────────────┐   │
│  │  POST /api/queue-alignment  → prepare & queue       │  │
│  │  GET  /api/alignment-status → job status list       │  │
│  │  GET  /api/alignment-thumbnails → result images     │  │
│  │  POST /api/reset-alignment  → clear job status      │  │
│  └─────────────────────────────────────────────────────┘  │
│  ┌─ Alignment Queue Engine (in-memory) ────────────────┐  │
│  │  prepareAndQueue() → convert_tiff_to_nrrd.py        │  │
│  │                    → split_channels.py               │  │
│  │  processAlignmentQueue() → align_single_cmtk.sh     │  │
│  │  detectRunningAlignments() → monitor existing procs  │  │
│  └─────────────────────────────────────────────────────┘  │
├───────────────────────────────────────────────────────────┤
│  Scripts                                                   │
│    Python (venv): get_image_data.py, apply_rotation.py,   │
│      reset_rotation.py, split_channels.py,                │
│      convert_tiff_to_nrrd.py                              │
│    Bash: align_single_cmtk.sh → CMTK/bin/{registration,  │
│                                             reformatx}    │
├───────────────────────────────────────────────────────────┤
│  Filesystem                                                │
│    Images/<submitter>/*.tif    – source TIFFs (4D ZCYX)   │
│    _backups/<submitter>/*.tif  – pristine originals        │
│    *.nrrd                      – template volumes          │
│    orientations.json           – per-image state           │
│    nrrd_output/                – converted NRRDs from TIFF │
│    channels/                   – split signal/background   │
│    corrected/                  – CMTK alignment outputs    │
└───────────────────────────────────────────────────────────┘
```

---

## 2. Directory Layout

| Path | Purpose |
|---|---|
| `server.js` | Express HTTP server (port 3000) with orientation review and alignment queue APIs |
| `public/index.html` | Orientation review frontend (HTML + CSS + JS) |
| `public/alignment-status.html` | Alignment queue status/monitoring frontend |
| `get_image_data.py` | Load TIFF, compare to template, output JSON with base64 thumbnails |
| `apply_rotation.py` | Apply 90° rotation(s) to TIFF, overwrite in-place |
| `reset_rotation.py` | Restore TIFF from `_backups/` (or legacy `.original`) |
| `split_channels.py` | Split multi-channel NRRD into separate signal and background files |
| `convert_tiff_to_nrrd.py` | Convert TIFF images to NRRD format with metadata preservation |
| `align_single_cmtk.sh` | Run CMTK registration and reformatting for a single image |
| `orientations.json` | Persistent per-image state (auto-analysis + manual corrections + approval) |
| `Images/` | Source TIFF images, organised by submitter subdirectory |
| `_backups/` | Pristine original TIFFs, mirrors `Images/` structure |
| `JRC2018U_template_lps.nrrd` | Brain template -- LPS orientation (primary) |
| `JRC2018U_template.nrrd` | Brain template -- original orientation |
| `JRCVNC2018U_template.nrrd` | VNC template |
| `JRCVNC2018U_template_lps.nrrd` | VNC template -- LPS orientation |
| `nrrd_output/` | Converted NRRDs from TIFF (created by `convert_tiff_to_nrrd.py`) |
| `channels/` | Split background/signal NRRDs (created by `split_channels.py`) |
| `corrected/` | CMTK alignment outputs: `*_xform/` transforms, `*_aligned.nrrd` results, `*_alignment_thumbnails.json` |
| `CMTK/bin/` | CMTK command-line tools (`registration`, `reformatx`, etc.) |
| `venv/` | Python virtual environment |

---

## 3. Server API Reference (`server.js`)

### `GET /api/images`
Lists all TIFF images in `Images/` recursively.

- Filters out files containing `.original` in the name (legacy backup artefacts).
- Returns JSON array of strings: `["DeepanshuSingh/Brain_Fru11.12AD_FD6DBD_FB1.1_NC82_S1", ...]`
- Each entry is the relative path from `Images/` with the `.tif` extension stripped.

### `GET /api/image?name=<path>&bg_channel=<0|1>`
Runs `get_image_data.py` and returns its JSON output.

- `name`: relative image path (URL-encoded, no extension).
- `bg_channel`: which channel to treat as background/neuropil (default `1`).
- Timeout: 120 seconds. Max buffer: 50 MB (thumbnails are large base64 strings).
- Runs inside `venv` via `source venv/bin/activate && python get_image_data.py "<name>" <bg_channel>`.

### `POST /api/rotate?name=<path>`
Body: `{ "rotations": { "x": 0, "y": 90, "z": 0 } }`

- Calls `apply_rotation.py "<name>" '<json>'` to rotate the TIFF on disk.
- The TIFF is modified **in-place** (both channels).
- After success, resets `manual_corrections.rotations` to `{ x: 0, y: 0, z: 0 }` in `orientations.json` (since the rotation has been baked into the file).
- After success, the frontend reloads the image to get updated thumbnails.

### `POST /api/reset?name=<path>`
Calls `reset_rotation.py "<name>"` to restore the TIFF from its backup.

### `POST /api/save?name=<path>`
Body: `{ "template": "JRC2018U_template_lps", "template_correct": true, "background_channel": 1, "rotations": { "x": 0, "y": 0, "z": 0 } }`

- Merges `manual_corrections` into `orientations.json` entry.
- Preserves auto-analysis data and approval status.

### `POST /api/approve?name=<path>`
Sets `approved: true` and `approved_at` timestamp in `orientations.json`.
Requires the image to have been saved first.

### `GET /api/saved`
Returns the full `orientations.json` as a JSON object.

### `POST /api/queue-alignment`
Body: `{ "image_base": "Brain_Fru11.12AD_FD6DBD_FB1.1_NC82_S1" }`

Queues an approved image for CMTK alignment. The `image_base` is the filename without directory prefix or extension.

- **Prerequisite checks:** The image must exist in `orientations.json` and have `approved: true`.
- **Duplicate prevention:** Returns success immediately if the image is already being prepared, is already queued, or is currently processing.
- **Preparation pipeline:** If the NRRD or channel files are missing, the server responds immediately with status `preparing` and runs conversion/splitting in the background:
  1. If `nrrd_output/<image_base>.nrrd` is missing → runs `convert_tiff_to_nrrd.py` in background
  2. If `channels/<image_base>_signal.nrrd` or `channels/<image_base>_background.nrrd` is missing → runs `split_channels.py` in background
  3. Once all prerequisites exist, the image is automatically moved to `queued` status
- **If all prerequisites exist:** The image is queued immediately.
- Returns: `{ "success": true, "message": "..." }` with context-specific message.

### `GET /api/alignment-status`
Returns a JSON array of all alignment job objects:
```json
[
  {
    "image_base": "Brain_Fru11.12AD_FD6DBD_FB1.1_NC82_S1",
    "status": "queued",
    "progress": 0,
    "error": "",
    "queued_at": "2026-02-14T10:55:48.599Z",
    "queue_position": 1,
    "is_current": false
  }
]
```

Status values: `preparing` | `queued` | `processing` | `completed` | `failed`.
Additional fields on completion: `completed_at` (ISO timestamp). On failure: `error` (string).

### `GET /api/alignment-thumbnails?image_base=<name>`
Returns the alignment result thumbnails for a completed job.

- Reads from `corrected/<image_base>_alignment_thumbnails.json`.
- Returns JSON with `thumbnails` object containing base64-encoded PNG images for each axis (template and aligned versions).
- Returns 404 if thumbnails not found (alignment may not be complete).

### `POST /api/reset-alignment`
Body: `{ "image_base": "Brain_Fru11.12AD_FD6DBD_FB1.1_NC82_S1" }`

Clears alignment tracking for an image. Removes it from the in-memory status map and the queue (if present). Does **not** delete any files on disk.

---

## 4. Python Scripts

### 4.1. `get_image_data.py`

**Purpose:** Load a TIFF sample, extract metadata, compare against an NRRD template, generate thumbnails/histograms, and return JSON to the server.

**Invocation:** `python get_image_data.py "<image_path>" [bg_channel]`

**Key functions:**

#### `_extract_voxel_sizes(tif)` (lines ~35–97)
Extracts physical voxel sizes `[vz, vy, vx]` in µm from TIFF metadata.

1. **ImageJ metadata** (most common for FlyBrain TIFFs):
   - `spacing` key → Z voxel size
   - `XResolution` tag → `(numerator, denominator)` where pixel size = `denominator / numerator` µm
   - `YResolution` tag → same
   - Respects `unit` tag (µm, nm conversion)
2. **OME-XML metadata** (fallback):
   - Parses `PhysicalSizeX/Y/Z` from the `<Pixels>` element
3. **Default:** `DEFAULT_VOXEL_SIZE = 0.5` µm if nothing found.
   - Rationale: typical confocal fly brain resolution is ~0.3–0.6 µm; 0.5 is a safe middle ground vs. the previous default of 1.0 which made physical extents too large.

#### `load_template(template_key)` (lines ~105–118)
Loads and caches NRRD template data. Returns dict with `data`, `header`, `vox_sizes`, `shape`, `physical_size`.

Template selection logic (in `main()`):
- If image path contains `"VNC"` → `JRCVNC2018U_template`
- Otherwise → `JRC2018U_template_lps`

#### `analyze_projections(data, vox_sizes)` (lines ~122–158)
Generates 2D max-intensity projections and 1D filtered profiles for each axis.

- `projections_2d[axis]` = `np.max(data, axis=axis)` — the MIP along that axis
- `projections_1d[axis]` = sum of voxels above 75th-percentile threshold along remaining axes
- `peaks_data[axis]` = peak detection via `scipy.signal.find_peaks` with height > 10% of max

**Axis convention (critical for understanding thumbnails):**
| Axis index | Collapsed axis | 2D result | View label |
|---|---|---|---|
| 0 | X (left-right) | Y×Z plane | "X-Y (Dorsal View)" |
| 1 | Y (anterior-posterior) | X×Z plane | "X-Z (Lateral View)" |
| 2 | Z (dorsal-ventral) | X×Y plane | "Y-Z (Anterior View)" |

> **Note:** The mapping `axis 0 → Dorsal, axis 1 → Lateral, axis 2 → Anterior` is used throughout the UI.

#### `check_orientation(...)` (lines ~161–213)
Compares sample peak structure against template expectations:
- Peak count ratio > 2× or < 0.3× → axis swap warning
- Y-axis asymmetry < -0.15 → 180° Y flip (anterior-posterior)
- X-axis asymmetry > 0.3 → 90° Z rotation

Returns `(orientation_correct, changes_list, suggested_rotations_dict)`.

#### `generate_thumbnail(proj_2d, ...)` (lines ~216–250)
Creates a base64 PNG from a 2D max projection.

1. **Auto-crop:** Computes bounding box of pixels above the 5th-percentile of non-zero values. Adds 5% margin. This removes surrounding black space so the brain fills the thumbnail.
2. **Stretch rendering:** Uses `aspect='auto'` so the image stretches to fill the 4×4-inch canvas regardless of aspect ratio. This is intentional for orientation comparison — physical proportions are not preserved but the full content is always visible.
3. **Output:** 4×4 inch, 100 dpi → ~400×400 px PNG → base64 string.

#### `generate_histogram(...)` (lines ~253–298)
Creates a 3-subplot histogram comparing sample vs template 1D projection profiles:
- Profiles centred around 0 (midpoint subtracted)
- Template scaled to match sample amplitude
- Peaks marked with green dots

#### `save_to_orientations(...)` (lines ~301–313)
Auto-saves `image_info` and `automated_analysis` into `orientations.json` without overwriting any existing `manual_corrections` or `approved` fields.

#### `main()` (lines ~316–474)
Full pipeline: load TIFF → extract metadata → create backup → split channels → detect template → analyse projections → check orientation → generate thumbnails × 3 axes × (sample + template + signal) → generate histogram → save to orientations.json → print JSON.

### 4.2. `apply_rotation.py`

**Purpose:** Apply 90° multiples rotation to the TIFF on disk.

**Rotation convention:**
```python
axis_mapping = {
    'x': (0, 1),  # rotate in Z-Height plane
    'y': (0, 2),  # rotate in Z-Width plane
    'z': (1, 2),  # rotate in Height-Width plane
}
```
Uses `np.rot90(data, k=degrees//90, axes=axis_mapping[axis])`.

**Application order:** Rotations are applied sequentially as the `dict` is iterated: `x` first, then `y`, then `z`. This matches the Euler angle convention used in the frontend's matrix decomposition.

**Data handling:**
- 4D data `[Z, C, H, W]`: each channel is rotated independently, preserving the 4D structure.
- 3D data `[Z, H, W]`: rotated directly.

### 4.3. `reset_rotation.py`

**Purpose:** Restore image to original orientation from backup.

**Backup lookup order:**
1. `_backups/<submitter>/filename.tif` (current mechanism)
2. `Images/<submitter>/filename.original.tif` (legacy mechanism)

Copies the backup over the current file using `shutil.copy2` (preserves metadata).

### 4.4. `convert_tiff_to_nrrd.py`

**Purpose:** Convert TIFF image files to NRRD format for use with CMTK alignment tools.

**Invocation:** `python3 convert_tiff_to_nrrd.py [image_base]`

- If `image_base` is provided, converts only the matching TIFF from `Images/`.
- If omitted, converts all TIFFs in `Images/` recursively.
- Output directory: `nrrd_output/`

**Metadata extraction:**
- Reads ImageJ metadata (`spacing`, `unit`) for Z voxel size
- Reads `XResolution`/`YResolution` TIFF tags for XY voxel size
- Defaults to 1.0 if metadata is unavailable

**Shape handling:**
- 4D `[Z, C, Y, X]` → transposed to `[Z, Y, X, C]` for NRRD (multi-channel preserved)
- 3D `[Z, Y, X]` → saved directly
- 2D → transposed to `[X, Y]`

### 4.5. `split_channels.py`

**Purpose:** Split multi-channel NRRD files into separate signal and background channel files.

**Invocation:** `python3 split_channels.py [image_base]`

- If `image_base` is provided, processes only `nrrd_output/<image_base>.nrrd`.
- If omitted, processes all NRRDs in `nrrd_output/`.
- Output directory: `channels/`
- Output files: `<image_base>_signal.nrrd` (channel 0) and `<image_base>_background.nrrd` (channel 1)

**Processing:**
- Expects 4D data with shape `[Z, Y, X, 2]` (2 channels)
- Each channel is extracted and transposed to `[X, Y, Z]` order for CMTK compatibility
- 3D NRRD header is constructed from the 4D source header
- Skips files that are not 4D with exactly 2 channels

### 4.6. `align_single_cmtk.sh`

**Purpose:** Run the full CMTK alignment pipeline for a single image against the appropriate template.

**Invocation:** `./align_single_cmtk.sh <image_base>`

**Pipeline steps:**
1. **Template selection:** If `image_base` contains `VNC` → `JRCVNC2018U_template_lps.nrrd`, otherwise → `JRC2018U_template_lps.nrrd`
2. **LPS template creation:** If the LPS template doesn't exist, creates it by setting `space = 'left-posterior-superior'` on the base template
3. **Set input space:** Sets `space = 'left-posterior-superior'` on the signal and background channel files
4. **CMTK registration:** Runs `CMTK/bin/registration` with `--auto-multi-levels 4 --dofs 6,12` using the background channel against the template. Output: `corrected/<image_base>_xform/registration.xform`
5. **Apply transform:** Runs `CMTK/bin/reformatx` to warp both signal and background channels using the computed transform. Output: `corrected/<image_base>_signal_aligned.nrrd` and `corrected/<image_base>_background_aligned.nrrd`
6. **Generate thumbnails:** Creates MIP comparison thumbnails (template vs aligned) for each axis and saves to `corrected/<image_base>_alignment_thumbnails.json`

**Input files required:** `channels/<image_base>_signal.nrrd` and `channels/<image_base>_background.nrrd`

**Timeout:** 600 seconds (set in `server.js`)

---

## 5. Backup Mechanism

### Current System (`_backups/` directory)
When `get_image_data.py` first processes an image, it creates a backup:
```
Images/DeepanshuSingh/Brain_Fru11.12AD.tif
  → _backups/DeepanshuSingh/Brain_Fru11.12AD.tif
```
The backup is only created once (if `backup_file.exists()` is False). Subsequent rotations modify the `Images/` copy but the `_backups/` copy is never touched.

### Legacy System (`.original` suffix) — DEPRECATED
Previously, backups were created as `filename.original.tif` next to the original. This caused a cascading bug: when the backup itself was processed, it would create `filename.original.original.tif`, and so on. The `.original` mechanism has been replaced but `reset_rotation.py` still checks for legacy backups as a fallback.

### Server Filtering
`server.js` excludes files containing `.original` in the name when listing images, preventing legacy backups from appearing in the UI.

---

## 6. Frontend Architecture

### 6.1. Page Structure

The page is a single-page application with 7 card sections:

| # | Card | Purpose |
|---|---|---|
| 1 | Image Information | Sample dimensions, voxel size, channels; template selection |
| 2 | Orientation Assessment | Peak comparison table; suggested changes list |
| 3 | Background Channel vs Template | **MIP thumbnails with interactive rotation toolbar** |
| 4 | Signal Channel | Signal-channel MIPs (for visual reference only) |
| 5 | Projection Analysis | Histogram comparison (sample vs template profiles) |
| 6 | Manual Corrections | X/Y/Z rotation dropdowns; Apply/Reset buttons |
| 7 | Review & Approve | Save assessment; approve for CMTK alignment |

### 6.2. Interactive Rotation Preview System (Section 3)

This is the most complex part of the frontend. It provides a live preview of rotations applied to the sample thumbnails using CSS transforms, without modifying the actual TIFF data.

#### Global State Variables
```javascript
let previewMatrix = [[1,0,0],[0,1,0],[0,0,1]]; // Current preview rotation (3×3)
let originalThumbnails = { x: '...', y: '...', z: '...' };  // Original base64 PNGs
```

#### Rotation Matrix Convention

The rotation matrices match the numpy `np.rot90` convention used in `apply_rotation.py`:

- **X rotation** (axes 0,1): rotates in the Z–Y plane, column 2 invariant
- **Y rotation** (axes 0,2): rotates in the Z–X plane, column 1 invariant
- **Z rotation** (axes 1,2): rotates in the Y–X plane, column 0 invariant

The 3×3 rotation matrices are permutation matrices (entries ∈ {-1, 0, 1}) since only 90° multiples are supported. There are exactly **24 unique matrices** (the rotation group of the cube).

```javascript
// X +90°: [[0,-1,0],[1,0,0],[0,0,1]]   Swaps axis 0↔1 (Dorsal ↔ Lateral)
// Y +90°: [[0,0,-1],[0,1,0],[1,0,0]]   Swaps axis 0↔2 (Dorsal ↔ Anterior)
// Z +90°: [[1,0,0],[0,0,-1],[0,1,0]]   Swaps axis 1↔2 (Lateral ↔ Anterior)
```

#### Matrix Composition

Rotations are composed by left-multiplication: each new rotation matrix is multiplied on the left of the current `previewMatrix`. This means the latest rotation is applied last in world-space, which is the intuitive "apply operation to current state" behaviour.

```javascript
function applyPreviewRotation(axis, degrees) {
    const R = makeRotMatrix(axis, degrees);
    previewMatrix = mat3Mul(R, previewMatrix);  // R × current
    updateRotationPreview();
}
```

#### Matrix to Euler Angle Decomposition

`matrixToAngles(M)` decomposes a rotation matrix back into `{x, y, z}` angles by brute-force searching all 64 combinations of `(0°, 90°, 180°, 270°)` per axis:

```javascript
test = Rz(rz) × Ry(ry) × Rx(rx)
// if test === M, return {x: rx, y: ry, z: rz}
```

The **composition order** is `Rz × Ry × Rx` (X applied first, Z last). This matches `apply_rotation.py` where rotations are applied x→y→z sequentially to the data.

> **Why brute-force?** With only 64 combinations to check and integer arithmetic, this is both correct and fast. Analytical decomposition of permutation matrices is error-prone.

#### View Mapping (`computeViewMapping`)

The most complex function. Given a 3×3 rotation matrix `R`, it determines for each of the 3 view slots (Dorsal, Lateral, Anterior) which original thumbnail to show and what CSS transform to apply.

**Algorithm for each view slot `i`:**

1. **Find source projection:** Column `R[i][j] ≠ 0` determines that new axis `i` was old axis `j`. The MIP that collapses axis `j` (key `keys[j]`) is the source thumbnail.

2. **Determine in-plane orientation:** The remaining two display axes `(p, q)` map to old axes via `R[p][c]` and `R[q][c]`. Check whether the horizontal/vertical axes match or are swapped.

3. **Compute CSS transforms:**
   - If display axes match original axes (same order): only flips needed based on sign
   - If display axes are swapped: apply 90° CSS rotation, then flips

```javascript
mapping.push({ sourceKey, cssRot, flipH, flipV });
```

**Applied as CSS:**
```javascript
img.style.transform = [scaleX(-1), scaleY(-1), rotate(90deg)].join(' ');
```

#### Per-View Controls

Each sample thumbnail has three controls below it:
- **↻ Rotate CW:** In-plane clockwise rotation. Applies +90° around the axis perpendicular to that view's projection plane.
  - Dorsal view → Z rotation (axis perpendicular to XY plane)
  - Lateral view → Y rotation (axis perpendicular to XZ plane)
  - Anterior view → X rotation (axis perpendicular to YZ plane)
- **↺ Rotate CCW:** Same axis, 270° (= -90°).
- **⇅ Swap with…** dropdown: Swaps MIP content between two view slots. Internally applies a +90° rotation around the axis that connects those two views:
  - Dorsal ↔ Lateral: X-axis (connects view 0 and view 1)
  - Dorsal ↔ Anterior: Y-axis (connects view 0 and view 2)
  - Lateral ↔ Anterior: Z-axis (connects view 1 and view 2)

#### Status Synchronisation

The preview system keeps these in sync:
1. `previewMatrix` (authoritative state)
2. Dropdown values `rot-x`, `rot-y`, `rot-z` (always reflect decomposed angles)
3. Status bar text and colour (identity = green "no rotation", otherwise = amber with angles)
4. "Apply Rotation" button enabled/disabled state
5. Thumbnail images and CSS transforms

Changes flow **bidirectionally**:
- Toolbar/per-view buttons → `applyPreviewRotation()` → update matrix → `updateRotationPreview()` → update dropdowns + thumbnails
- Manual dropdown changes → `syncPreviewFromDropdowns()` → recompute matrix → `updateRotationPreview()` → update thumbnails

### 6.3. Alignment Status Page (`public/alignment-status.html`)

A dedicated monitoring dashboard for the CMTK alignment queue, accessible via the "Alignment Status" button in the main review page header.

#### Page Sections

| # | Section | Purpose |
|---|---|---|
| 1 | Overview Cards | Counts for Queued, Processing, Completed, Failed, Approved |
| 2 | Currently Processing | Active alignment job with elapsed time |
| 3 | Queued Jobs | Jobs waiting to process, with queue position. Includes `preparing` jobs (purple) |
| 4 | Completed Jobs | Successfully aligned images with completion timestamp |
| 5 | Failed Jobs | Failed jobs with error message and "Retry" / "Reset" buttons |
| 6 | Approved Images | Images approved but not yet queued, each with a "Queue for Alignment" button |

#### Key Features
- **Auto-refresh:** Polls `GET /api/alignment-status` every 30 seconds
- **Queue All Approved:** Button in header batch-queues all approved images by calling `POST /api/queue-alignment` for each
- **Per-image queuing:** Individual "Queue for Alignment" buttons in the Approved Images section
- **Status colours:** Preparing = purple, Processing = amber, Completed = green, Failed = red

#### Job Status Lifecycle
```
preparing → queued → processing → completed
                                → failed
```
- `preparing`: NRRD conversion or channel splitting running in background
- `queued`: Waiting for a processing slot (sequential queue, one at a time)
- `processing`: `align_single_cmtk.sh` is currently executing
- `completed`: Alignment finished successfully, thumbnails available
- `failed`: Alignment or preparation failed, error message available

---

## 7. Data Formats

### 7.1. TIFF Sample Data
- **4D:** `[Z_slices, Channels (2), Height, Width]` — most common
- **3D:** `[Z_slices, Height, Width]` — after rotation of a single channel

Channel convention:
- Channel 0: typically signal (neuron-specific expression)
- Channel 1: typically background/neuropil (NC82 or similar)
- User can swap via the Background Channel selector

### 7.2. NRRD Template Data
- **3D:** `[X, Y, Z]` with `space directions` giving voxel sizes
- Loaded via `pynrrd`. Voxel sizes extracted from diagonal of `space directions` matrix.

### 7.3. `orientations.json` Entry Structure
```json
{
  "DeepanshuSingh/Brain_Fru11.12AD_FD6DBD_FB1.1_NC82_S1": {
    "image_info": {
      "shape": [598, 2, 1024, 1024],
      "num_channels": 2,
      "background_channel": 1,
      "voxel_sizes": [1.0, 0.312, 0.312]
    },
    "automated_analysis": {
      "detected_template": "JRC2018U_template_lps",
      "orientation_correct": false,
      "suggested_changes": ["180° Y-axis rotation suggested"],
      "suggested_rotations": { "x": 0, "y": 180, "z": 0 },
      "peak_summary": { "0": {...}, "1": {...}, "2": {...} },
      "template_info": { "shape": [1210, 566, 174], "voxel_sizes": [...], ... }
    },
    "manual_corrections": {
      "template": "JRC2018U_template_lps",
      "template_correct": true,
      "background_channel": 1,
      "rotations": { "x": 0, "y": 180, "z": 0 }
    },
    "saved_at": "2026-02-13T10:30:00.000Z",
    "approved": true,
    "approved_at": "2026-02-13T10:31:00.000Z"
  }
}
```

Fields are **merged, not overwritten**: `get_image_data.py` updates `image_info` and `automated_analysis`; the server updates `manual_corrections`, `saved_at`, `approved`, `approved_at`.

---

## 8. Known Templates

| Key | File | Shape | Voxel (µm) | Physical Size (µm) | Type |
|---|---|---|---|---|---|
| `JRC2018U_template_lps` | `JRC2018U_template_lps.nrrd` | 1210×566×174 | 0.52×0.52×1.0 | 629×294×174 | Brain (LPS) |
| `JRC2018U_template` | `JRC2018U_template.nrrd` | 1210×566×174 | 0.52×0.52×1.0 | 629×294×174 | Brain |
| `JRCVNC2018U_template` | `JRCVNC2018U_template.nrrd` | 660×1290×382 | 0.4×0.4×0.4 | 264×516×153 | VNC |
| `JRCVNC2018U_template_lps` | `JRCVNC2018U_template_lps.nrrd` | — | — | — | VNC (LPS) |

Template auto-detection: images with `"VNC"` in the path → `JRCVNC2018U_template`, all others → `JRC2018U_template_lps`.

---

## 9. Rotation Convention Reference

### Axis Naming
The data is stored as `[axis_0, axis_1, axis_2]` = `[Z, Y, X]` (or `[Z, Height, Width]` for the array).

| Axis | Anatomical | Array position | NRRD |
|---|---|---|---|
| X | Left-Right | axis 2 (Width) | 1st dimension |
| Y | Anterior-Posterior | axis 1 (Height) | 2nd dimension |
| Z | Dorsal-Ventral | axis 0 (Z slices) | 3rd dimension |

### `np.rot90` Mapping
| Rotation | `np.rot90` axes | Effect |
|---|---|---|
| X +90° | (0, 1) = Z↔Height | Rotates in sagittal plane |
| Y +90° | (0, 2) = Z↔Width | Rotates in coronal plane |
| Z +90° | (1, 2) = Height↔Width | Rotates in axial plane |

### Application Order
Rotations are applied **sequentially**: X first, then Y, then Z. The frontend's `matrixToAngles()` decomposition assumes the same order: `M = Rz × Ry × Rx` (rightmost applied first).

### Frontend Matrix Values
Each rotation matrix is a signed permutation matrix (entries ∈ {-1, 0, 1}):

**X-axis rotations:**
```
  0°: I             90°: [[0,-1,0],     180°: [[-1,0,0],     270°: [[0,1,0],
                          [1,0,0],              [0,-1,0],           [-1,0,0],
                          [0,0,1]]              [0,0,1]]            [0,0,1]]
```
**Y-axis rotations:**
```
  0°: I             90°: [[0,0,-1],     180°: [[-1,0,0],     270°: [[0,0,1],
                          [0,1,0],              [0,1,0],            [0,1,0],
                          [1,0,0]]              [0,0,-1]]           [-1,0,0]]
```
**Z-axis rotations:**
```
  0°: I             90°: [[1,0,0],      180°: [[1,0,0],      270°: [[1,0,0],
                          [0,0,-1],            [0,-1,0],            [0,0,1],
                          [0,1,0]]             [0,0,-1]]            [0,-1,0]]
```

---

## 10. Thumbnail Generation Details

### Pipeline
```
3D volume → np.max(axis=i) → 2D MIP → auto-crop → matplotlib imshow → base64 PNG
```

### Auto-crop Algorithm
1. Compute threshold = 5th percentile of non-zero pixels
2. Create binary mask: pixels > threshold
3. Find bounding box (`rmin, rmax, cmin, cmax`) of non-zero rows/columns
4. Add 5% margin (minimum 2 pixels) on all sides
5. Crop the 2D image to this bounding box

**Why:** MIPs of brain data typically have large regions of black (background). Cropping ensures the brain fills the thumbnail for easier visual comparison.

### Rendering
- Figure size: 4×4 inches at 100 dpi
- `aspect='auto'`: image is stretched to fill the canvas (non-uniform scaling)
- **Rationale for stretching:** The user needs to compare orientation, not physical proportions. Templates have anisotropic voxels (e.g., 0.52×0.52×1.0 µm) which would produce very thin MIPs if aspect-correct rendering were used.

### CSS-Based Live Preview
Instead of re-rendering thumbnails server-side for each preview rotation, the frontend applies CSS transforms to the existing thumbnail images:
- `scaleX(-1)` / `scaleY(-1)` for axis flips
- `rotate(90deg)` for in-plane 90° rotation
- Images are swapped between view slots when axes are re-assigned

This is instantaneous and requires no server round-trip.

---

## 11. Alignment Queue System

The alignment queue is an in-memory system managed by `server.js` that orchestrates the CMTK alignment pipeline. It processes jobs sequentially (one at a time) to avoid overloading the system with concurrent CPU-intensive CMTK registration processes.

### 11.1. In-Memory State

```javascript
let alignmentQueue = [];          // Array of image_base strings waiting to process
let currentAlignment = null;      // image_base of currently processing job (or null)
let alignmentStatus = {};         // image_base → { status, progress, error, queued_at, completed_at }
let preparingImages = new Set();  // image_base strings currently being prepared (NRRD/channel creation)
```

> **Note:** All queue state is in-memory and lost on server restart. However, `detectRunningAlignments()` runs on startup to detect and monitor any CMTK processes still running from a previous server session.

### 11.2. Preparation Pipeline (`prepareAndQueue`)

When `POST /api/queue-alignment` is called for an image missing prerequisites:

```
TIFF file → convert_tiff_to_nrrd.py → nrrd_output/<base>.nrrd
                                            ↓
                                    split_channels.py
                                            ↓
                              channels/<base>_signal.nrrd
                              channels/<base>_background.nrrd
                                            ↓
                                    queueAlignment()
```

Each step runs as a background child process. The HTTP response is returned immediately with status `preparing`. If any step fails, the job transitions to `failed` with an error message.

### 11.3. Queue Processing (`processAlignmentQueue`)

1. Check `currentAlignment` is null and queue is non-empty
2. Check no CMTK `registration` process is already running (via `ps aux`)
3. Dequeue the next `image_base` and set status to `processing`
4. Execute `./align_single_cmtk.sh "<image_base>"` (timeout: 600s)
5. On completion: set status to `completed` or `failed`, clear `currentAlignment`, process next

### 11.4. Startup Recovery (`detectRunningAlignments`)

On server startup, the server scans running processes for:
- `align_single_cmtk.sh` wrapper scripts (extracts image base from arguments)
- `CMTK/bin/registration` processes (extracts image base from output path pattern `corrected/<base>_xform/registration.xform`)

Detected processes are tracked as `processing` and monitored every 10 seconds. When a process disappears:
- If `corrected/<base>_xform/` exists → marked `completed`
- Otherwise → marked `failed`

Once all monitored processes finish, normal queue processing resumes.

---

## 12. Workflow: Full User Journey

1. **Load**: User picks an image from the dropdown. Server calls `get_image_data.py`, which loads the TIFF, analyses it, generates thumbnails, and returns JSON.

2. **Compare**: UI displays sample MIPs beside template MIPs for each projection axis. User visually compares shapes.

3. **Preview rotation**: If the sample is mis-oriented, user clicks rotation toolbar buttons or per-view controls. Thumbnails update instantly via CSS. The X/Y/Z dropdown values update automatically.

4. **Apply**: User clicks "Apply Rotation". Server calls `apply_rotation.py` which modifies the TIFF, then the page reloads the image (re-runs the full analysis pipeline). The preview resets.

5. **Verify**: After applying, the re-generated thumbnails should now match the template.

6. **Save**: User clicks "Save Assessment" to persist their corrections (template, channel selection, rotation values) to `orientations.json`.

7. **Approve**: After saving, user can "Approve for CMTK Alignment". This sets `approved: true` in `orientations.json`.

8. **Queue for alignment**: User navigates to the Alignment Status page and clicks "Queue for Alignment" on individual images or "Queue All Approved" to batch-queue. The server prepares prerequisites (NRRD conversion, channel splitting) in the background if needed.

9. **Alignment**: The queue processes images sequentially. Each image runs through `align_single_cmtk.sh` which performs CMTK registration and reformatting against the appropriate template. Results are saved to `corrected/`.

10. **Review alignment**: After completion, the Alignment Status page shows comparison thumbnails (template vs aligned MIPs) for each axis. Users can verify the alignment quality.

11. **Reset** (optional): If a rotation was wrong, "Reset to Original" restores the TIFF from `_backups/`. Alignment status can also be reset to re-queue a failed job.

---

## 13. Troubleshooting

### Image shows all black thumbnails
- The background channel may be wrong. Try swapping to Channel 0.
- The TIFF may be corrupted. Delete cached files (NRRDs in `channels/`, `nrrd_output/`) and the `orientations.json` entry, then reload.
- Check `_backups/` for the original and restore with "Reset to Original".

### Thumbnails are mostly empty/tiny
- Auto-crop relies on the 5th-percentile threshold. Very dim images may have a poor bounding box. Check the histogram for signal levels.

### Rotation preview doesn't match applied result
- Ensure `apply_rotation.py`'s axis mapping matches the frontend's `makeRotMatrix()`. Both should use:
  - X → planes (0,1), Y → planes (0,2), Z → planes (1,2)
- Verify with the test: `M = Rz(rz) × Ry(ry) × Rx(rx)` should produce the same permutation as applying `np.rot90` for x, then y, then z.

### `.original.original.original...` chain files
- This was a legacy bug where the backup mechanism repeatedly suffixed `.original`. It has been fixed; backups now go to `_backups/`. If legacy chains exist, delete them manually and verify `_backups/` has the true original.

### Server won't start (port in use)
```bash
pkill -f "node server.js"
npm start
```

### Python script errors
```bash
source venv/bin/activate
python -m py_compile get_image_data.py   # syntax check
python get_image_data.py "DeepanshuSingh/SomeImage" 1  # manual test
```

### Reprocessing a corrupted image
```bash
# 1. Delete all cached/derived files
rm -f nrrd_output/<name>.nrrd
rm -f channels/<name>_signal.nrrd channels/<name>_background.nrrd
rm -rf corrected/<name>_xform/
rm -f corrected/<name>_signal_aligned.nrrd corrected/<name>_background_aligned.nrrd
rm -f corrected/<name>_alignment_thumbnails.json

# 2. Remove from orientations.json
python3 -c "
import json
with open('orientations.json') as f: d = json.load(f)
d.pop('<full/path/name>', None)
with open('orientations.json', 'w') as f: json.dump(d, f, indent=2)
"

# 3. Reset alignment status (if server is running)
curl -X POST http://localhost:3000/api/reset-alignment \
  -H "Content-Type: application/json" \
  -d '{"image_base":"<name>"}'

# 4. Reload in the UI (or curl the API)
curl "http://localhost:3000/api/image?name=<url-encoded-name>"
```

### Queue for Alignment button appears to hang
The preparation step (NRRD conversion and channel splitting) runs in the background. The button should respond immediately. If it hangs, check:
- Server logs for errors from `split_channels.py` or `convert_tiff_to_nrrd.py`
- `ps aux | grep split_channels` to see if the preparation process is running
- The Alignment Status page should show the image with `preparing` status

### Alignment stuck in "processing"
CMTK registration can take a long time (minutes to hours) for large images. Check:
```bash
ps aux | grep "CMTK/bin/registration"  # Is the process still running?
```
If the process has died but the status page still shows "processing", restart the server. `detectRunningAlignments()` will re-check process state on startup.

### Alignment fails immediately
- Check that `channels/<name>_signal.nrrd` and `channels/<name>_background.nrrd` exist and are valid
- Ensure the CMTK binaries are present: `ls CMTK/bin/registration CMTK/bin/reformatx`
- Check server logs for the specific error message

### Queue state lost after server restart
The alignment queue is in-memory. After restart, any jobs that were in `preparing` or `queued` state are lost. However:
- Running CMTK processes are auto-detected and monitored
- Re-queue images using the Alignment Status page

---

## 14. Dependencies

### Node.js
- `express` — HTTP server

### Python (in `venv/`)
- `numpy` — array operations, rotation
- `scipy` — peak detection (`scipy.signal.find_peaks`)
- `matplotlib` — thumbnail/histogram rendering
- `tifffile` — TIFF file I/O with metadata access
- `nrrd` (pynrrd) — NRRD file I/O

### External Tools
- **CMTK** (Computational Morphometry Toolkit) — installed in `CMTK/bin/`
  - `registration` — affine registration of images to templates
  - `reformatx` — apply transformations to warp images

### Setup
```bash
python3 -m venv venv
source venv/bin/activate
pip install numpy scipy matplotlib tifffile nrrd
npm install
npm start
```

---

## 15. Voxel Size Extraction

Voxel sizes are critical for matching sample physical extent to template physical extent.

### Priority order:
1. **ImageJ metadata** (most FlyBrain TIFFs):
   - Z: `spacing` key from `imagej_metadata`
   - XY: stored as TIFF `XResolution`/`YResolution` tags in `(numerator, denominator)` format
   - Pixel size = `denominator / numerator` (µm/pixel)
   - **Important:** The TIFF spec stores resolution as pixels/unit, which inverts to unit/pixel

2. **OME-XML** (some standardised microscopy TIFFs):
   - Attributes `PhysicalSizeX`, `PhysicalSizeY`, `PhysicalSizeZ` on the `<Pixels>` element

3. **Default:** 0.5 µm in all dimensions

### Typical values observed:
| Image | vz (µm) | vy (µm) | vx (µm) | Source |
|---|---|---|---|---|
| Brain_Fru11.12AD_FD6DBD | 1.0 | 0.312 | 0.312 | ImageJ spacing+XRes |
| Brain_SPR8AD.dsxDBD | 0.5 | 0.5 | 0.5 | Default (no metadata) |
| VNC_Fru11.12AD_FD6DBD | 0.5 | 0.884 | 0.884 | ImageJ XRes only |
