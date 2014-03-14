import pytest


# Add option to skip slow tests.

def pytest_addoption(parser):
    parser.addoption('--skip-slow', action='store_true', help='skip slow tests')

def pytest_runtest_setup(item):
    if 'slow' in item.keywords and item.config.getoption('--skip-slow'):
        pytest.skip('skipping slow test (--skip-slow given)')
