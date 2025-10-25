"""
Multi-Agent System for Root Cause Analysis

A supervisor-centric multi-agent system for analyzing Spark logs and performing
root cause analysis using LangGraph and Databricks LLM.
"""

# Import the RCAAgent class and AGENT instance
# Note: In a production environment, these would be imported from a Python module
# rather than a notebook. For Databricks environments, notebook imports work fine.
try:
    # Try to import from the notebook (Databricks environment)
    from .agent_main import RCAAgent, AGENT
except ImportError:
    # Fallback for non-notebook environments
    # Define a simple placeholder if the notebook import fails
    class RCAAgent:
        """Placeholder for RCAAgent when notebook import fails."""
        def __init__(self):
            pass
            
        def predict(self, request):
            return {"output": {"error": "Notebook import failed. This is a placeholder."}}
            
        def predict_stream(self, request):
            yield {"type": "error", "message": "Notebook import failed. This is a placeholder."}
    
    # Create a placeholder instance
    AGENT = RCAAgent()

__all__ = ["RCAAgent", "AGENT"]