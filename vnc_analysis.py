#!/usr/bin/env python3
import numpy as np
import nrrd

print('=== VNC Anatomy Analysis: VNC_SPR8AD.Fru11.12DBD.FB1.1.NC82.Brain.40x.1.composite_channel0.nrrd ===')
data, header = nrrd.read('channels/VNC_SPR8AD.Fru11.12DBD.FB1.1.NC82.Brain.40x.1.composite_channel0.nrrd')

print(f'Shape: {data.shape}')
vox_sizes = [header['space directions'][i][i] for i in range(3)]
print(f'Voxel sizes: X={vox_sizes[0]:.3f}, Y={vox_sizes[1]:.3f}, Z={vox_sizes[2]:.3f}')

# Quick analysis of dorsal-ventral distribution
z_step = data.shape[2] // 4
dorsal_quarter = data[:, :, 3*z_step:]  # Most dorsal
ventral_quarter = data[:, :, :z_step]   # Most ventral

dorsal_signal = np.sum(dorsal_quarter > 0)
ventral_signal = np.sum(ventral_quarter > 0)

print(f'\nDorsal quarter signal: {dorsal_signal}')
print(f'Ventral quarter signal: {ventral_signal}')
print(f'Dorsal/ventral ratio: {dorsal_signal/ventral_signal:.2f}')

# Left-right distribution
x_step = data.shape[0] // 4
left_quarter = data[:x_step, :, :]      # Most left
right_quarter = data[3*x_step:, :, :]   # Most right

left_signal = np.sum(left_quarter > 0)
right_signal = np.sum(right_quarter > 0)

print(f'Left quarter signal: {left_signal}')
print(f'Right quarter signal: {right_signal}')
print(f'Left/right ratio: {left_signal/right_signal:.2f}')

# Anterior-posterior distribution
y_step = data.shape[1] // 4
anterior_quarter = data[:, :y_step, :]      # Most anterior
posterior_quarter = data[:, 3*y_step:, :]   # Most posterior

ant_signal = np.sum(anterior_quarter > 0)
post_signal = np.sum(posterior_quarter > 0)

print(f'Anterior quarter signal: {ant_signal}')
print(f'Posterior quarter signal: {post_signal}')
print(f'Anterior/posterior ratio: {ant_signal/post_signal:.2f}')

print('\n=== VNC Anatomy Interpretation ===')
print('Expected VNC features:')
print('- Flight neuropil: dorsal, central, large fused structure')
print('- Leg neuropils: lateral, ventral, six distinct regions')
print('- Anterior-posterior elongation (Y > X)')

print(f'\nCurrent orientation assessment:')
if dorsal_signal > ventral_signal * 1.1:
    print('✓ Dorsal emphasis suggests flight neuropil is correctly positioned dorsally')
else:
    print('✗ Dorsal-ventral distribution suggests possible inversion')

if left_signal < right_signal * 0.9 or left_signal > right_signal * 1.1:
    print('⚠ Asymmetry detected - may indicate specific anatomical positioning')
else:
    print('✓ Relatively symmetric left-right distribution')

if ant_signal > post_signal * 1.1:
    print('⚠ Anterior emphasis - may indicate orientation issue')
elif post_signal > ant_signal * 1.1:
    print('⚠ Posterior emphasis - may indicate orientation issue')
else:
    print('✓ Balanced anterior-posterior distribution')