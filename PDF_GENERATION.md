# PDF Report Generation Guide

This guide explains how to generate professionally formatted PDF reports from your RCA agent analysis results.

## Installation

First, ensure you have the required dependency installed:

```bash
pip install reportlab
```

Or install all requirements:

```bash
pip install -r requirements.txt
```

## Quick Start

### Method 1: Using the Quick Function (Recommended)

```python
from multiAgentSystem.pdf_generator import quick_pdf_report

# Your RCA agent output
result = AGENT.predict({
    "user_context": "Query is failing with executor errors",
    "logs_path": "/path/to/spark/logs"
})

# Generate PDF with one line
pdf_path = quick_pdf_report(result, "rca_report.pdf")
print(f"Report generated: {pdf_path}")
```

### Method 2: Direct Integration in Notebook

```python
# After running your RCA analysis
result = AGENT.predict({
    "user_context": "Spark job failing intermittently",
    "logs_path": "/Volumes/catalog/schema/logs/"
})

# Import the PDF generator
from multiAgentSystem.pdf_generator import quick_pdf_report

# Generate the report
quick_pdf_report(result, "spark_rca_report.pdf")
```

## Advanced Usage

### Customized PDF Generation

```python
from multiAgentSystem.pdf_generator import generate_pdf_report

# Generate with custom settings
generate_pdf_report(
    output_data=result,
    output_path="detailed_report.pdf",
    title="Critical Query Failure Analysis",
    include_metadata=True,       # Show confidence, iterations
    include_evidence=True,        # Include log excerpts
    max_evidence_items=5,         # Limit evidence to 5 items
    include_keywords=True,        # Show search keywords
    include_critique=True         # Include critic feedback
)
```

### Function Parameters

#### `generate_pdf_report()`

- **`output_data`** (required): The output dictionary from the RCA agent
- **`output_path`** (required): Path where the PDF should be saved
- **`title`**: Custom title for the report (default: "Spark Root Cause Analysis Report")
- **`include_metadata`**: Include confidence, iterations, approval status (default: True)
- **`include_evidence`**: Include log evidence sections (default: True)
- **`max_evidence_items`**: Maximum evidence items to show (default: 3, None for all)
- **`include_keywords`**: Include search keywords section (default: True)
- **`include_critique`**: Include critic feedback (default: False)

#### `quick_pdf_report()`

Simplified function with sensible defaults:
- **`output_data`** (required): The output dictionary from the RCA agent
- **`output_path`**: Path for the PDF (default: "rca_report.pdf")

## Report Structure

The generated PDF includes the following sections:

### 1. Header
- Report title
- Generation timestamp

### 2. Analysis Summary (if `include_metadata=True`)
- Confidence level (as percentage)
- Number of iterations
- Critic approval status

### 3. Problem Description
- Clear description of the identified problem

### 4. Root Cause Analysis
- Detailed explanation of the root cause

### 5. Recommended Mitigation
- Step-by-step mitigation strategies
- Automatically formatted as numbered list when possible

### 6. Search Keywords (if `include_keywords=True`)
- Keywords used to search the logs
- Highlighted for easy reference

### 7. Supporting Evidence (if `include_evidence=True`)
- Log excerpts that support the analysis
- Limited to `max_evidence_items` for readability
- Formatted in monospace font

### 8. Critic Feedback (if `include_critique=True`)
- Validation feedback from the critic agent
- Highlights any concerns or gaps

## Complete Example

```python
from multiAgentSystem.pdf_generator import generate_pdf_report

# Your agent output
result = {
    'output': {
        'problem': "Query failed due to executor memory issues",
        'rca': "Root cause is insufficient memory allocation...",
        'mitigation': "Increase executor memory. Optimize queries. Use partitioning.",
        'confidence': 0.85,
        'iterations': 3,
        'keywords': ['OutOfMemoryError', 'executor lost', 'GC overhead'],
        'evidence': [
            "Log evidence 1: Executor lost at timestamp...",
            "Log evidence 2: Memory pressure detected..."
        ],
        'critic_approved': True,
        'critique': 'Analysis is well-supported by evidence.'
    }
}

# Generate comprehensive report
generate_pdf_report(
    output_data=result,
    output_path="comprehensive_rca_report.pdf",
    title="Production Query Failure - RCA Report",
    include_metadata=True,
    include_evidence=True,
    max_evidence_items=3,
    include_keywords=True,
    include_critique=True
)
```

## Integration Patterns

### Pattern 1: Batch Processing

```python
from multiAgentSystem.pdf_generator import quick_pdf_report
import os

def analyze_multiple_jobs(job_contexts, output_dir="reports"):
    os.makedirs(output_dir, exist_ok=True)
    
    for job_id, context in job_contexts.items():
        result = AGENT.predict(context)
        pdf_path = f"{output_dir}/rca_{job_id}.pdf"
        quick_pdf_report(result, pdf_path)
        print(f"Generated report for {job_id}")
```

### Pattern 2: Conditional Reporting

```python
from multiAgentSystem.pdf_generator import generate_pdf_report

result = AGENT.predict(context)

# Only generate detailed reports for high-confidence results
if result['output']['confidence'] > 0.7:
    generate_pdf_report(
        result,
        "high_confidence_report.pdf",
        include_critique=True,
        include_evidence=True,
        max_evidence_items=5
    )
else:
    # Generate minimal report for low-confidence results
    generate_pdf_report(
        result,
        "low_confidence_report.pdf",
        include_critique=True,
        include_evidence=False
    )
```

### Pattern 3: Custom Wrapper Function

```python
from multiAgentSystem.pdf_generator import generate_pdf_report
from datetime import datetime

def generate_timestamped_report(result, base_name="rca_report"):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{base_name}_{timestamp}.pdf"
    
    return generate_pdf_report(
        output_data=result,
        output_path=filename,
        include_metadata=True,
        include_evidence=True,
        max_evidence_items=3
    )

# Usage
result = AGENT.predict(context)
pdf_path = generate_timestamped_report(result, "spark_failure")
```

## Troubleshooting

### Issue: ImportError for reportlab

**Solution**: Install reportlab
```bash
pip install reportlab
```

### Issue: "Missing required fields in output_data"

**Solution**: Ensure your output contains `problem`, `rca`, and `mitigation` fields:
```python
# Check structure
print(result.keys())
print(result['output'].keys())
```

### Issue: PDF text encoding errors

**Solution**: The function automatically handles special characters, but if you encounter issues:
- Check for null bytes in your data
- Ensure text is proper UTF-8

### Issue: Very large PDF files

**Solution**: Limit evidence items:
```python
generate_pdf_report(result, "report.pdf", max_evidence_items=2)
```

## Best Practices

1. **Use descriptive titles** that include context about the analysis
2. **Limit evidence items** to 3-5 for readability
3. **Include critique** only when sharing with technical reviewers
4. **Use quick_pdf_report()** for routine reports
5. **Generate timestamped reports** to maintain history
6. **Store reports** in a dedicated directory structure

## Example Output

The generated PDF will have:
- Professional styling with color-coded sections
- Clear hierarchical structure
- Proper spacing and typography
- Monospace formatting for log evidence
- Table-based metadata display
- Timestamp and disclaimer footer

## Support

For issues or questions:
1. Check the function docstrings: `help(generate_pdf_report)`
2. Review the example file: `examples/pdf_generation_example.py`
3. See the main documentation: `README.md`
