"""
PDF Report Generator for RCA Analysis Results

This module provides functionality to generate professionally formatted PDF reports
from the multi-agent RCA system output. It uses ReportLab for high-quality PDF generation
and supports Markdown formatting for rich text content.
"""

import os
import re
from datetime import datetime
from typing import Dict, Any, Optional, List, Union
import markdown
from xml.sax.saxutils import escape

try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import letter, A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch, mm
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, PageBreak,
        Table, TableStyle, KeepTogether, Image, Frame, PageTemplate,
        ListFlowable, ListItem, Preformatted
    )
    from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_JUSTIFY, TA_RIGHT
    from reportlab.pdfgen import canvas
except ImportError:
    raise ImportError(
        "reportlab is required for PDF generation. "
        "Install it with: pip install reportlab"
    )

# --- Constants & Styles ---

BRAND_COLOR = colors.HexColor('#104776')  # Dark Blue (Databricks-ish)
ACCENT_COLOR = colors.HexColor('#FF3621')  # Spark Orange-ish
BG_COLOR = colors.HexColor('#F5F7FA')     # Light Gray
CODE_BG_COLOR = colors.HexColor('#F0F0F0')
BORDER_COLOR = colors.HexColor('#E1E4E8')

class ReportStyles:
    """Custom styles for the RCA report."""
    
    def __init__(self):
        self.styles = getSampleStyleSheet()
        
        # Title (Cover Page)
        self.cover_title = ParagraphStyle(
            'CoverTitle',
            parent=self.styles['Title'],
            fontSize=28,
            leading=34,
            textColor=BRAND_COLOR,
            alignment=TA_CENTER,
            spaceAfter=20,
            fontName='Helvetica-Bold'
        )
        
        self.cover_subtitle = ParagraphStyle(
            'CoverSubtitle',
            parent=self.styles['Normal'],
            fontSize=14,
            leading=18,
            textColor=colors.gray,
            alignment=TA_CENTER,
            spaceAfter=40
        )

        # Headings
        self.h1 = ParagraphStyle(
            'CustomH1',
            parent=self.styles['Heading1'],
            fontSize=18,
            leading=22,
            textColor=BRAND_COLOR,
            spaceBefore=20,
            spaceAfter=10,
            fontName='Helvetica-Bold',
            borderPadding=5,
            borderWidth=0,
            borderColor=BRAND_COLOR
        )
        
        self.h2 = ParagraphStyle(
            'CustomH2',
            parent=self.styles['Heading2'],
            fontSize=14,
            leading=18,
            textColor=colors.HexColor('#2c3e50'),
            spaceBefore=15,
            spaceAfter=8,
            fontName='Helvetica-Bold'
        )
        
        self.h3 = ParagraphStyle(
            'CustomH3',
            parent=self.styles['Heading3'],
            fontSize=12,
            leading=14,
            textColor=colors.HexColor('#34495e'),
            spaceBefore=10,
            spaceAfter=5,
            fontName='Helvetica-Bold'
        )

        # Body Text
        self.body = ParagraphStyle(
            'CustomBody',
            parent=self.styles['Normal'],
            fontSize=10,
            leading=14,
            textColor=colors.HexColor('#24292e'),
            alignment=TA_JUSTIFY,
            spaceAfter=8
        )
        
        # Code Blocks
        self.code = ParagraphStyle(
            'CustomCode',
            parent=self.styles['Code'],
            fontSize=8,
            leading=10,
            textColor=colors.HexColor('#24292e'),
            backColor=CODE_BG_COLOR,
            borderPadding=10,
            leftIndent=0,
            rightIndent=0,
            spaceAfter=10,
            fontName='Courier',
            wordWrap='CJK' # Helps with wrapping long lines
        )
        
        # Metadata Label/Value
        self.meta_label = ParagraphStyle(
            'MetaLabel',
            parent=self.styles['Normal'],
            fontSize=9,
            textColor=colors.gray,
            fontName='Helvetica-Bold'
        )
        
        self.meta_value = ParagraphStyle(
            'MetaValue',
            parent=self.styles['Normal'],
            fontSize=9,
            textColor=colors.black,
            fontName='Helvetica'
        )

# --- Markdown Parsing Helper ---

