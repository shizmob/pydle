from setuptools import setup, find_packages
import pydle

setup(
    name=pydle.__name__,
    version=pydle.__version__,
    packages=[
        'pydle',
        'pydle.features',
        'pydle.features.rfc1459',
        'pydle.features.ircv3_1',
        'pydle.features.ircv3_2',
        'pydle.utils'
    ],
    requires=['tornado'],
    extras_require={
        'SASL': 'pure-sasl >=0.1.6',                       # for pydle.features.sasl
        'Generating documentation': 'sphinx_rtd_theme'     # the Sphinx theme we use
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
    license=pydle.__license__,

    zip_safe=True,
    test_suite='tests'
)
