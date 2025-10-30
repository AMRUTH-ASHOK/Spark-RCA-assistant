"""
PDF Report Generator for RCA Analysis Results

This module provides functionality to generate professionally formatted PDF reports
from the multi-agent RCA system output.
"""

from typing import Dict, Any, Optional, List
from datetime import datetime
import textwrap


def generate_pdf_report(
    output_data: Dict[str, Any],
    output_path: str,
    title: str = "Spark Root Cause Analysis Report",
    include_metadata: bool = True,
    include_evidence: bool = True,
    max_evidence_items: int = 3,
    include_keywords: bool = True,
    include_critique: bool = False
) -> str:
    """
    Generate a formatted PDF report from RCA agent output.
    
    Args:
        output_data: The output dictionary from the RCA agent containing the analysis results
        output_path: Path where the PDF should be saved (e.g., "report.pdf")
        title: Title for the report
        include_metadata: Whether to include metadata section (iterations, confidence, etc.)
        include_evidence: Whether to include evidence section
        max_evidence_items: Maximum number of evidence items to include (set to None for all)
        include_keywords: Whether to include keywords section
        include_critique: Whether to include critic feedback section
        
    Returns:
        Path to the generated PDF file
        
    Raises:
        ImportError: If reportlab is not installed
        ValueError: If output_data is missing required fields
    """
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import letter, A4
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import inch
        from reportlab.platypus import (
            SimpleDocTemplate, Paragraph, Spacer, PageBreak,
            Table, TableStyle, KeepTogether
        )
        from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_JUSTIFY
    except ImportError:
        raise ImportError(
            "reportlab is required for PDF generation. "
            "Install it with: pip install reportlab"
        )
    
    # Validate input data
    if not isinstance(output_data, dict):
        raise ValueError("output_data must be a dictionary")
    
    # Extract the actual output if it's nested
    if 'output' in output_data:
        data = output_data['output']
    else:
        data = output_data
    
    # Validate required fields
    required_fields = ['problem', 'rca', 'mitigation']
    missing_fields = [field for field in required_fields if field not in data]
    if missing_fields:
        raise ValueError(f"Missing required fields in output_data: {missing_fields}")
    
    # Create PDF document
    doc = SimpleDocTemplate(
        output_path,
        pagesize=letter,
        rightMargin=0.75*inch,
        leftMargin=0.75*inch,
        topMargin=0.75*inch,
        bottomMargin=0.75*inch
    )
    
    # Container for PDF elements
    story = []
    
    # Define styles
    styles = getSampleStyleSheet()
    
    # Custom styles
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        textColor=colors.HexColor('#1a1a1a'),
        spaceAfter=30,
        alignment=TA_CENTER,
        fontName='Helvetica-Bold'
    )
    
    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=16,
        textColor=colors.HexColor('#2c5aa0'),
        spaceAfter=12,
        spaceBefore=20,
        fontName='Helvetica-Bold',
        borderWidth=0,
        borderColor=colors.HexColor('#2c5aa0'),
        borderPadding=5,
        backColor=colors.HexColor('#f0f4f8')
    )
    
    subheading_style = ParagraphStyle(
        'CustomSubHeading',
        parent=styles['Heading3'],
        fontSize=13,
        textColor=colors.HexColor('#444444'),
        spaceAfter=8,
        spaceBefore=12,
        fontName='Helvetica-Bold'
    )
    
    body_style = ParagraphStyle(
        'CustomBody',
        parent=styles['BodyText'],
        fontSize=11,
        textColor=colors.HexColor('#333333'),
        spaceAfter=12,
        alignment=TA_JUSTIFY,
        leading=16
    )
    
    code_style = ParagraphStyle(
        'CustomCode',
        parent=styles['Code'],
        fontSize=9,
        textColor=colors.HexColor('#2c3e50'),
        backColor=colors.HexColor('#f8f9fa'),
        leftIndent=20,
        rightIndent=20,
        spaceAfter=10,
        fontName='Courier'
    )
    
    # Add title
    story.append(Paragraph(title, title_style))
    story.append(Spacer(1, 0.2*inch))
    
    # Add generation timestamp
    timestamp = datetime.now().strftime("%B %d, %Y at %I:%M %p")
    story.append(Paragraph(f"<i>Generated on {timestamp}</i>", styles['Normal']))
    story.append(Spacer(1, 0.3*inch))
    
    # Add metadata section if requested
    if include_metadata:
        confidence = data.get('confidence', 0.0)
        iterations = data.get('iterations', 'N/A')
        critic_approved = data.get('critic_approved', False)
        
        story.append(Paragraph("Analysis Summary", heading_style))
        
        # Create metadata table
        metadata_data = [
            ['Confidence Level', f"{confidence:.0%}" if isinstance(confidence, (int, float)) else str(confidence)],
            ['Iterations', str(iterations)],
            ['Critic Approved', '✓ Yes' if critic_approved else '✗ No']
        ]
        
        metadata_table = Table(metadata_data, colWidths=[2*inch, 4*inch])
        metadata_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#e8f4f8')),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.HexColor('#333333')),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cccccc'))
        ]))
        
        story.append(metadata_table)
        story.append(Spacer(1, 0.3*inch))
    
    # Add Problem Description
    story.append(Paragraph("1. Problem Description", heading_style))
    story.append(Paragraph(_clean_text(data.get('problem', 'N/A')), body_style))
    story.append(Spacer(1, 0.2*inch))
    
    # Add Root Cause Analysis
    story.append(Paragraph("2. Root Cause Analysis", heading_style))
    story.append(Paragraph(_clean_text(data.get('rca', 'N/A')), body_style))
    story.append(Spacer(1, 0.2*inch))
    
    # Add Mitigation Steps
    story.append(Paragraph("3. Recommended Mitigation", heading_style))
    mitigation_text = _clean_text(data.get('mitigation', 'N/A'))
    
    # Try to format as numbered list if it contains sentences
    mitigation_paragraphs = _format_mitigation_steps(mitigation_text)
    for para in mitigation_paragraphs:
        story.append(Paragraph(para, body_style))
    story.append(Spacer(1, 0.2*inch))
    
    # Add Keywords section if requested
    if include_keywords and 'keywords' in data:
        keywords = data.get('keywords', [])
        if keywords:
            story.append(Paragraph("4. Search Keywords", heading_style))
            keywords_text = ', '.join([f"<b>{kw}</b>" for kw in keywords])
            story.append(Paragraph(keywords_text, body_style))
            story.append(Spacer(1, 0.2*inch))
    
    # Add Evidence section if requested
    if include_evidence and 'evidence' in data:
        evidence_list = data.get('evidence', [])
        if evidence_list:
            story.append(Paragraph("5. Supporting Evidence", heading_style))
            
            # Limit evidence items if specified
            if max_evidence_items is not None and max_evidence_items > 0:
                evidence_list = evidence_list[:max_evidence_items]
            
            for idx, evidence in enumerate(evidence_list, 1):
                story.append(Paragraph(f"<b>Evidence {idx}:</b>", subheading_style))
                
                # Truncate very long evidence
                evidence_text = _clean_text(str(evidence))
                if len(evidence_text) > 2000:
                    evidence_text = evidence_text[:2000] + "... [truncated]"
                
                story.append(Paragraph(evidence_text, code_style))
                story.append(Spacer(1, 0.15*inch))
    
    # Add Critique section if requested
    if include_critique and 'critique' in data:
        critique = data.get('critique', '')
        if critique and critique.strip():
            story.append(Paragraph("6. Critic Feedback", heading_style))
            story.append(Paragraph(_clean_text(critique), body_style))
            story.append(Spacer(1, 0.2*inch))
    
    # Add footer note
    story.append(Spacer(1, 0.5*inch))
    story.append(Paragraph(
        "<i>This report was automatically generated by the Spark RCA Multi-Agent System. "
        "Please verify all findings with your specific environment and use cases.</i>",
        styles['Italic']
    ))
    
    # Build PDF
    doc.build(story)
    
    return output_path


