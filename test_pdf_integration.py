"""
Test script to verify PDF report generation integration

This script demonstrates that the supervisor agent automatically generates
PDF reports when the analysis completes.
"""

# Mock test to verify the tool works
from multiAgentSystem.tools.pdf_report_tool import generate_rca_report_tool

# Sample RCA output
sample_output = {
    "problem": "Spark query failed due to executor memory issues during shuffle operation.",
    "rca": "The root cause is insufficient executor memory allocation combined with data skew during the shuffle phase.",
    "mitigation": "Increase executor memory from 4GB to 8GB. Enable adaptive query execution. Add salt key to distribute skewed data.",
    "confidence": 0.85,
    "iterations": 3,
    "keywords": ["OutOfMemoryError", "executor lost", "shuffle", "data skew"],
    "evidence": [
        "Log line 1: OutOfMemoryError at shuffle stage",
        "Log line 2: Executor 3 lost with exit code 137",
        "Log line 3: Partition skew detected: 80% data in single partition"
    ],
    "critic_approved": True,
    "critique": "Analysis is well-supported by evidence."
}

print("Testing PDF report generation...")
print("-" * 80)

try:
    pdf_path = generate_rca_report_tool(sample_output, base_filename="test_report")
    print(f"✓ Success! PDF report generated at:")
    print(f"  {pdf_path}")
    print("\nThe supervisor agent will automatically call this tool when analysis completes.")
    print("Check the multiAgentSystem/Reports/ directory for generated reports.")
except Exception as e:
    print(f"✗ Error: {e}")
    print("\nMake sure reportlab is installed:")
    print("  pip install reportlab")