def md_to_flowables(text: str, styles: ReportStyles) -> List[Any]:
    """
    Convert Markdown text to ReportLab Flowables.
    Handles headers, lists, code blocks, and basic formatting.
    """
    if not text:
        return []
        
    flowables = []
    lines = text.split('\n')
    
    in_code_block = False
    code_buffer = []
    
    current_list_items = []
    
    for line in lines:
        # Code Blocks
        if line.strip().startswith('```'):
            if in_code_block:
                # End of code block
                code_text = '\n'.join(code_buffer)
                # Escape XML characters for ReportLab
                code_text = escape(code_text)
                # Replace spaces with non-breaking spaces for indentation preservation
                code_text = code_text.replace(' ', '&nbsp;')
                code_text = code_text.replace('\n', '<br/>')
                
                flowables.append(Paragraph(code_text, styles.code))
                code_buffer = []
                in_code_block = False
            else:
                # Start of code block
                in_code_block = True
            continue
            
        if in_code_block:
            code_buffer.append(line)
            continue
            
        # Headers
        if line.startswith('# '):
            flowables.append(Paragraph(line[2:], styles.h1))
        elif line.startswith('## '):
            flowables.append(Paragraph(line[3:], styles.h2))
        elif line.startswith('### '):
            flowables.append(Paragraph(line[4:], styles.h3))
            
        # Lists (Basic support)
        elif line.strip().startswith('- ') or line.strip().startswith('* '):
            item_text = line.strip()[2:]
            # Process inline formatting
            item_text = _process_inline_formatting(item_text)
            current_list_items.append(ListItem(Paragraph(item_text, styles.body)))
            
        # Normal Text
        elif line.strip():
            if current_list_items:
                flowables.append(ListFlowable(current_list_items, bulletType='bullet', start='circle'))
                current_list_items = []
                
            # Process inline formatting
            formatted_text = _process_inline_formatting(line)
            flowables.append(Paragraph(formatted_text, styles.body))
            
        else:
            # Empty line - flush list if any
            if current_list_items:
                flowables.append(ListFlowable(current_list_items, bulletType='bullet', start='circle'))
                current_list_items = []
            flowables.append(Spacer(1, 4))

    # Flush remaining list
    if current_list_items:
        flowables.append(ListFlowable(current_list_items, bulletType='bullet', start='circle'))

    return flowables

def _process_inline_formatting(text: str) -> str:
    """Process bold, italic, and code inline formatting for ReportLab."""
    # Escape XML first
    text = escape(text)
    
    # Bold: **text** -> <b>text</b>
    text = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', text)
    # Italic: *text* -> <i>text</i>
    text = re.sub(r'\*(.*?)\*', r'<i>\1</i>', text)
    # Inline Code: `text` -> <font face="Courier" backColor="#F0F0F0">text</font>
    text = re.sub(r'`(.*?)`', r'<font face="Courier" color="#E74C3C">\1</font>', text)
    
    return text

# --- Main Generator ---

