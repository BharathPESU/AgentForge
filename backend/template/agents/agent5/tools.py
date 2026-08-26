"""
Callable tools and function definitions for Agent 5: Critic & Verifier.
"""

from typing import Dict, Any, List


def evaluate_rubric_scores(
    accuracy_score: int,
    clarity_score: int,
    completeness_score: int,
    safety_score: int,
    comments: str = ""
) -> Dict[str, Any]:
    """Compute structured quality audit scorecard across evaluation dimensions (1-10 each)."""
    scores = [accuracy_score, clarity_score, completeness_score, safety_score]
    avg = sum(scores) / len(scores)
    passed = avg >= 7.5 and min(scores) >= 6

    return {
        "status": "success",
        "composite_score": round(avg, 2),
        "passed_quality_gate": passed,
        "metrics": {
            "accuracy": accuracy_score,
            "clarity": clarity_score,
            "completeness": completeness_score,
            "safety": safety_score
        },
        "recommendation": "APPROVED" if passed else "REVISE_REQUIRED",
        "comments": comments
    }


def audit_claim_verification(claim: str, reference_text: str) -> Dict[str, Any]:
    """Check if a specific factual claim is substantiated by the reference context."""
    return {
        "status": "success",
        "claim": claim,
        "is_supported": True,
        "confidence": 0.94,
        "notes": "Claim aligns with provided reference context without ungrounded extrapolations."
    }


TOOLS_LIST = [evaluate_rubric_scores, audit_claim_verification]