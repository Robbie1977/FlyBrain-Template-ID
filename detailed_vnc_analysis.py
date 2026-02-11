#!/usr/bin/env python3
import numpy as np
import nrrd
from scipy import ndimage

print('=== Detailed VNC Leg vs Flight Neuropil Analysis ===')
data, header = nrrd.read('channels/VNC_SPR8AD.Fru11.12DBD.FB1.1.NC82.Brain.40x.1.composite_channel0.nrrd')

# Create a thresholded version to focus on dense neuropils
threshold = np.percentile(data[data > 0], 75)  # 75th percentile of non-zero values
dense_regions = data > threshold

print(f'Dense neuropil threshold: {threshold:.1f}')
print(f'Dense voxels: {np.sum(dense_regions)} / {np.sum(data > 0)} ({100*np.sum(dense_regions)/np.sum(data > 0):.1f}%)')

# Label connected components to identify distinct neuropil regions
labeled_regions, num_regions = ndimage.label(dense_regions)
print(f'Number of distinct dense regions: {num_regions}')

# Analyze the size distribution of regions
region_sizes = []
for region_id in range(1, num_regions + 1):
    size = np.sum(labeled_regions == region_id)
    region_sizes.append(size)

region_sizes = sorted(region_sizes, reverse=True)
print(f'Top 10 region sizes: {region_sizes[:10]}')

# Large regions (> 1000 voxels) are likely flight neuropil
# Medium regions (100-1000 voxels) could be leg neuropils
# Small regions (< 100 voxels) are likely noise/artifacts

large_regions = [s for s in region_sizes if s > 1000]
medium_regions = [s for s in region_sizes if 100 <= s <= 1000]
small_regions = [s for s in region_sizes if s < 100]

print(f'Large regions (>1000 vx, likely flight): {len(large_regions)}')
print(f'Medium regions (100-1000 vx, likely legs): {len(medium_regions)}')
print(f'Small regions (<100 vx, likely noise): {len(small_regions)}')

# Analyze the positions of large regions (potential flight neuropil)
flight_candidates = []
for region_id in range(1, num_regions + 1):
    if np.sum(labeled_regions == region_id) > 1000:
        coords = np.where(labeled_regions == region_id)
        centroid = (np.mean(coords[0]), np.mean(coords[1]), np.mean(coords[2]))
        flight_candidates.append(centroid)

print(f'\nFlight neuropil candidate positions (X, Y, Z voxel coordinates):')
for i, (x, y, z) in enumerate(flight_candidates[:3]):  # Show top 3
    # Convert to relative position within the volume
    rel_x = x / data.shape[0]
    rel_y = y / data.shape[1]
    rel_z = z / data.shape[2]
    print(f'  Region {i+1}: X={rel_x:.2f}, Y={rel_y:.2f}, Z={rel_z:.2f} ({"dorsal" if rel_z > 0.6 else "ventral" if rel_z < 0.4 else "mid"})')

# Check if flight neuropil is properly positioned dorsally
if flight_candidates:
    avg_z = np.mean([pos[2] for pos in flight_candidates]) / data.shape[2]
    print(f'\nAverage flight neuropil Z-position: {avg_z:.2f} ({"dorsal ✓" if avg_z > 0.6 else "ventral ✗" if avg_z < 0.4 else "mid ⚠"})')

print('\n=== Interpretation ===')
print('Expected VNC anatomy:')
print('- Flight neuropil: 1 large dorsal structure')
print('- Leg neuropils: 6 medium lateral/ventral structures')
print('- Current analysis shows:', 'large dorsal structure ✓' if any(pos[2]/data.shape[2] > 0.6 for pos in flight_candidates) else 'no dorsal flight neuropil ✗')