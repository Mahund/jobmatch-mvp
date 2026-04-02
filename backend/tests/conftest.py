import pytest


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "integration: marks tests that make real network/external calls (skip with -m 'not integration')",
    )
