"""OpenAI LLM integration for paper analysis and notebook generation."""
import asyncio
import json
import logging
from typing import Any

from openai import AsyncOpenAI

from app.sanitizer import sanitize_paper_text

logger = logging.getLogger(__name__)

MODEL_NAME = "gpt-5.4"
LLM_TIMEOUT_SECONDS = 300  # 5 minutes per API call — generation of 30-50 cells can take time

# ── Prompts ──────────────────────────────────────────────

ANALYSIS_SYSTEM_PROMPT = """\
You are an expert ML research analyst. Given the full text of a research paper, \
produce a structured JSON analysis that identifies everything needed to create a \
production-quality implementation notebook.

Your output MUST be valid JSON with this exact structure:
{
  "title": "Paper title",
  "summary": "2-3 sentence summary of the paper's contribution",
  "key_algorithms": [
    {
      "name": "Algorithm name",
      "description": "What it does and why it matters",
      "equations": ["Key equations in LaTeX or text form"],
      "parameters": ["Key hyperparameters and their typical values"]
    }
  ],
  "methodology": ["Step-by-step methodology items"],
  "data_characteristics": "Description of data types and distributions used in the paper",
  "suggested_packages": ["Python packages needed for implementation"],
  "evaluation_metrics": ["Metrics used to evaluate results"]
}

Be thorough and precise. Identify ALL key algorithms, not just the main one. \
Include all important equations. This analysis will be used by top ML researchers \
at labs like OpenAI and DeepMind to accelerate paper replication."""

GENERATION_SYSTEM_PROMPT = """\
You are a world-class ML engineer and educator creating a Google Colab notebook that \
implements a research paper as a graduate-level tutorial. The notebook must be \
RESEARCH-GRADE — suitable for ML researchers at top labs (OpenAI, DeepMind, Google Brain) \
to use for paper replication and deep understanding.

CRITICAL REQUIREMENTS:
1. **Production Python**: Type hints on all functions, proper docstrings, modular design
2. **Realistic Synthetic Data**: Generate data that matches the paper's domain — \
   use appropriate distributions, realistic scales, and proper data shapes. \
   NEVER use trivial random noise. Document WHY each distribution was chosen.
3. **Complete Implementation**: Implement EVERY key algorithm from the paper, \
   not just the main one. Each algorithm gets its own section.
4. **Equation-to-Code Mapping**: For every key equation in the paper, show it in \
   LaTeX/markdown, then EXPLICITLY connect it to the code. Use comments like \
   "# Equation 3 from Section 2.1 — corresponds to the attention weight computation". \
   Map each mathematical symbol to its code variable.
5. **Step-by-Step Algorithm Breakdown**: For each algorithm, provide a numbered \
   step-by-step walkthrough BEFORE the code. Example: "Step 1: Compute query, key, \
   value projections. Step 2: Calculate scaled dot-product attention scores..."
6. **Why This Matters**: For each major component, include a "Why this matters" or \
   "Intuition" markdown cell explaining WHY this step is important, what problem it \
   solves, and what would happen without it. This is critical for educational value.
7. **Visualizations**: Use matplotlib/plotly to visualize intermediate results, \
   attention maps, loss curves, data distributions, etc.
8. **Expected vs Actual Output**: After key computations, include verification cells \
   that compare expected output shapes/ranges/properties against actual output. \
   Example: "Expected: attention weights sum to 1.0 per row. Actual: ..."
9. **Runnable in Colab**: All cells must execute WITHOUT errors when run sequentially. \
   Include pip installs. CRITICAL: Every code cell must include ALL imports it uses — \
   do NOT assume imports from previous cells carry over. If a cell uses `dataclass`, it \
   MUST have `from dataclasses import dataclass`. If it uses `np`, it MUST have \
   `import numpy as np`. If it uses `torch`, it MUST have `import torch`. \
   The imports cell (cell #3) should be comprehensive, but every subsequent code cell \
   must ALSO re-import anything it references. This prevents NameError when cells are \
   run out of order or after a kernel restart.
10. **Educational Depth**: This is a graduate-level tutorial, not just code. Explain \
    the intuition, the math, the engineering choices, and the tradeoffs.

OUTPUT FORMAT — valid JSON:
{
  "cells": [
    {"cell_type": "markdown", "source": "# Title\\n\\nDescription..."},
    {"cell_type": "code", "source": "import numpy as np\\n..."},
    ...
  ]
}

NOTEBOOK STRUCTURE (follow this order):
1. Title + paper citation + notebook overview
2. Environment setup (pip installs)
3. Imports and configuration
4. **Background & Motivation** — markdown explaining the paper's contribution, \
   the problem it solves, and why it matters to the field
5. **Prerequisite Concepts** — brief refresher on concepts the reader needs \
   (e.g., "Before diving in, let's review self-attention...")
6. Data generation (realistic synthetic data with clear documentation of WHY \
   each distribution was chosen)
7. For EACH key algorithm:
   a. **Step-by-step algorithm walkthrough** (numbered list in markdown)
   b. **Mathematical formulation** (equations with explicit variable definitions)
   c. **Equation-to-code mapping** (markdown cell connecting each equation to code)
   d. **Implementation** (production Python with inline comments referencing equations)
   e. **Verification** — expected vs actual output comparison
   f. **Why this matters** — intuition and importance
   g. **Visualization** of intermediate results
8. Full pipeline / training loop (if applicable)
9. Experiments and results visualization
10. **Summary & Key Takeaways** — bullet points of what the reader learned, \
    the paper's key contributions, and potential extensions
11. Discussion: limitations of this implementation, comparison to paper results
12. References

Generate 30-50 cells for a thorough tutorial. Each code cell should be \
self-contained and well-commented. Markdown cells should be detailed and educational — \
this notebook should teach, not just demonstrate."""


