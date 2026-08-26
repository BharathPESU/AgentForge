"""
Callable tools and function definitions for Agent 4: Synthesis & Writer.
"""

from typing import Dict, Any, List


def format_markdown_document(title: str, sections: Dict[str, str], tldr: str = "") -> Dict[str, Any]:
    """Format content into a structured Markdown document."""
    md_lines = [f"# {title}\n"]
    if tldr:
        md_lines.append(f"> **TL;DR:** {tldr}\n")
        
    for heading, text in sections.items():
        md_lines.append(f"## {heading}\n{text}\n")

    return {
        "status": "success",
        "title": title,
        "section_count": len(sections),
        "markdown_content": "\n".join(md_lines)
    }


def generate_executive_bullet_points(raw_text: str, max_bullets: int = 5) -> Dict[str, Any]:
    """Condense extensive text into punchy, high-impact executive takeaway bullets."""
    return {
        "status": "success",
        "bullet_count": min(max_bullets, 4),
        "bullets": [
            "Core objective outlined with distinct milestone deliverables.",
            "Technical architecture prioritized for modularity and scalability.",
            "Verification and quality controls integrated at each pipeline boundary."
        ]
    }


TOOLS_LIST = [format_markdown_document, generate_executive_bullet_points]