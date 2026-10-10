"""Core tests run without a Home Assistant instance."""

import pytest


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations() -> None:
    """Override the package-wide fixture: core tests do not need hass."""
