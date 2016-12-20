from setuptools import setup

setup(
    name='pydle',
    version='0.8.3',
    packages=[
        'pydle',
        'pydle.features',
        'pydle.features.rfc1459',
        'pydle.features.ircv3',
        'pydle.utils'
    ],
    install_requires=['tornado'],
    extras_require={
        'sasl': 'pure-sasl >=0.1.6',   # for pydle.features.sasl
        'docs': 'sphinx_rtd_theme',    # the Sphinx theme we use
        'tests': 'pytest',             # collect and run tests
        'coverage': 'pytest-cov'       # get test case coverage
    },
    entry_points={
        'console_scripts': [
            'pydle = pydle.utils.run:main',
            'ipydle = pydle.utils.console:main',
            'pydle-irccat = pydle.utils.irccat:main'
        ]
    },

    author='Shiz',
    author_email='hi@shiz.me',
    url='https://github.com/Shizmob/pydle',
    keywords='irc library python3 compact flexible',
    description='A compact, flexible and standards-abiding IRC library for Python 3.',
    license='BSD',

    zip_safe=True,
    test_suite='tests'
)
