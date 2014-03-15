import pytest


def pytest_addoption(parser):
    # Add option to skip meta (test suite-testing) tests.
    parser.addoption('--skip-meta', action='store_true', help='skip test suite-testing tests')
    # Add option to skip slow tests.
    parser.addoption('--skip-slow', action='store_true', help='skip slow tests')

def pytest_runtest_setup(item):
    if 'meta' in item.keywords and item.config.getoption('--skip-meta'):
        pytest.skip('skipping meta test (--skip-meta given)')
    if 'slow' in item.keywords and item.config.getoption('--skip-slow'):
        pytest.skip('skipping slow test (--skip-slow given)')
