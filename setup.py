from setuptools import setup, find_packages
import pydle

setup(
    name=pydle.__name__,
    version=pydle.__version__,
    packages=[
        'pydle',
        'pydle.features',
        'pydle.utils'
    ],
    extras_require={
        'SASL': 'pure-sasl >=0.1.6'   # for pydle.features.sasl
    },
    entry_points={
        'console_scripts': [
            'irccat = pydle.utils.irccat:main',
            'pydle = pydle.utils.run:main',
            'ipydle = pydle.utils.console:main'
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
