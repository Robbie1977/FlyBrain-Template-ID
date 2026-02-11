#!/usr/bin/env python3
import numpy as np
import nrrd

def analyze_vnc_anatomy(filename):
    print(f"\n=== Detailed VNC Anatomy Analysis: {filename} ===")
    data, header = nrrd.read(filename)

    print(f"Shape: {data.shape}")
    vox_sizes = [header['space directions'][i][i] for i in range(3)]
    print(f"Voxel sizes: X={vox_sizes[0]:.3f}, Y={vox_sizes[1]:.3f}, Z={vox_sizes[2]:.3f}")

    # Get bounding box of signal
    nonzero = data > 0
    coords = np.where(nonzero)

    if len(coords[0]) > 0:
        bbox = [(np.min(c), np.max(c)) for c in coords]
        signal_dims = [(bbox[i][1] - bbox[i][0]) * vox_sizes[i] for i in range(3)]
        print(f"Actual signal dimensions: X={signal_dims[0]:.1f}μm, Y={signal_dims[1]:.1f}μm, Z={signal_dims[2]:.1f}μm")

        # Analyze Z-distribution (dorsal-ventral)
        z_coords = coords[2]
        z_range = np.max(z_coords) - np.min(z_coords)
        print(f"Z extent: {z_range} voxels = {z_range * vox_sizes[2]:.1f}μm")

        # Look for anatomical features in different Z slices
        unique_z = np.unique(z_coords)
        print(f"Signal present in {len(unique_z)} Z slices out of {data.shape[2]} total")

        # Analyze X-Y distribution at different Z levels
        mid_z = data.shape[2] // 2
        dorsal_half = data[:, :, mid_z:]  # dorsal (higher Z)
        ventral_half = data[:, :, :mid_z]  # ventral (lower Z)

        dorsal_signal = np.sum(dorsal_half > 0)
        ventral_signal = np.sum(ventral_half > 0)

        print(f"Dorsal half signal voxels: {dorsal_signal}")
        print(f"Ventral half signal voxels: {ventral_signal}")
        print(f"Dorsal/ventral ratio: {dorsal_signal/ventral_signal:.2f}")

        # Look for bilateral symmetry
        mid_x = data.shape[0] // 2
        left_half = data[:mid_x, :, :]
        right_half = data[mid_x:, :, :]

        left_signal = np.sum(left_half > 0)
        right_signal = np.sum(right_half > 0)

        print(f"Left half signal voxels: {left_signal}")
        print(f"Right half signal voxels: {right_signal}")
        print(f"Left/right symmetry ratio: {left_signal/right_signal:.2f}")

        # Check for distinct anatomical regions
        # Look at projections to identify potential leg vs flight neuropils
        x_projection = np.sum(data > 0, axis=0)  # Sum along X
        y_projection = np.sum(data > 0, axis=1)  # Sum along Y
        z_projection = np.sum(data > 0, axis=2)  # Sum along Z

        # Analyze dorsal-ventral distribution in more detail
        z_step = data.shape[2] // 4
        dorsal_quarter = data[:, :, 3*z_step:]  # Most dorsal
        mid_dorsal = data[:, :, 2*z_step:3*z_step]
        mid_ventral = data[:, :, z_step:2*z_step]
        ventral_quarter = data[:, :, :z_step]  # Most ventral

        dorsal_signal = np.sum(dorsal_quarter > 0)
        mid_dorsal_signal = np.sum(mid_dorsal > 0)
        mid_ventral_signal = np.sum(mid_ventral > 0)
        ventral_signal = np.sum(ventral_quarter > 0)

        print("
Dorsal-ventral layering:")
        print(f"Most dorsal quarter: {dorsal_signal} voxels")
        print(f"Mid-dorsal quarter: {mid_dorsal_signal} voxels")
        print(f"Mid-ventral quarter: {mid_ventral_signal} voxels")
        print(f"Most ventral quarter: {ventral_signal} voxels")

        # Look for lateral distribution (potential leg neuropils)
        x_step = data.shape[0] // 4
        left_quarter = data[:x_step, :, :]
        mid_left = data[x_step:2*x_step, :, :]
        mid_right = data[2*x_step:3*x_step, :, :]
        right_quarter = data[3*x_step:, :, :]

        left_signal = np.sum(left_quarter > 0)
        mid_left_signal = np.sum(mid_left > 0)
        mid_right_signal = np.sum(mid_right > 0)
        right_signal = np.sum(right_quarter > 0)

        print("
Left-right distribution:")
        print(f"Left quarter: {left_signal} voxels")
        print(f"Mid-left quarter: {mid_left_signal} voxels")
        print(f"Mid-right quarter: {mid_right_signal} voxels")
        print(f"Right quarter: {right_signal} voxels")

        # Analyze anterior-posterior distribution
        y_step = data.shape[1] // 4
        anterior_quarter = data[:, :y_step, :]
        mid_anterior = data[:, y_step:2*y_step, :]
        mid_posterior = data[:, 2*y_step:3*y_step, :]
        posterior_quarter = data[:, 3*y_step:, :]

        ant_signal = np.sum(anterior_quarter > 0)
        mid_ant_signal = np.sum(mid_anterior > 0)
        mid_post_signal = np.sum(mid_posterior > 0)
        post_signal = np.sum(posterior_quarter > 0)

        print("
Anterior-posterior distribution:")
        print(f"Anterior quarter: {ant_signal} voxels")
        print(f"Mid-anterior quarter: {mid_ant_signal} voxels")
        print(f"Mid-posterior quarter: {mid_post_signal} voxels")
        print(f"Posterior quarter: {post_signal} voxels")

        # VNC anatomy interpretation
        print("\n=== VNC Anatomy Interpretation ===")
        print("Expected VNC features:")
        print("- Flight neuropil: dorsal, central, large fused structure")
        print("- Leg neuropils: lateral, ventral, six distinct regions")
        print("- Anterior-posterior elongation (Y > X)")

        # Check for potential leg neuropil pattern (should be more lateral)
        lateral_signal = left_signal + right_signal
        central_signal = mid_left_signal + mid_right_signal
        lateral_ratio = lateral_signal / central_signal if central_signal > 0 else float('inf')

        print(f"\nLateral/central signal ratio: {lateral_ratio:.2f}")
        if lateral_ratio > 1.2:
            print("→ Strong lateral signal suggests leg neuropils are positioned laterally ✓")
        elif lateral_ratio < 0.8:
            print("→ Strong central signal suggests flight neuropil dominance")
        else:
            print("→ Balanced distribution, unclear orientation")

        # Check dorsal-ventral pattern
        dorsal_ratio = dorsal_signal / ventral_signal if ventral_signal > 0 else float('inf')
        print(f"Dorsal/ventral signal ratio: {dorsal_ratio:.2f}")
        if dorsal_ratio > 1.1:
            print("→ Dorsal emphasis suggests flight neuropil is dorsal ✓")
        elif dorsal_ratio < 0.9:
            print("→ Ventral emphasis suggests leg neuropils are dorsal (inverted)")
        else:
            print("→ Balanced dorsal-ventral distribution")

if __name__ == "__main__":
    analyze_vnc_anatomy("channels/VNC_SPR8AD.Fru11.12DBD.FB1.1.NC82.Brain.40x.1.composite_channel0.nrrd")