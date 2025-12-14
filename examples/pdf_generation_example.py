"""
Example: Using the PDF Report Generator

This script demonstrates how to use the PDF report generator
to create formatted reports from RCA agent output.
"""

from multiAgentSystem.pdf_generator import generate_pdf_report, quick_pdf_report

# Example output from the RCA agent
example_output = {
    'output': {
        'problem': "Query ID 01f0a416-cb80-1228-9eda-e3118e89fd48 failed due to executor 0 failure during execution of a TakeOrderedAndProject operation.",
        'rca': "The root cause appears to be memory issues during the TakeOrderedAndProject operation...",
        'mitigation': "To resolve this issue, several approaches can be taken. First, consider optimizing the query...",
        'confidence': 0.85,
        'iterations': 3,
        'keywords': ['01f0a416-cb80-1228-9eda-e3118e89fd48', 'OutOfMemoryError', 'executor lost'],
        'evidence_map': {
            "OutOfMemoryError": {
                "count": 5,
                "files": ["executor-1.log", "executor-2.log"],
                "sample_lines": ["2023-10-27 10:00:01 ERROR Executor: Exception in task 0.0 in stage 0.0 (TID 0) java.lang.OutOfMemoryError: Java heap space"]
            },
            "executor lost": {
                "count": 2,
                "files": ["driver.log"],
                "sample_lines": ["Executor 1 lost"]
            }
        },
        'critic_approved': False,
        'critique': 'The draft claims...'
    }
}

# ============================================================================
# Method 1: Quick PDF Generation (recommended for most cases)
# ============================================================================

# Generate a PDF with default settings
output_path = quick_pdf_report(example_output, "rca_report.pdf")
print(f"PDF generated: {output_path}")


# ============================================================================
# Method 2: Customized PDF Generation
# ============================================================================

# Generate a PDF with custom settings
output_path = generate_pdf_report(
    output_data=example_output,
    output_path="detailed_rca_report.pdf",
    title="Detailed Spark RCA Report",
    include_metadata=True,      # Include confidence, iterations, etc.
    include_evidence=True,       # Include log evidence
    max_evidence_items=5,        # Show up to 5 evidence items
    include_keywords=True,       # Include search keywords
    include_critique=True        # Include critic feedback
)
print(f"Detailed PDF generated: {output_path}")


# ============================================================================
# Method 3: Integration with RCA Agent
# ============================================================================

# Assuming you have the RCAAgent already set up
# from multiAgentSystem.agent_main import AGENT

def analyze_and_generate_report(user_context: str, logs_path: str, output_pdf: str = "rca_report.pdf"):
    """
    Run RCA analysis and generate PDF report.
    
    Args:
        user_context: Description of the problem
        logs_path: Path to Spark logs
        output_pdf: Path for output PDF
        
    Returns:
        Tuple of (analysis_result, pdf_path)
    """
    # Run the RCA agent
    # result = AGENT.predict({
    #     "user_context": user_context,
    #     "logs_path": logs_path
    # })
    
    # For this example, we'll use the example output
    result = example_output
    
    # Generate the PDF report
    pdf_path = quick_pdf_report(result, output_pdf)
    
    print(f"Analysis complete. Report saved to: {pdf_path}")
    return result, pdf_path


# Example usage
if __name__ == "__main__":
    # Example 1: Quick report
    print("Generating quick report...")
    quick_pdf_report(example_output, "quick_report.pdf")
    
    # Example 2: Detailed report
    print("\nGenerating detailed report...")
    generate_pdf_report(
        output_data=example_output,
        output_path="detailed_report.pdf",
        title="Spark Query Failure Analysis",
        include_critique=True
    )
    
    print("\nReports generated successfully!")
