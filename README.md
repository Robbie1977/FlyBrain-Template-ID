# Fly Brain Template Identification and Conversion Guide

This guide provides comprehensive information for identifying template images aligned to existing template spaces, converting common file types to navis loadable formats, and bridging to standard VFB templates using navis FlyBrains tools.

## Table of Contents
1. [Template Identification](#template-identification)
2. [Template Specifications](#template-specifications)
3. [File Format Conversion](#file-format-conversion)
4. [Navis FlyBrains Integration](#navis-flybrains-integration)
5. [VFB Template Bridging](#vfb-template-bridging)
6. [Automated Processing Workflow](#automated-processing-workflow)

## Template Identification

### Identifying Template Alignment from File Metadata

#### NRRD Files
NRRD files contain header information that specifies the template space. Key fields to examine:

- `sizes`: Dimensions in voxels (X Y Z)
- `space directions`: Physical spacing per voxel in microns
- `space units`: Should be "microns" for all axes

Example NRRD header:
```
NRRD0005
type: uint8
dimension: 3
space dimension: 3
sizes: 1211 567 175
space directions: (0.5189161,0,0) (0,0.5189161,0) (0,0,1)
encoding: gzip
space units: "microns" "microns" "microns"
```

#### H5J Files
H5J files from Janelia Workstation contain metadata about alignment space. Use the `process_h5j_simple.py` script to extract:

- Alignment space name
- Voxel dimensions
- Template gender/sex specification

#### Mesh and Skeleton Files
For OBJ, PLY, and SWC files, template identification requires:
- Checking associated metadata files
- Examining coordinate ranges
- Comparing to known template bounds

**Coordinate Units**: OBJ/PLY/SWC files typically use coordinates in microns (μm), though files derived directly from electron microscopy (EM) connectome data may use nanometers (nm). Given that 1 μm = 1000 nm and Drosophila brain dimensions are well-established, the coordinate scale can be readily determined. For instance, a coordinate of (10,0,0) indicates a position 10 μm from the origin (0,0,0). Furthermore, as the origin is conventionally placed at the corner of the bounding volume with substantial empty space surrounding the neuropil, neuronal coordinates rarely appear near the origin (unless an offset has been applied), facilitating unit scale identification.

### Template Matching Logic

1. **Extract dimensions and voxel sizes** from file metadata
2. **Compare to known template specifications** (see table below)
3. **Check physical volume consistency** - templates represent the same physical brain volume but may have different sampling
4. **Verify orientation** - X is longest axis, Z is shortest (correct anatomy)

## Template Specifications

### Janelia Template Spaces

| Short Form | Full Name | X Count | Y Count | Z Count | X (μm) | Y (μm) | Z (μm) | Notes |
|------------|-----------|---------|---------|---------|--------|--------|--------|-------|
| JRC2018_MALE_38um_iso_16bit | JRC2018 Male 38um isotropic | 1561 | 744 | 546 | 0.38 | 0.38 | 0.38 | High-res male brain |
| JRC2018_FEMALE_38um_iso_16bit | JRC2018 Female 38um isotropic | 1652 | 768 | 479 | 0.38 | 0.38 | 0.38 | High-res female brain |
| JRC2018_FEMALE_63x | JRC2018 Female 63x | 1652 | 768 | 478 | 0.38 | 0.38 | 0.38 | Female brain at 63x objective |
| JRC2018_UNISEX_38um_iso_16bit | JRC2018 Unisex 38um isotropic | 1652 | 773 | 456 | 0.38 | 0.38 | 0.38 | Unisex brain template |
| Brain-63x | Brain 63x | 1450 | 725 | 436 | 1 | 1 | 1 | Lower resolution brain |
| JRC2018_FEMALE_40x | JRC2018 Female 40x | 1427 | 664 | 413 | 0.44 | 0.44 | 0.44 | Female brain at 40x |
| JRCVNC2018M | JRC2018 VNC Male 4iso 8bit | 659 | 1342 | 401 | 0.4 | 0.4 | 0.4 | Male ventral nerve cord |
| JRCVNC2018U | JRC2018 VNC Unisex 4iso 8bit | 660 | 1290 | 382 | 0.4 | 0.4 | 0.4 | Unisex VNC template |
| JRCVNC2018F | JRC2018 VNC Female 4iso 8bit | 660 | 1342 | 358 | 0.4 | 0.4 | 0.4 | Female ventral nerve cord |
| Court2017VNS | VNS-Court2017 | 512 | 1024 | 270 | 0.4612588 | 0.4612588 | 0.46 | Court lab VNS template |
| Court2018VNS | 20x_flyVNCtemplate_Female_symmetric | 512 | 1024 | 220 | 0.4612588 | 0.4612588 | 0.7 | Court lab female VNS |
| UNISEX_VNC | Unisex VNC | 573 | 1119 | 219 | 0.461122 | 0.461122 | 0.7 | Unisex VNC |
| JFRC_2010 | JFRC 2010 | 1024 | 512 | 218 | 0.622088 | 0.622088 | 0.622088 | Older JFRC template |
| JRC2018_VNC_FEMALE-205 | JRC2018 VNC Female 205 | 573 | 1164 | 205 | 0.461122 | 0.461122 | 0.7 | Female VNC variant |
| JRC2018_VNC_FEMALE-204 | JRC2018 VNC Female 204 | 573 | 1164 | 204 | 0.461122 | 0.461122 | 0.7 | Female VNC variant |
| JRC2018_FEMALE_20x-182 | JRC2018 Female 20x 182 | 1210 | 563 | 182 | 0.5189161 | 0.5189161 | 1 | Female brain at 20x |
| JRC2018_FEMALE_20x-181 | JRC2018 Female 20x 181 | 1210 | 563 | 181 | 0.5189161 | 0.5189161 | 1 | Female brain at 20x |
| JRC2018U | Unisex | 1211 | 567 | 175 | 0.5189161 | 0.5189161 | 1 | Standard unisex brain |
| Ito2017VNCF | AvgVNCFemale_768-1024 | 768 | 1024 | 163 | 0.4300931 | 0.4300931 | 1.059838 | Ito lab female VNC |

### Navis FlyBrains Template Names

| Janelia Name | Navis Name | VFB ID | VFB Name |
|--------------|------------|--------|----------|
| JRC2018_UNISEX_38um_iso_16bit | JRC2018U | VFB_00101567 | JRC2018Unisex |
| JRC2018_FEMALE_38um_iso_16bit | JRC2018F | VFB_00101384 | JRC_FlyEM_Hemibrain |
| JRCVNC2018U | JRCVNC2018U | VFB_00200000 | JRC2018UnisexVNC |

### Key Notes on Template Spaces

1. **Same Physical Volume**: All templates represent the same physical brain/VNC volume but sampled at different resolutions
2. **Voxel Size Variation**: X and Y voxel sizes are often identical, but Z may differ (anisotropic sampling)
3. **Isotropic vs Anisotropic**: Some templates are truly isotropic (equal voxel sizes in all dimensions)
4. **Gender Differences**: Male/female templates account for sexual dimorphism in brain structure
5. **Resolution Trade-offs**: Higher magnification (63x) provides finer detail but smaller field of view
6. **VFB Template Availability**: Virtual Fly Brain maintains unisex templates (JRC2018U for brain, JRCVNC2018U for VNC) and one female brain template (JRCFIB2018F). No separate male templates exist in VFB.
7. **Hemibrain Note**: The Hemibrain (JRC_FlyEM_Hemibrain) is not one of the main VFB templates for new data alignment. It contains original hemibrain neurons aligned to it but is not actively used for aligning new datasets.

### All VFB Templates

The following table lists all templates currently available in Virtual Fly Brain, with metadata extracted from VFB. **Active templates** (marked with ⭐) are the main ones VFB uses for aligning new data. Note: VFB indexing may start from 0 while the extent values here represent actual voxel counts.

| VFB ID | Name/Description | Extent (X×Y×Z) | Voxel Size (X×Y×Z μm) | Orientation | Status |
|--------|------------------|-----------------|----------------------|-------------|--------|
| VFB_00101567 | JRC2018Unisex (Brain) | 1211×567×175 | 0.5189161×0.5189161×1.0 | LPS | ⭐ **ACTIVE** - Main brain template |
| VFB_00200000 | JRC2018UnisexVNC | 660×1290×382 | 0.4×0.4×0.4 | LPS | ⭐ **ACTIVE** - Main VNC template |
| VFB_00049000 | L3 CNS template | 486×1999×364 | 0.293×0.293×0.5 | RIA | ⭐ **ACTIVE** - Larval CNS template |
| VFB_00050000 | L1 larval CNS ssTEM - Cardona/Janelia (Seymour) | 512×512×484 | 0.243×0.243×0.5 | LIP | ⭐ **ACTIVE** - L1EM larval CNS template |
| VFB_00101384 | JRC_FlyEM_Hemibrain | 544×640×672 | 0.512×0.512×0.512 | LIP | Hemibrain neurons only |
| VFB_00017894 | JFRC2 | 1023×511×217 | 0.62208×0.62208×0.62208 | LPS | Legacy template |
| VFB_00030786 | Ito2014 | 511×511×134 | 0.636234×0.636234×1.41 | LPS | Legacy template |
| VFB_00100000 | Court2018VNS | 511×1023×229 | 0.4612588×0.4612588×0.46 | LPS | Legacy VNS template |
| VFB_00110000 | Adult Head (McKellar2020) | 961×2000×248 | 0.438472×0.438537×1.31787 | RAS | Specialized head template |
| VFB_00120000 | Adult T1 Leg (Kuan2020) | 595×763×600 | 1.0×1.0×1.0 | RPI | Specialized leg template |

### NRRD Files
NRRD files are natively supported by navis. Load directly:

```python
import navis
import nrrd

# Load NRRD file
data, header = nrrd.read('file.nrrd')
volume = navis.Volume(data, name='volume')

# Extract template info from header
voxel_size = [header['space directions'][i][i] for i in range(3)]
dims = header['sizes']
```

### H5J Files
Use the `process_h5j_simple.py` script from VirtualFlyBrain/Management repo:

```python
# Process H5J file
from process_h5j_simple import process_h5j_file

# This extracts channels and aligns to target template
process_h5j_file('input.h5j', output_dir='output/')
```

The script automatically:
- Detects source template from H5J metadata
- Identifies signal and reference channels
- Transforms to target VFB template space
- Saves as NRRD files

### Mesh Files (OBJ/PLY)
Convert meshes to navis-compatible format:

```python
import navis
import trimesh

# Load mesh
mesh = trimesh.load('file.obj')

# Convert to navis MeshNeuron
neuron = navis.MeshNeuron(mesh, name='neuron')

# If needed, transform coordinates
# neuron = navis.xform_brain(neuron, source='source_template', target='target_template')
```

### Skeleton Files (SWC)
SWC files are natively supported:

```python
import navis

# Load SWC skeleton
neuron = navis.read_swc('file.swc')

# Validate and repair if needed
neuron = navis.heal_skeleton(neuron)
```

## Navis FlyBrains Integration

### Template Registration
Navis uses the `flybrains` module for template registration:

```python
import navis
import flybrains

# Available templates
print(flybrains.templates)

# Get template info
template = flybrains.JRC2018U
print(f"Dimensions: {template.dims}")
print(f"Voxel size: {template.voxdims}")
```

### Coordinate Transformation
Transform between template spaces:

```python
import navis
import flybrains

# Transform neuron from one template to another
transformed_neuron = navis.xform_brain(
    neuron, 
    source=flybrains.JRC2018F,  # source template
    target=flybrains.JRC2018U   # target template
)
```

### Volume Transformation
For image volumes:

```python
import navis
import numpy as np

# Transform volume coordinates
transformed_volume = navis.xform_brain(
    volume, 
    source='JRC2018F', 
    target='JRC2018U'
)
```

## VFB Template Bridging

### Querying VFB Template Specifications
Use VFB Connect to get dynamic template specs:

```python
from vfb_connect.cross_server_tools import VfbConnect

vc = VfbConnect(neo_endpoint='http://kb.virtualflybrain.org')

query = """
MATCH (t:Template)<-[:depicts]-(tc:Template)-[r:in_register_with]->(tc) 
WHERE 'JRC2018U' IN t.symbol 
RETURN r
"""

results = vc.nc.commit_list([query])
# Extract dims and voxdims from results
```

### Unified Dimension Calculation
VFB uses extent and voxel size information from template metadata:

```python
def get_vfb_template_specs(template_name):
    # Template specifications from VFB KB
    specs = {
        'JRC2018U': {  # VFB_00101567
            'dims': [1211, 567, 175],  # voxel dimensions
            'voxdims': [0.5189161, 0.5189161, 1.0],  # microns per voxel
            'extent': [628.4, 294.0, 175.0]  # physical extent in microns
        },
        'JRCVNC2018U': {  # VFB_00200000
            'dims': [660, 1290, 382],  # voxel dimensions
            'voxdims': [0.4, 0.4, 0.4],  # microns per voxel
            'extent': [264.0, 516.0, 152.8]  # physical extent in microns
        }
    }
    
    return specs.get(template_name, {})
```

### Voxelization for VFB Compatibility
When voxelizing neurons for VFB:

```python
# For JRC2018U brain (VFB_00101567)
# Dimensions: 1211 x 567 x 175 voxels
# Voxel size: 0.5189161 x 0.5189161 x 1.0 microns
vx = navis.voxelize(
    transformed_neuron, 
    pitch=['0.5189161 microns', '0.5189161 microns', '1.0 microns'], 
    bounds=[[0, 628.4], [0, 294.0], [0, 175.0]], 
    parallel=False
)

# For JRCVNC2018U VNC (VFB_00200000)
# Dimensions: 660 x 1290 x 382 voxels
# Voxel size: 0.4 x 0.4 x 0.4 microns
vx = navis.voxelize(
    transformed_neuron, 
    pitch=['0.4 microns', '0.4 microns', '0.4 microns'], 
    bounds=[[0, 264.0], [0, 516.0], [0, 152.8]], 
    parallel=False
)
```

## Automated Processing Workflow

### Step-by-Step Process

1. **Identify Input File Type and Channels**
   - NRRD: Check header for dimensions, voxel size, template info
   - H5J: Use `process_h5j_simple.py` to extract metadata
   - OBJ/PLY/SWC: Check associated files or coordinate ranges

2. **Determine Source Template**
   - Match dimensions and voxel sizes to known templates
   - Use VFB KB queries for dynamic template specs
   - Handle gender-specific templates appropriately

3. **Select Target VFB Template**
   - For brain data: JRC2018U (unisex)
   - For VNC data: JRCVNC2018U (unisex)
   - Consider resolution requirements

4. **Convert File Format**
   - Use appropriate navis loading functions
   - Handle multi-channel data (signal vs reference)

5. **Transform to Target Space**
   - Use `navis.xform_brain()` for coordinate transformation
   - Apply template-specific transformations

6. **Validate and Export**
   - Check coordinate bounds
   - Ensure anatomical orientation (X longest, Z shortest)
   - Export in VFB-compatible format

### Error Handling

- **Missing Template Specs**: Fall back to flybrains defaults
- **Coordinate Bounds**: Verify within template extents
- **Memory Issues**: Process in chunks for large volumes
- **Orientation**: Ensure proper anatomical orientation

### Quality Assurance

- Compare transformed coordinates to expected ranges
- Validate voxelization parameters
- Check for data loss during transformation
- Verify channel separation (signal vs reference)

This guide enables automated identification and processing of fly brain imaging data for integration with Virtual Fly Brain and other neuroanatomical resources.