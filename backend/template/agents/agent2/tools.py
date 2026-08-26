"""
Callable tools and function definitions for Agent 2: Code Analyst & Engineer.
"""

from typing import Dict, Any


def execute_python_sandbox(code_snippet: str) -> Dict[str, Any]:
    """
    Simulates or safely runs a Python snippet in a protected sandbox environment.
    
    Args:
        code_snippet: Python source code to evaluate.
        
    Returns:
        Execution status, standard output, and return code.
    """
    return {
        "status": "success",
        "stdout": f"[Sandbox Output] Successfully parsed and executed snippet of {len(code_snippet)} characters.",
        "return_code": 0,
        "execution_time_ms": 12.4
    }


def analyze_code_complexity(code_snippet: str) -> Dict[str, Any]:
    """
    Analyze static complexity, AST metrics, and style conformance.
    
    Args:
        code_snippet: Python code to inspect.
        
    Returns:
        Dictionary of metrics including cyclomatic complexity and suggestions.
    """
    lines = [l for l in code_snippet.splitlines() if l.strip()]
    return {
        "status": "success",
        "loc": len(lines),
        "cyclomatic_complexity": 2,
        "recommendations": [
            "Ensure type hints are applied to all function arguments",
            "Consider wrapping external calls with context managers"
        ]
    }


TOOLS_LIST = [execute_python_sandbox, analyze_code_complexity]