"""PDF report generator for rocket motor tests."""

import io
from datetime import datetime
from typing import Dict, List
import matplotlib
matplotlib.use('Agg')  # Use non-interactive backend
import matplotlib.pyplot as plt
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image, PageBreak
from reportlab.lib.enums import TA_CENTER, TA_LEFT


class TestReportGenerator:
    """Generate PDF reports for rocket motor tests."""

    def __init__(self):
        self.styles = getSampleStyleSheet()
        self._setup_custom_styles()

    def _setup_custom_styles(self):
        """Create custom paragraph styles."""
        self.styles.add(ParagraphStyle(
            name='CustomTitle',
            parent=self.styles['Heading1'],
            fontSize=24,
            textColor=colors.HexColor('#1e3a8a'),
            spaceAfter=30,
            alignment=TA_CENTER
        ))

        self.styles.add(ParagraphStyle(
            name='SectionHeader',
            parent=self.styles['Heading2'],
            fontSize=16,
            textColor=colors.HexColor('#2563eb'),
            spaceAfter=12,
            spaceBefore=12
        ))

        self.styles.add(ParagraphStyle(
            name='MetricLabel',
            parent=self.styles['Normal'],
            fontSize=10,
            textColor=colors.HexColor('#64748b')
        ))

    def generate_report(self, test_data: Dict) -> io.BytesIO:
        """Generate PDF report for a test."""
        buffer = io.BytesIO()

        # Create PDF document
        doc = SimpleDocTemplate(
            buffer,
            pagesize=letter,
            rightMargin=0.75*inch,
            leftMargin=0.75*inch,
            topMargin=0.75*inch,
            bottomMargin=0.75*inch
        )

        # Build content
        story = []

        # Title
        story.append(Paragraph("Rocket Motor Test Report", self.styles['CustomTitle']))
        story.append(Spacer(1, 0.2*inch))

        # Test metadata
        story.extend(self._build_metadata_section(test_data))
        story.append(Spacer(1, 0.3*inch))

        # Thrust curve chart
        chart_image = self._generate_thrust_curve(test_data)
        if chart_image:
            story.append(Paragraph("Thrust Curve", self.styles['SectionHeader']))
            story.append(chart_image)
            story.append(Spacer(1, 0.3*inch))

        # Analysis metrics
        if test_data.get('analysis'):
            story.extend(self._build_analysis_section(test_data['analysis']))

        # Warnings
        if test_data.get('analysis', {}).get('warnings'):
            story.append(Spacer(1, 0.2*inch))
            story.extend(self._build_warnings_section(test_data['analysis']['warnings']))

        # Raw data table (on new page)
        if test_data.get('data') and test_data['data'].get('readings'):
            story.append(PageBreak())
            story.extend(self._build_raw_data_section(test_data))

        # Build PDF
        doc.build(story)
        buffer.seek(0)
        return buffer

    def _build_metadata_section(self, test_data: Dict) -> List:
        """Build test metadata section."""
        elements = []

        elements.append(Paragraph("Test Information", self.styles['SectionHeader']))

        # Format timestamp
        timestamp_str = test_data.get('timestamp', 'N/A')
        if timestamp_str != 'N/A':
            try:
                dt = datetime.fromisoformat(timestamp_str)
                timestamp_str = dt.strftime('%Y-%m-%d %H:%M:%S')
            except:
                pass

        # Create metadata table
        data = [
            ['Test ID:', str(test_data.get('id', 'N/A'))],
            ['Label:', test_data.get('label', 'Unlabeled')],
            ['Date:', timestamp_str],
            ['Duration:', f"{(test_data.get('duration_ms', 0) / 1000):.2f} seconds"],
            ['Motor Class:', test_data.get('motor_class', 'N/A')],
        ]

        table = Table(data, colWidths=[2*inch, 4*inch])
        table.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 11),
            ('TEXTCOLOR', (0, 0), (0, -1), colors.HexColor('#475569')),
            ('ALIGN', (0, 0), (0, -1), 'RIGHT'),
            ('ALIGN', (1, 0), (1, -1), 'LEFT'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('LEFTPADDING', (0, 0), (-1, -1), 8),
            ('RIGHTPADDING', (0, 0), (-1, -1), 8),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ]))

        elements.append(table)
        return elements

    def _generate_thrust_curve(self, test_data: Dict) -> Image:
        """Generate thrust curve chart as image."""
        if not test_data.get('data') or not test_data['data'].get('readings'):
            return None

        readings = test_data['data']['readings']
        start_time = readings[0]['timestamp']

        times = [(r['timestamp'] - start_time) / 1000.0 for r in readings]
        forces = [r.get('force', 0) for r in readings]

        # Create figure
        fig, ax = plt.subplots(figsize=(7, 4))
        ax.plot(times, forces, linewidth=2, color='#2563eb')
        ax.fill_between(times, forces, alpha=0.3, color='#2563eb')

        ax.set_xlabel('Time (s)', fontsize=11)
        ax.set_ylabel('Thrust (N)', fontsize=11)
        ax.set_title('Thrust vs Time', fontsize=13, fontweight='bold')
        ax.grid(True, alpha=0.3)

        # Add peak thrust annotation
        max_force = max(forces)
        max_time = times[forces.index(max_force)]
        ax.plot(max_time, max_force, 'ro', markersize=8)
        ax.annotate(f'Peak: {max_force:.2f} N',
                   xy=(max_time, max_force),
                   xytext=(10, 10), textcoords='offset points',
                   bbox=dict(boxstyle='round,pad=0.5', fc='yellow', alpha=0.7),
                   arrowprops=dict(arrowstyle='->', connectionstyle='arc3,rad=0'))

        plt.tight_layout()

        # Save to BytesIO buffer (keeps image in memory)
        img_buffer = io.BytesIO()
        plt.savefig(img_buffer, format='png', dpi=150, bbox_inches='tight')
        plt.close(fig)
        img_buffer.seek(0)

        # Create ReportLab Image from buffer
        img = Image(img_buffer, width=6*inch, height=3.5*inch)

        return img

    def _build_analysis_section(self, analysis: Dict) -> List:
        """Build analysis metrics section."""
        elements = []

        elements.append(Paragraph("Analysis Results", self.styles['SectionHeader']))

        # Create metrics table
        metrics_data = [
            ['Metric', 'Value', 'Unit'],
            ['Peak Thrust', f"{analysis.get('peak_thrust_n', 0):.2f}", 'N'],
            ['Average Thrust', f"{analysis.get('avg_thrust_n', 0):.2f}", 'N'],
            ['Total Impulse', f"{analysis.get('total_impulse_ns', 0):.2f}", 'N·s'],
            ['Burn Time', f"{analysis.get('burn_time_s', 0):.2f}", 's'],
            ['Time to Peak', f"{analysis.get('time_to_peak_s', 0):.2f}", 's'],
            ['Time to 90%', f"{analysis.get('time_to_90pct_s', 0):.2f}", 's'],
            ['Rise Rate', f"{analysis.get('rise_rate_ns', 0):.2f}", 'N/s'],
            ['Decay Rate', f"{abs(analysis.get('decay_rate_ns', 0)):.2f}", 'N/s'],
            ['Thrust Stability (σ)', f"{analysis.get('thrust_stability_std', 0):.2f}", 'N'],
            ['Impulse Efficiency', f"{(analysis.get('impulse_efficiency', 0) * 100):.1f}", '%'],
            ['Burn Profile', analysis.get('burn_profile', 'N/A'), ''],
            ['Motor Class', analysis.get('motor_class', 'N/A'), ''],
            ['CATO Detected', 'YES' if analysis.get('cato_detected') else 'NO', ''],
        ]

        table = Table(metrics_data, colWidths=[2.5*inch, 1.5*inch, 1*inch])
        table.setStyle(TableStyle([
            # Header row
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2563eb')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 11),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),

            # Data rows
            ('FONTNAME', (0, 1), (0, -1), 'Helvetica-Bold'),
            ('FONTNAME', (1, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 10),
            ('ALIGN', (0, 1), (0, -1), 'LEFT'),
            ('ALIGN', (1, 1), (1, -1), 'RIGHT'),
            ('ALIGN', (2, 1), (2, -1), 'LEFT'),

            # Grid
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e1')),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),

            # Padding
            ('LEFTPADDING', (0, 0), (-1, -1), 8),
            ('RIGHTPADDING', (0, 0), (-1, -1), 8),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),

            # Alternating row colors
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f1f5f9')]),
        ]))

        elements.append(table)
        return elements

    def _build_warnings_section(self, warnings: List[str]) -> List:
        """Build warnings section."""
        elements = []

        elements.append(Paragraph("⚠ Warnings", self.styles['SectionHeader']))

        for warning in warnings:
            elements.append(Paragraph(f"• {warning}", self.styles['Normal']))
            elements.append(Spacer(1, 0.1*inch))

        return elements

    def _build_raw_data_section(self, test_data: Dict) -> List:
        """Build raw data table section."""
        elements = []

        elements.append(Paragraph("Raw Data", self.styles['SectionHeader']))
        elements.append(Spacer(1, 0.1*inch))

        readings = test_data['data']['readings']
        start_time = readings[0]['timestamp']

        # Limit to reasonable number of rows (e.g., every 10th point if more than 500 points)
        step = max(1, len(readings) // 500)

        # Build table data
        table_data = [['Time (s)', 'Force (N)', 'Raw ADC']]

        for i in range(0, len(readings), step):
            reading = readings[i]
            time_s = (reading['timestamp'] - start_time) / 1000.0
            force_n = reading.get('force', 0)
            raw_adc = reading.get('raw', 0)

            table_data.append([
                f"{time_s:.3f}",
                f"{force_n:.2f}",
                f"{raw_adc}"
            ])

        # Add note if data was downsampled
        if step > 1:
            note = f"Note: Showing every {step} data points ({len(table_data)-1} of {len(readings)} total points)"
            elements.append(Paragraph(note, self.styles['Normal']))
            elements.append(Spacer(1, 0.1*inch))

        # Create table with smaller font
        table = Table(table_data, colWidths=[1.5*inch, 1.5*inch, 1.5*inch])
        table.setStyle(TableStyle([
            # Header row
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2563eb')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 9),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),

            # Data rows
            ('FONTNAME', (0, 1), (-1, -1), 'Courier'),
            ('FONTSIZE', (0, 1), (-1, -1), 7),
            ('ALIGN', (0, 1), (0, -1), 'RIGHT'),
            ('ALIGN', (1, 1), (1, -1), 'RIGHT'),
            ('ALIGN', (2, 1), (2, -1), 'RIGHT'),

            # Grid
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cbd5e1')),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),

            # Padding
            ('LEFTPADDING', (0, 0), (-1, -1), 6),
            ('RIGHTPADDING', (0, 0), (-1, -1), 6),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),

            # Alternating row colors
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8fafc')]),
        ]))

        elements.append(table)
        return elements
