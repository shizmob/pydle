import os
import pytest


def pytest_addoption(parser):
    # Add option to skip meta (test suite-testing) tests.
    parser.addoption('--skip-meta', action='store_true', help='skip test suite-testing tests')
    # Add option to skip slow tests.
    parser.addoption('--skip-slow', action='store_true', help='skip slow tests')
    # Add option to skip real life tests.
    parser.addoption('--skip-real', action='store_true', help='skip real life tests')


def pytest_runtest_setup(item):
    if 'meta' in item.keywords and item.config.getoption('--skip-meta'):
        pytest.skip('skipping meta test (--skip-meta given)')
    if 'slow' in item.keywords and item.config.getoption('--skip-slow'):
        pytest.skip('skipping slow test (--skip-slow given)')

    if 'real' in item.keywords:
        if item.config.getoption('--skip-real'):
            pytest.skip('skipping real life test (--skip-real given)')
        if (not os.getenv('PYDLE_TESTS_REAL_HOST') or
            not os.getenv('PYDLE_TESTS_REAL_PORT')):
            pytest.skip('skipping real life test (no real server given)')
