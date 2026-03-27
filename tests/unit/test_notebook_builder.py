"""Unit tests for Task 5: Notebook assembly with nbformat."""
import json

import nbformat
import pytest


SAMPLE_CELLS = [
    {"cell_type": "markdown", "source": "# Test Paper\n\nImplementation notebook."},
    {"cell_type": "code", "source": "import numpy as np\nimport torch"},
    {"cell_type": "markdown", "source": "## Algorithm 1: Self-Attention"},
    {"cell_type": "code", "source": "def attention(Q, K, V):\n    return Q @ K.T @ V"},
    {"cell_type": "code", "source": "result = attention(np.eye(3), np.eye(3), np.eye(3))\nprint(result)"},
]

PAPER_META = {
    "title": "Attention Is All You Need",
    "authors": "Vaswani et al.",
}


@pytest.fixture
def notebook_bytes():
    from app.notebook_builder import build_notebook
    return build_notebook(SAMPLE_CELLS, PAPER_META)


def test_build_notebook_returns_bytes(notebook_bytes: bytes):
    """build_notebook returns bytes."""
    assert isinstance(notebook_bytes, bytes)
    assert len(notebook_bytes) > 0


def test_notebook_is_valid_nbformat(notebook_bytes: bytes):
    """Output is valid nbformat v4."""
    nb = nbformat.reads(notebook_bytes.decode("utf-8"), as_version=4)
    nbformat.validate(nb)


def test_notebook_has_python3_kernel(notebook_bytes: bytes):
    """Notebook specifies Python 3 kernel."""
    nb = nbformat.reads(notebook_bytes.decode("utf-8"), as_version=4)
    assert nb.metadata.kernelspec.name == "python3"
    assert "Python" in nb.metadata.kernelspec.display_name


def test_notebook_has_colab_metadata(notebook_bytes: bytes):
    """Notebook includes Colab-specific metadata."""
    nb = nbformat.reads(notebook_bytes.decode("utf-8"), as_version=4)
    assert "colab" in nb.metadata
    assert nb.metadata.colab.provenance is not None


def test_notebook_has_accelerator(notebook_bytes: bytes):
    """Notebook hints GPU accelerator for Colab."""
    nb = nbformat.reads(notebook_bytes.decode("utf-8"), as_version=4)
    assert "accelerator" in nb.metadata


def test_notebook_has_header_cell(notebook_bytes: bytes):
    """First cell is a markdown header with paper title and attribution."""
    nb = nbformat.reads(notebook_bytes.decode("utf-8"), as_version=4)
    first_cell = nb.cells[0]
    assert first_cell.cell_type == "markdown"
    assert "Attention Is All You Need" in first_cell.source
    assert "Paper-to-Notebook" in first_cell.source


def test_notebook_has_setup_cell(notebook_bytes: bytes):
    """Second cell is a code cell with pip installs."""
    nb = nbformat.reads(notebook_bytes.decode("utf-8"), as_version=4)
    # Find the first code cell
    code_cells = [c for c in nb.cells if c.cell_type == "code"]
    first_code = code_cells[0]
    assert "pip install" in first_code.source or "!pip" in first_code.source


def test_notebook_contains_all_llm_cells(notebook_bytes: bytes):
    """All LLM-generated cells are present in the notebook."""
    nb = nbformat.reads(notebook_bytes.decode("utf-8"), as_version=4)
    all_sources = [c.source for c in nb.cells]
    # Check that algorithm cell content is included
    assert any("attention" in s.lower() for s in all_sources)
    assert any("numpy" in s for s in all_sources)


def test_notebook_cell_count(notebook_bytes: bytes):
    """Notebook has header + setup + all LLM cells."""
    nb = nbformat.reads(notebook_bytes.decode("utf-8"), as_version=4)
    # header + setup + 5 LLM cells = at least 7
    assert len(nb.cells) >= 7


def test_empty_cells_skipped():
    """Empty or invalid cells from LLM are skipped."""
    from app.notebook_builder import build_notebook

    cells_with_empty = [
        {"cell_type": "markdown", "source": "# Valid"},
        {"cell_type": "code", "source": ""},  # empty
        {"cell_type": "code", "source": "x = 1"},
    ]
    nb_bytes = build_notebook(cells_with_empty, PAPER_META)
    nb = nbformat.reads(nb_bytes.decode("utf-8"), as_version=4)
    # Empty code cell should be skipped
    code_sources = [c.source for c in nb.cells if c.cell_type == "code"]
    assert "" not in code_sources
