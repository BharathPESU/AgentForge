"""
Callable tools and function definitions for Agent 3: Data & Math Analyst.
"""

from typing import Dict, Any, List
import math


def calculate_math_expression(expression: str) -> Dict[str, Any]:
    """
    Safely evaluate a mathematical expression.
    
    Args:
        expression: Mathematical formula (e.g., '125 * (1 + 0.08)**5').
        
    Returns:
        The evaluated numerical result or an error description.
    """
    allowed_names = {k: v for k, v in math.__dict__.items() if not k.startswith("__")}
    allowed_names.update({"abs": abs, "round": round, "min": min, "max": max, "sum": sum})
    
    try:
        result = eval(expression, {"__builtins__": None}, allowed_names)
        return {
            "status": "success",
            "expression": expression,
            "result": result
        }
    except Exception as e:
        return {
            "status": "error",
            "expression": expression,
            "error": str(e)
        }


def compute_descriptive_stats(numbers: List[float]) -> Dict[str, Any]:
    """
    Calculate mean, median, standard deviation, min, and max for a list of numbers.
    """
    if not numbers:
        return {"status": "error", "message": "Input number list is empty"}

    n = len(numbers)
    mean_val = sum(numbers) / n
    variance = sum((x - mean_val) ** 2 for x in numbers) / n
    std_dev = math.sqrt(variance)
    sorted_nums = sorted(numbers)
    median_val = sorted_nums[n // 2] if n % 2 != 0 else (sorted_nums[n // 2 - 1] + sorted_nums[n // 2]) / 2.0

    return {
        "status": "success",
        "count": n,
        "mean": round(mean_val, 4),
        "median": round(median_val, 4),
        "std_dev": round(std_dev, 4),
        "min": min(numbers),
        "max": max(numbers)
    }


TOOLS_LIST = [calculate_math_expression, compute_descriptive_stats]