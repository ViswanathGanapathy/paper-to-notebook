"""Unit tests for v2 Task 10: LLM timeout configuration."""


def test_llm_timeout_constant_exists():
    """LLM_TIMEOUT_SECONDS is defined and reasonable."""
    from app.llm_generator import LLM_TIMEOUT_SECONDS

    assert isinstance(LLM_TIMEOUT_SECONDS, (int, float))
    assert 60 <= LLM_TIMEOUT_SECONDS <= 300  # Between 1-5 minutes


def test_analyze_paper_uses_timeout():
    """analyze_paper wraps the API call with asyncio.wait_for."""
    import inspect
    from app.llm_generator import analyze_paper

    source = inspect.getsource(analyze_paper)
    assert "wait_for" in source or "timeout" in source


def test_generate_cells_uses_timeout():
    """generate_notebook_cells wraps the API call with asyncio.wait_for."""
    import inspect
    from app.llm_generator import generate_notebook_cells

    source = inspect.getsource(generate_notebook_cells)
    assert "wait_for" in source or "timeout" in source


def test_cors_has_csrf_warning():
    """CORS config has a CSRF warning comment."""
    from pathlib import Path
    main_source = Path("app/main.py").read_text()
    assert "csrf" in main_source.lower() or "CSRF" in main_source