def _clean_text(text: str) -> str:
    """
    Clean and escape text for PDF rendering.
    
    Args:
        text: Raw text to clean
        
    Returns:
        Cleaned text safe for PDF rendering
    """
    if not isinstance(text, str):
        text = str(text)
    
    # Replace problematic characters
    text = text.replace('&', '&amp;')
    text = text.replace('<', '&lt;')
    text = text.replace('>', '&gt;')
    
    # Remove or replace special characters that might cause issues
    text = text.replace('\x00', '')
    
    return text


def _format_mitigation_steps(text: str) -> List[str]:
    """
    Format mitigation text into structured steps.
    
    Args:
        text: Raw mitigation text
        
    Returns:
        List of formatted paragraph strings
    """
    # Split by common delimiters
    steps = []
    
    # Try to split by periods followed by capital letters or numbers
    import re
    sentences = re.split(r'(?<=[.!?])\s+(?=[A-Z0-9])', text)
    
    if len(sentences) > 1:
        for idx, sentence in enumerate(sentences, 1):
            if sentence.strip():
                steps.append(f"<b>{idx}.</b> {sentence.strip()}")
    else:
        # Return as single paragraph if no clear structure
        steps.append(text)
    
    return steps


# Convenience function for quick PDF generation
def quick_pdf_report(output_data: Dict[str, Any], output_path: str = "rca_report.pdf") -> str:
    """
    Quick PDF generation with default settings.
    
    Args:
        output_data: The output dictionary from the RCA agent
        output_path: Path where the PDF should be saved
        
    Returns:
        Path to the generated PDF file
    """
    return generate_pdf_report(
        output_data=output_data,
        output_path=output_path,
        include_metadata=True,
        include_evidence=True,
        max_evidence_items=3,
        include_keywords=True,
        include_critique=False
    )
