"""Root conftest — allow nested event loops for async test compatibility with Playwright."""
import nest_asyncio
import pytest

nest_asyncio.apply()


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    """Reset the rate limiter before each test to prevent cross-test interference."""
    from app.security import limiter
    limiter.reset()
    yield
