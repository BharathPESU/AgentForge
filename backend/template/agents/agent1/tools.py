"""
Agent 1 Tools Definition Template.
Define custom callable python functions for Agent 1 below.
"""

from typing import Dict, Any

def example_tool(input_param: str) -> Dict[str, Any]:
    """
    Example Tool Template for Agent 1.
    Replace with your custom business logic, API call, vector retrieval, or data parser.
    
    Args:
        input_param: Input argument for the tool.
        
    Returns:
        Structured result dictionary.
    """
    return {
        "status": "success",
        "input": input_param,
        "result": f"Processed input via example_tool: '{input_param}'"
    }


# Export list of callable tools for this agent
TOOLS_LIST = [example_tool]