def generate_pdf_report(
    output_data: Dict[str, Any],
    output_path: str,
    title: str = "Spark Root Cause Analysis Report",
    include_metadata: bool = True,
    include_evidence: bool = True,
    max_evidence_items: int = 5,
    include_keywords: bool = True,
    include_critique: bool = False,
    evidence_map: Optional[Dict[str, Any]] = None
) -> str:
    """
    Generate a professionally formatted PDF report.
    """
    # Extract data
    data = output_data.get('output', output_data)
    
    # Setup Document
    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        rightMargin=20*mm,
        leftMargin=20*mm,
        topMargin=20*mm,
        bottomMargin=20*mm
    )
    
    styles = ReportStyles()
    story = []
    
    # --- Cover Page ---
    story.append(Spacer(1, 40*mm))
    story.append(Paragraph(title, styles.cover_title))
    story.append(Spacer(1, 10*mm))
    
    timestamp = datetime.now().strftime("%B %d, %Y")
    story.append(Paragraph(f"Generated on {timestamp}", styles.cover_subtitle))
    
    story.append(Spacer(1, 20*mm))
    
    # Executive Summary Box (Metadata)
    if include_metadata:
        confidence = data.get('confidence', 0.0)
        iterations = data.get('iterations', 'N/A')
        
        # Create a nice summary table
        summary_data = [
            [Paragraph("Confidence Score", styles.meta_label), Paragraph(f"{confidence:.0%}" if isinstance(confidence, (int, float)) else str(confidence), styles.meta_value)],
            [Paragraph("Iterations", styles.meta_label), Paragraph(str(iterations), styles.meta_value)],
            [Paragraph("Analysis Status", styles.meta_label), Paragraph("Completed", styles.meta_value)]
        ]
        
        t = Table(summary_data, colWidths=[40*mm, 80*mm])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.white),
            ('BOX', (0, 0), (-1, -1), 1, BORDER_COLOR),
            ('INNERGRID', (0, 0), (-1, -1), 0.5, BORDER_COLOR),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('PADDING', (0, 0), (-1, -1), 12),
        ]))
        
        # Center the table
        t_centered = Table([[t]], colWidths=[170*mm])
        t_centered.setStyle(TableStyle([('ALIGN', (0,0), (-1,-1), 'CENTER')]))
        story.append(t_centered)
    
    story.append(PageBreak())
    
    # --- Content Sections ---
    
    # 1. Problem Description
    story.append(Paragraph("1. Problem Description", styles.h1))
    story.extend(md_to_flowables(data.get('problem', 'No problem description provided.'), styles))
    story.append(Spacer(1, 10))
    
    # 2. Root Cause Analysis
    story.append(Paragraph("2. Root Cause Analysis", styles.h1))
    story.extend(md_to_flowables(data.get('rca', 'No analysis provided.'), styles))
    story.append(Spacer(1, 10))
    
    # 3. Mitigation
    story.append(Paragraph("3. Recommended Mitigation", styles.h1))
    story.extend(md_to_flowables(data.get('mitigation', 'No mitigation provided.'), styles))
    story.append(Spacer(1, 10))
    
    # 4. Evidence
    ev_map = evidence_map if evidence_map else data.get('evidence_map', {})
    if include_evidence and ev_map:
        story.append(Paragraph("4. Supporting Evidence", styles.h1))
        
        # Sort evidence
        sorted_evidence = sorted(
            ev_map.items(),
            key=lambda x: x[1].get('count', 0),
            reverse=True
        )
        
        if max_evidence_items:
            sorted_evidence = sorted_evidence[:max_evidence_items]
            
        for idx, (pattern, entry) in enumerate(sorted_evidence, 1):
            # Evidence Header
            count = entry.get('count', 0)
            story.append(Paragraph(f"{idx}. {pattern} <font size=9 color='gray'>(Count: {count})</font>", styles.h3))
            
            # Evidence Details Table
            files = entry.get('files', [])
            files_str = ", ".join(files[:3]) + (f" (+{len(files)-3} more)" if len(files) > 3 else "")
            
            samples = entry.get('sample_lines', [])
            sample_text = samples[0][:300] + "..." if samples else "No sample available"
            
            ev_data = [
                [Paragraph("Files:", styles.meta_label), Paragraph(files_str, styles.code)],
                [Paragraph("Sample:", styles.meta_label), Paragraph(escape(sample_text), styles.code)]
            ]
            
            ev_table = Table(ev_data, colWidths=[25*mm, 145*mm])
            ev_table.setStyle(TableStyle([
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('PADDING', (0, 0), (-1, -1), 4),
                ('GRID', (0, 0), (-1, -1), 0.25, BORDER_COLOR),
                ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#FAFAFA')), # Label column bg
            ]))
            story.append(ev_table)
            story.append(Spacer(1, 8))

    # 5. Keywords (Optional)
    if include_keywords and 'keywords' in data:
        keywords = data.get('keywords', [])
        if keywords:
            story.append(Paragraph("5. Search Keywords", styles.h1))
            kw_text = ", ".join([f"<b>{k}</b>" for k in keywords])
            story.append(Paragraph(kw_text, styles.body))

    # Footer
    def footer(canvas, doc):
        canvas.saveState()
        canvas.setFont('Helvetica', 9)
        canvas.setFillColor(colors.gray)
        page_num = canvas.getPageNumber()
        text = f"Page {page_num} | Spark RCA Assistant"
        canvas.drawRightString(A4[0] - 20*mm, 15*mm, text)
        canvas.restoreState()

    # Build
    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    
    return output_path

def quick_pdf_report(output_data: Dict[str, Any], output_path: str = "rca_report.pdf") -> str:
    """Convenience wrapper."""
    return generate_pdf_report(output_data, output_path)