"""
PDF Report Generation Tool

This tool generates a formatted PDF report from the RCA analysis results.

MLflow Tracing: This tool is decorated with @mlflow.trace for observability in Databricks.
"""

import os
from datetime import datetime
from typing import Dict, Any, Optional
from multiAgentSystem.pdf_generator import generate_pdf_report

try:
    import mlflow
    from mlflow.entities import SpanType
    MLFLOW_AVAILABLE = True
except ImportError:
    MLFLOW_AVAILABLE = False
    # Define a no-op decorator if mlflow is not available
    def noop_decorator(*args, **kwargs):
        def decorator(func):
            return func
        return decorator if not args else decorator(args[0])
    mlflow = type('obj', (object,), {'trace': noop_decorator})


@mlflow.trace(span_type=SpanType.TOOL if MLFLOW_AVAILABLE else None, name="generate_rca_report_tool")
def generate_rca_report_tool(
    output_data: Dict[str, Any],
    reports_dir: str = None,
    base_filename: str = "rca_report"
) -> str:
    """
    Generate a timestamped PDF report from RCA analysis results.

    This tool is traceable via MLflow for observability in Databricks agent traces.

    This tool is called by the supervisor agent before returning final output
    to create a permanent record of the analysis.

    Args:
        output_data: The analysis results containing problem, rca, mitigation, etc.
        reports_dir: Directory to save reports (default: multiAgentSystem/Reports/)
        base_filename: Base name for the report file (default: "rca_report")

    Returns:
        Absolute path to the generated PDF report

    Raises:
        Exception: If PDF generation fails
    """
    try:
        # Determine reports directory
        if reports_dir is None:
            # Get the multiAgentSystem directory
            current_file = os.path.abspath(__file__)
            multiagent_dir = os.path.dirname(os.path.dirname(current_file))
            reports_dir = os.path.join(multiagent_dir, "Reports")
        
        # Create reports directory if it doesn't exist
        os.makedirs(reports_dir, exist_ok=True)
        
        # Generate timestamped filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{base_filename}_{timestamp}.pdf"
        output_path = os.path.join(reports_dir, filename)
        
        # Generate the PDF report
        generate_pdf_report(
            output_data=output_data,
            output_path=output_path,
            title="Spark Root Cause Analysis Report",
            include_metadata=True,
            include_evidence=True,
            max_evidence_items=3,
            include_keywords=True,
            include_critique=False  # Don't include internal critique in final report
        )
        
        return output_path
        
    except Exception as e:
        # Log the error but don't fail the entire workflow
        error_msg = f"Failed to generate PDF report: {str(e)}"
        print(f"Warning: {error_msg}")
        return f"ERROR: {error_msg}"
