"""Fixtures for the Claude Mailbox tests."""

import pytest


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Allow Home Assistant to load the integration under test."""
    return
