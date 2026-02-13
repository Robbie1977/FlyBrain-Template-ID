#!/usr/bin/env python3
"""
Generate a comprehensive PDF report of the fly brain orientation analysis.
Includes thumbnails of max projections, histograms, and analysis results.
"""

import numpy as np
import nrrd
import matplotlib.pyplot as plt
from matplotlib.backends.backend_pdf import PdfPages
from pathlib import Path
from scipy.signal import find_peaks
import sys
from reportlab.lib.pagesizes import letter, A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle
from reportlab.lib.units import inch
from io import BytesIO
import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend

class OrientationAnalysisPDF:
    """Generate PDF report for fly brain orientation analysis."""

    def __init__(self, output_path="orientation_analysis_report.pdf"):
        self.output_path = output_path
        self.templates = {}
        self.samples = {}
        self.corrected_samples = {}

        # Initialize PDF document
        self.doc = SimpleDocTemplate(output_path, pagesize=A4)
        self.styles = getSampleStyleSheet()
        self.story = []

        # Custom styles
        self.title_style = ParagraphStyle(
            'CustomTitle',
            parent=self.styles['Heading1'],
            fontSize=16,
            spaceAfter=30,
        )

        self.heading_style = ParagraphStyle(
            'CustomHeading',
            parent=self.styles['Heading2'],
            fontSize=14,
            spaceAfter=20,
        )

        self.normal_style = self.styles['Normal']

    def load_templates(self):
        """Load template data."""
        template_files = [
            Path("JRC2018U_template.nrrd"),
            Path("JRC2018U_template_lps.nrrd"),
            Path("JRCVNC2018U_template.nrrd"),
            Path("JRCVNC2018U_template_lps.nrrd")
        ]

        for template_file in template_files:
            if template_file.exists():
                print(f"Loading template: {template_file.name}")
                data, header = nrrd.read(str(template_file))
                vox_sizes = [header['space directions'][i][i] for i in range(3)]

                # Calculate projections and peaks
                projections, peaks_data = self.analyze_projections(data, vox_sizes)

                self.templates[template_file.stem] = {
                    'data': data,
                    'header': header,
                    'vox_sizes': vox_sizes,
                    'projections': projections,
                    'peaks': peaks_data,
                    'shape': data.shape,
                    'physical_size': [s * vs for s, vs in zip(data.shape, vox_sizes)]
                }

    def load_samples(self):
        """Load sample data from channels folder."""
        channels_dir = Path("channels")
        if not channels_dir.exists():
            return

        sample_files = list(channels_dir.glob("*_background.nrrd"))  # Process all samples

        for sample_file in sample_files:
            print(f"Loading sample: {sample_file.name}")
            data, header = nrrd.read(str(sample_file))
            vox_sizes = [header['space directions'][i][i] for i in range(3)]

            # Calculate projections and peaks
            projections, peaks_data = self.analyze_projections(data, vox_sizes)

            # Determine template
            if "VNC" in sample_file.name:
                template_key = "JRCVNC2018U_template"
            else:
                template_key = "JRC2018U_template_lps"

            # Check orientation
            orientation_correct, changes_needed = self.check_orientation(peaks_data, template_key, projections)

            self.samples[sample_file.stem] = {
                'data': data,
                'header': header,
                'vox_sizes': vox_sizes,
                'projections': projections,
                'peaks': peaks_data,
                'template': template_key,
                'orientation_correct': orientation_correct,
                'changes_needed': changes_needed,
                'shape': data.shape,
                'physical_size': [s * vs for s, vs in zip(data.shape, vox_sizes)]
            }

            # Load corresponding signal channel
            signal_file = sample_file.parent / sample_file.name.replace('_background.nrrd', '_signal.nrrd')
            if signal_file.exists():
                signal_data, _ = nrrd.read(str(signal_file))
                signal_projections, _ = self.analyze_projections(signal_data, vox_sizes)
                self.samples[sample_file.stem]['signal_projections'] = signal_projections
                self.samples[sample_file.stem]['signal_data'] = signal_data

    def analyze_projections(self, data, vox_sizes):
        """Analyze projections and find peaks."""
        # Calculate signal threshold
        signal_threshold = np.percentile(data[data > 0], 75) if np.any(data > 0) else np.mean(data)

        projections = {}
        peaks_data = {}

        axes_names = ['X (Left-Right)', 'Y (Anterior-Posterior)', 'Z (Dorsal-Ventral)']

        for axis in range(3):
            # Create projection
            proj = np.sum(data, axis=tuple(i for i in range(3) if i != axis))

            # Filtered projection
            filtered_data = np.where(data > signal_threshold, data, 0)
            filtered_proj = np.sum(filtered_data, axis=tuple(i for i in range(3) if i != axis))

            # Find peaks
            peaks, properties = find_peaks(filtered_proj,
                                         height=np.max(filtered_proj)*0.1,
                                         distance=len(filtered_proj)//20)

            projections[axis] = {
                'full': proj,
                'filtered': filtered_proj,
                'physical_coords': np.arange(len(filtered_proj)) * vox_sizes[axis]
            }

            peaks_data[axis] = {
                'peaks': peaks,
                'properties': properties,
                'num_peaks': len(peaks),
                'axis_name': axes_names[axis]
            }

        return projections, peaks_data

    def check_orientation(self, peaks_data, template_key, sample_projections):
        """Check if sample orientation matches template expectations."""
        if template_key not in self.templates:
            return False, "Template not found"

        template_peaks = self.templates[template_key]['peaks']

        # Simple orientation check based on peak patterns
        # This is a simplified version - in practice would be more sophisticated
        changes = []

        # Check X-axis (should have bilateral peaks for brain)
        if template_key.startswith('JRC2018U'):
            expected_x_peaks = 8
            if peaks_data[0]['num_peaks'] > expected_x_peaks * 1.5:
                changes.append("90° rotation (X-Y swap)")
            elif peaks_data[0]['num_peaks'] < expected_x_peaks * 0.5:
                changes.append("Potential clipping or wrong template")

        # Check Y-axis asymmetry
        y_proj = sample_projections[1]['filtered']
        center_idx = len(y_proj) // 2
        front_half = np.sum(y_proj[:center_idx])
        back_half = np.sum(y_proj[center_idx:])
        asymmetry = (front_half - back_half) / (front_half + back_half) if (front_half + back_half) > 0 else 0

        if template_key.startswith('JRC2018U') and asymmetry < -0.1:
            changes.append("180° Y-axis rotation")

        orientation_correct = len(changes) == 0
        changes_str = ", ".join(changes) if changes else "None"

        return orientation_correct, changes_str

    def create_max_projection_thumbnail(self, data, axis, title, figsize=(3, 3)):
        """Create max projection thumbnail for given axis."""
        if axis == 0:  # X projection (sum along X)
            proj = np.max(data, axis=0)
        elif axis == 1:  # Y projection (sum along Y)
            proj = np.max(data, axis=1)
        else:  # Z projection (sum along Z)
            proj = np.max(data, axis=2)

        fig, ax = plt.subplots(figsize=figsize)
        ax.imshow(proj, cmap='gray')
        ax.set_title(title, fontsize=8)
        ax.axis('off')

        # Save to buffer
        buf = BytesIO()
        fig.savefig(buf, format='png', dpi=100, bbox_inches='tight')
        buf.seek(0)
        plt.close(fig)

        return buf

    def create_comparison_thumbnail(self, sample_data, template_data, axis, axis_name, figsize=(3, 2)):
        """Create side-by-side comparison thumbnail for sample and template."""
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=figsize)

        # Sample projection
        if axis == 0:  # X projection
            sample_proj = np.max(sample_data, axis=0)
            template_proj = np.max(template_data, axis=0)
        elif axis == 1:  # Y projection
            sample_proj = np.max(sample_data, axis=1)
            template_proj = np.max(template_data, axis=1)
        else:  # Z projection
            sample_proj = np.max(sample_data, axis=2)
            template_proj = np.max(template_data, axis=2)

        # Plot sample
        ax1.imshow(sample_proj, cmap='gray')
        ax1.set_title('Sample', fontsize=8)
        ax1.axis('off')

        # Plot template
        ax2.imshow(template_proj, cmap='gray')
        ax2.set_title('Template', fontsize=8)
        ax2.axis('off')

        # Overall title
        fig.suptitle(f'{axis_name}', fontsize=9, y=0.95)

        plt.tight_layout()

        # Save to buffer
        buf = BytesIO()
        fig.savefig(buf, format='png', dpi=100, bbox_inches='tight')
        buf.seek(0)
        plt.close(fig)

        return buf

    def create_histogram_plot(self, projections, peaks_data, template_projections=None, title="", figsize=(6, 4)):
        """Create histogram plot with optional template overlay."""
        fig, axes = plt.subplots(3, 1, figsize=figsize)
        axes_names = ['X (Left-Right)', 'Y (Anterior-Posterior)', 'Z (Dorsal-Ventral)']

        for axis in range(3):
            ax = axes[axis]
            proj_data = projections[axis]
            coords = proj_data['physical_coords']
            filtered_proj = proj_data['filtered']

            # Plot sample histogram
            ax.plot(coords, filtered_proj, 'b-', linewidth=1, label='Sample')

            # Plot template guide lines if provided
            if template_projections:
                template_coords = template_projections[axis]['physical_coords']
                template_filtered = template_projections[axis]['filtered']
                # Scale template to match sample range
                scale_factor = np.max(filtered_proj) / np.max(template_filtered) if np.max(template_filtered) > 0 else 1
                ax.plot(template_coords, template_filtered * scale_factor, 'r--', linewidth=1, alpha=0.7, label='Template')

            # Mark peaks
            if axis in peaks_data and len(peaks_data[axis]['peaks']) > 0:
                peak_positions = coords[peaks_data[axis]['peaks']]
                peak_heights = peaks_data[axis]['properties']['peak_heights']
                ax.plot(peak_positions, peak_heights, 'go', markersize=3, label='Peaks')

            ax.set_title(f'{axes_names[axis]} - {peaks_data[axis]["num_peaks"]} peaks', fontsize=8)
            ax.set_xlabel('Position (μm)', fontsize=6)
            ax.set_ylabel('Intensity', fontsize=6)
            ax.tick_params(axis='both', which='major', labelsize=6)
            if axis == 0:
                ax.legend(fontsize=6)

        plt.suptitle(title, fontsize=10)
        plt.tight_layout()

        # Save to buffer
        buf = BytesIO()
        fig.savefig(buf, format='png', dpi=150, bbox_inches='tight')
        buf.seek(0)
        plt.close(fig)

        return buf

    def add_title_page(self):
        """Add title page to PDF."""
        title = Paragraph("Fly Brain Anatomical Orientation Analysis Report", self.title_style)
        self.story.append(title)
        self.story.append(Spacer(1, 0.5*inch))

        date = Paragraph(f"Generated on: {self.get_current_date()}", self.normal_style)
        self.story.append(date)
        self.story.append(Spacer(1, 0.5*inch))

        summary = Paragraph("This report contains analysis of fly brain microscopy images, including template characteristics, sample orientation detection, and correction results.", self.normal_style)
        self.story.append(summary)
        self.story.append(Spacer(1, 1*inch))

    def add_template_section(self):
        """Add template analysis section."""
        heading = Paragraph("Template Analysis Results", self.heading_style)
        self.story.append(heading)
        self.story.append(Spacer(1, 0.25*inch))

        for template_name, template_data in self.templates.items():
            # Template info
            template_title = Paragraph(f"Template: {template_name}", self.styles['Heading3'])
            self.story.append(template_title)

            info_text = f"""
            <b>Physical Dimensions:</b> {template_data['physical_size'][0]:.1f} × {template_data['physical_size'][1]:.1f} × {template_data['physical_size'][2]:.1f} μm<br/>
            <b>Voxel Resolution:</b> {template_data['vox_sizes'][0]:.3f} × {template_data['vox_sizes'][1]:.3f} × {template_data['vox_sizes'][2]:.3f} μm<br/>
            <b>Data Range:</b> {template_data['data'].min()}-{template_data['data'].max()}
            """
            self.story.append(Paragraph(info_text, self.normal_style))

            # Max projections
            projections_title = Paragraph("Maximum Intensity Projections:", self.styles['Heading4'])
            self.story.append(projections_title)

            # Create thumbnails
            thumbnail_table_data = []
            row_data = []

            for axis, axis_name in enumerate(['X-Y (Dorsal)', 'X-Z (Lateral)', 'Y-Z (Anterior)']):
                buf = self.create_max_projection_thumbnail(
                    template_data['data'], axis,
                    f"{template_name}\n{axis_name}",
                    figsize=(2, 2)
                )
                img = Image(buf)
                img.drawHeight = 1.5*inch
                img.drawWidth = 1.5*inch
                row_data.append(img)

                if len(row_data) == 3:
                    thumbnail_table_data.append(row_data)
                    row_data = []

            if row_data:
                thumbnail_table_data.append(row_data)

            if thumbnail_table_data:
                table = Table(thumbnail_table_data)
                table.setStyle(TableStyle([
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                    ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ]))
                self.story.append(table)

            # Histograms
            hist_buf = self.create_histogram_plot(
                template_data['projections'],
                template_data['peaks'],
                title=f"{template_name} Projection Analysis"
            )
            hist_img = Image(hist_buf)
            hist_img.drawHeight = 4*inch
            hist_img.drawWidth = 6*inch
            self.story.append(hist_img)

            self.story.append(Spacer(1, 0.5*inch))

    def add_sample_section(self):
        """Add sample analysis section."""
        heading = Paragraph("Sample Analysis Results", self.heading_style)
        self.story.append(heading)
        self.story.append(Spacer(1, 0.25*inch))

        for sample_name, sample_data in self.samples.items():
            # Sample info
            sample_title = Paragraph(f"Sample: {sample_name}", self.styles['Heading3'])
            self.story.append(sample_title)

            template_name = sample_data['template']
            info_text = f"""
            <b>Template Used:</b> {template_name}<br/>
            <b>Physical Dimensions:</b> {sample_data['physical_size'][0]:.1f} × {sample_data['physical_size'][1]:.1f} × {sample_data['physical_size'][2]:.1f} μm<br/>
            <b>Voxel Resolution:</b> {sample_data['vox_sizes'][0]:.3f} × {sample_data['vox_sizes'][1]:.3f} × {sample_data['vox_sizes'][2]:.3f} μm<br/>
            <b>Orientation Correct:</b> {'Yes' if sample_data['orientation_correct'] else 'No'}<br/>
            <b>Changes Needed:</b> {sample_data['changes_needed']}
            """
            self.story.append(Paragraph(info_text, self.normal_style))

            # Max projections comparison
            projections_title = Paragraph("Maximum Intensity Projections Comparison (Sample vs Template):", self.styles['Heading4'])
            self.story.append(projections_title)

            # Create comparison thumbnails for each axis
            comparison_table_data = []

            for axis, axis_name in enumerate(['X-Y (Dorsal)', 'X-Z (Lateral)', 'Y-Z (Anterior)']):
                buf = self.create_comparison_thumbnail(
                    sample_data['data'],
                    self.templates[template_name]['data'],
                    axis,
                    axis_name
                )
                img = Image(buf)
                img.drawHeight = 1.8*inch
                img.drawWidth = 3*inch
                comparison_table_data.append([img])

            if comparison_table_data:
                table = Table(comparison_table_data)
                table.setStyle(TableStyle([
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                    ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                ]))
                self.story.append(table)

            # Signal channel thumbnails if available
            if 'signal_data' in sample_data:
                signal_title = Paragraph("Signal Channel Projections:", self.styles['Heading4'])
                self.story.append(signal_title)

                # Create signal channel thumbnails
                signal_table_data = []
                signal_row_data = []

                for axis, axis_name in enumerate(['X-Y (Dorsal)', 'X-Z (Lateral)', 'Y-Z (Anterior)']):
                    buf = self.create_max_projection_thumbnail(
                        sample_data['signal_data'], axis,
                        f"{sample_name} Signal\n{axis_name}",
                        figsize=(2, 2)
                    )
                    img = Image(buf)
                    img.drawHeight = 1.5*inch
                    img.drawWidth = 1.5*inch
                    signal_row_data.append(img)

                    if len(signal_row_data) == 3:
                        signal_table_data.append(signal_row_data)
                        signal_row_data = []

                if signal_row_data:
                    signal_table_data.append(signal_row_data)

                if signal_table_data:
                    signal_table = Table(signal_table_data)
                    signal_table.setStyle(TableStyle([
                        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                    ]))
                    self.story.append(signal_table)

            # Histograms with template overlay
            if template_name in self.templates:
                hist_buf = self.create_histogram_plot(
                    sample_data['projections'],
                    sample_data['peaks'],
                    self.templates[template_name]['projections'],
                    title=f"{sample_name} vs {template_name} Projection Analysis"
                )
                hist_img = Image(hist_buf)
                hist_img.drawHeight = 4*inch
                hist_img.drawWidth = 6*inch
                self.story.append(hist_img)

            self.story.append(Spacer(1, 0.5*inch))

    def get_current_date(self):
        """Get current date string."""
        from datetime import datetime
        return datetime.now().strftime("%B %d, %Y")

    def generate_pdf(self):
        """Generate the complete PDF report."""
        print("Loading data...")
        self.load_templates()
        self.load_samples()

        print("Creating PDF content...")
        self.add_title_page()
        self.add_template_section()
        self.add_sample_section()

        print(f"Building PDF: {self.output_path}")
        self.doc.build(self.story)
        print("PDF generation complete!")

def main():
    """Main function."""
    pdf_generator = OrientationAnalysisPDF()
    pdf_generator.generate_pdf()

if __name__ == "__main__":
    main()