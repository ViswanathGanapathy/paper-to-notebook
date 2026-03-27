"""Unit tests for Task 4: OpenAI LLM integration for notebook generation."""
import asyncio
import json
from unittest.mock import AsyncMock, MagicMock

# ── Mock response helpers ────────────────────────────────

MOCK_ANALYSIS = {
    "title": "Attention Is All You Need",
    "summary": "Introduces the Transformer architecture based on self-attention.",
    "key_algorithms": [
        {
            "name": "Scaled Dot-Product Attention",
            "description": "Computes attention weights using queries, keys, and values.",
            "equations": ["Attention(Q,K,V) = softmax(QK^T / sqrt(d_k)) V"],
            "parameters": ["d_k", "d_v", "n_heads"],
        }
    ],
    "methodology": [
        "Multi-head attention mechanism",
        "Positional encoding",
        "Feed-forward networks with residual connections",
    ],
    "suggested_packages": ["numpy", "torch", "matplotlib"],
}

MOCK_CELLS = [
    {"cell_type": "markdown", "source": "# Attention Is All You Need\n\nImplementation tutorial."},
    {"cell_type": "code", "source": "import numpy as np\nimport torch"},
    {"cell_type": "markdown", "source": "## Scaled Dot-Product Attention"},
    {
        "cell_type": "code",
        "source": (
            "def scaled_dot_product_attention(Q: torch.Tensor, K: torch.Tensor, V: torch.Tensor) -> torch.Tensor:\n"
            "    d_k = Q.size(-1)\n"
            "    scores = torch.matmul(Q, K.transpose(-2, -1)) / (d_k ** 0.5)\n"
            "    weights = torch.softmax(scores, dim=-1)\n"
            "    return torch.matmul(weights, V)"
        ),
    },
    {"cell_type": "code", "source": "# Test with synthetic data\nQ = torch.randn(2, 8, 64)\nK = torch.randn(2, 8, 64)\nV = torch.randn(2, 8, 64)\nout = scaled_dot_product_attention(Q, K, V)\nprint(out.shape)"},
]


def _make_mock_response(content: dict) -> MagicMock:
    """Create a mock OpenAI chat completion response."""
    message = MagicMock()
    message.content = json.dumps(content)
    choice = MagicMock()
    choice.message = message
    resp = MagicMock()
    resp.choices = [choice]
    return resp


def _run(coro):
    """Run an async coroutine in a fresh event loop."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def test_analyze_paper_returns_structure():
    """analyze_paper returns a dict with expected keys."""
    from app.llm_generator import analyze_paper

    mock_client = MagicMock()
    mock_client.chat.completions.create = AsyncMock(
        return_value=_make_mock_response(MOCK_ANALYSIS)
    )

    result = _run(analyze_paper(mock_client, "Full text of the paper here..."))

    assert "title" in result
    assert "key_algorithms" in result
    assert "methodology" in result
    assert len(result["key_algorithms"]) >= 1
    mock_client.chat.completions.create.assert_called_once()


def test_generate_notebook_cells_returns_list():
    """generate_notebook_cells returns a list of cell dicts."""
    from app.llm_generator import generate_notebook_cells

    mock_client = MagicMock()
    mock_client.chat.completions.create = AsyncMock(
        return_value=_make_mock_response({"cells": MOCK_CELLS})
    )

    result = _run(generate_notebook_cells(mock_client, MOCK_ANALYSIS, "Full paper text..."))

    assert isinstance(result, list)
    assert len(result) >= 1
    for cell in result:
        assert "cell_type" in cell
        assert "source" in cell
        assert cell["cell_type"] in ("markdown", "code")


def test_generate_notebook_cells_has_code_and_markdown():
    """Generated cells include both markdown and code types."""
    from app.llm_generator import generate_notebook_cells

    mock_client = MagicMock()
    mock_client.chat.completions.create = AsyncMock(
        return_value=_make_mock_response({"cells": MOCK_CELLS})
    )

    result = _run(generate_notebook_cells(mock_client, MOCK_ANALYSIS, "Full paper text..."))

    types = {c["cell_type"] for c in result}
    assert "markdown" in types
    assert "code" in types


def test_analyze_paper_prompt_includes_paper_text():
    """The analysis prompt sends the paper text to the model."""
    from app.llm_generator import analyze_paper

    mock_client = MagicMock()
    mock_client.chat.completions.create = AsyncMock(
        return_value=_make_mock_response(MOCK_ANALYSIS)
    )

    paper_text = "This is the full paper text about transformers."
    _run(analyze_paper(mock_client, paper_text))

    call_args = mock_client.chat.completions.create.call_args
    messages = call_args.kwargs.get("messages") or call_args[1].get("messages")
    all_content = " ".join(m["content"] for m in messages)
    assert "transformers" in all_content.lower()


def test_analyze_paper_uses_correct_model():
    """The analysis call uses gpt-5.4."""
    from app.llm_generator import analyze_paper, MODEL_NAME

    mock_client = MagicMock()
    mock_client.chat.completions.create = AsyncMock(
        return_value=_make_mock_response(MOCK_ANALYSIS)
    )

    _run(analyze_paper(mock_client, "Paper text"))

    call_args = mock_client.chat.completions.create.call_args
    model = call_args.kwargs.get("model") or call_args[1].get("model")
    assert model == MODEL_NAME


def test_full_pipeline_create_client():
    """create_openai_client creates an AsyncOpenAI client."""
    from app.llm_generator import create_openai_client

    client = create_openai_client("sk-test-key")
    assert client is not None
    assert client.api_key == "sk-test-key"