def create_openai_client(api_key: str) -> AsyncOpenAI:
    """Create an AsyncOpenAI client with the given API key."""
    return AsyncOpenAI(api_key=api_key)


async def analyze_paper(
    client: AsyncOpenAI,
    paper_text: str,
) -> dict[str, Any]:
    """Phase 1: Analyze a research paper to identify key algorithms and methodology.

    Args:
        client: OpenAI async client
        paper_text: Full extracted text of the paper

    Returns:
        Structured analysis dict with title, algorithms, methodology, etc.
    """
    # Sanitize paper text to mitigate prompt injection (SEC-004)
    safe_text = sanitize_paper_text(paper_text)

    response = await asyncio.wait_for(
        client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": ANALYSIS_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": (
                        "Analyze this research paper and produce the structured JSON analysis.\n\n"
                        f"--- PAPER TEXT ---\n{safe_text}\n--- END PAPER ---"
                    ),
                },
            ],
            response_format={"type": "json_object"},
            temperature=0.2,
        ),
        timeout=LLM_TIMEOUT_SECONDS,
    )

    content = response.choices[0].message.content
    return json.loads(content)


async def generate_notebook_cells(
    client: AsyncOpenAI,
    analysis: dict[str, Any],
    paper_text: str,
) -> list[dict[str, str]]:
    """Phase 2: Generate notebook cells from the paper analysis.

    Args:
        client: OpenAI async client
        analysis: Structured analysis from Phase 1
        paper_text: Full paper text for reference

    Returns:
        List of cell dicts with cell_type and source keys
    """
    analysis_summary = json.dumps(analysis, indent=2)

    # Sanitize paper text for Phase 2 as well (SEC-004)
    safe_text = sanitize_paper_text(paper_text[:15000])

    response = await asyncio.wait_for(
        client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": GENERATION_SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": (
                        "Generate a complete Google Colab notebook implementing this paper.\n\n"
                        f"--- PAPER ANALYSIS ---\n{analysis_summary}\n--- END ANALYSIS ---\n\n"
                        f"--- FULL PAPER TEXT (for reference) ---\n{safe_text}\n--- END ---\n\n"
                        "Produce the notebook cells as JSON. Remember: research-grade quality, "
                        "realistic synthetic data, thorough implementations, and beautiful visualizations.\n\n"
                        "IMPORTANT: Every code cell MUST include its own imports. Do NOT rely on "
                        "imports from earlier cells. If a cell uses dataclass, typing, numpy, torch, "
                        "matplotlib, or ANY other module, it must import it at the top of that cell. "
                        "This prevents NameError when running cells after a kernel restart."
                    ),
                },
            ],
            response_format={"type": "json_object"},
            temperature=0.3,
        ),
        timeout=LLM_TIMEOUT_SECONDS,
    )

    content = response.choices[0].message.content
    parsed = json.loads(content)

    cells = parsed.get("cells", [])

    # Validate cell structure
    validated: list[dict[str, str]] = []
    for cell in cells:
        if isinstance(cell, dict) and "cell_type" in cell and "source" in cell:
            if cell["cell_type"] in ("markdown", "code"):
                validated.append({
                    "cell_type": cell["cell_type"],
                    "source": cell["source"],
                })

    return validated
