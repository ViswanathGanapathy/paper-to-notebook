"""Unit tests for v2 Task 8: Richer notebook explanation prompts."""


def test_generation_prompt_requires_equation_mapping():
    """The generation prompt instructs equation-to-code mapping."""
    from app.llm_generator import GENERATION_SYSTEM_PROMPT

    prompt_lower = GENERATION_SYSTEM_PROMPT.lower()
    assert "equation" in prompt_lower
    assert "code" in prompt_lower
    # Should explicitly require mapping equations to code
    assert "map" in prompt_lower or "correspond" in prompt_lower or "connect" in prompt_lower


def test_generation_prompt_requires_step_by_step():
    """The generation prompt requires step-by-step algorithm breakdown."""
    from app.llm_generator import GENERATION_SYSTEM_PROMPT

    prompt_lower = GENERATION_SYSTEM_PROMPT.lower()
    assert "step-by-step" in prompt_lower or "step by step" in prompt_lower


def test_generation_prompt_requires_intuition():
    """The generation prompt requires 'why this matters' intuition sections."""
    from app.llm_generator import GENERATION_SYSTEM_PROMPT

    prompt_lower = GENERATION_SYSTEM_PROMPT.lower()
    assert "intuition" in prompt_lower or "why" in prompt_lower
    assert "matters" in prompt_lower or "important" in prompt_lower


def test_generation_prompt_requires_expected_vs_actual():
    """The generation prompt requires comparison of expected vs actual output."""
    from app.llm_generator import GENERATION_SYSTEM_PROMPT

    prompt_lower = GENERATION_SYSTEM_PROMPT.lower()
    assert "expected" in prompt_lower
    assert "actual" in prompt_lower or "output" in prompt_lower


def test_generation_prompt_requires_summary():
    """The generation prompt requires a summary/takeaway cell."""
    from app.llm_generator import GENERATION_SYSTEM_PROMPT

    prompt_lower = GENERATION_SYSTEM_PROMPT.lower()
    assert "summary" in prompt_lower or "takeaway" in prompt_lower or "key findings" in prompt_lower


def test_generation_prompt_targets_graduate_level():
    """The generation prompt targets graduate-level tutorial quality."""
    from app.llm_generator import GENERATION_SYSTEM_PROMPT

    prompt_lower = GENERATION_SYSTEM_PROMPT.lower()
    assert "graduate" in prompt_lower or "tutorial" in prompt_lower or "educational" in prompt_lower


def test_notebook_structure_includes_all_sections():
    """The notebook structure in the prompt includes the enhanced sections."""
    from app.llm_generator import GENERATION_SYSTEM_PROMPT

    prompt_lower = GENERATION_SYSTEM_PROMPT.lower()
    # Must include these enhanced sections
    assert "background" in prompt_lower
    assert "motivation" in prompt_lower
    assert "limitation" in prompt_lower
    assert "reference" in prompt_lower
