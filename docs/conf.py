#!/usr/bin/env python3
import sys
import os
import os.path as path
import datetime


### -- General options -- ###

# Make autodoc and import work.
if path.exists(path.join('..', 'pydle')):
    sys.path.insert(0, os.path.abspath('..'))
import pydle

# General information about the project.
project = pydle.__name__
copyright = '2013-{current}, Shiz'.format(current=datetime.date.today().year)
version = release = pydle.__version__

# Sphinx extensions to use.
extensions = [
    # Generate API description from code.
    'sphinx.ext.autodoc',
    # Generate unit tests from docstrings.
    'sphinx.ext.doctest',
    # Link to Sphinx documentation for related projects.
    'sphinx.ext.intersphinx',
    # Generate TODO descriptions from docstrings.
    'sphinx.ext.todo',
    # Conditional operator for documentation.
    'sphinx.ext.ifconfig',
    # Include full source code with documentation.
    'sphinx.ext.viewcode'
]

# Documentation links for projects we link to.
intersphinx_mapping = {
    'python': ('http://docs.python.org/3', None)
}


### -- Build locations -- ###

templates_path = ['_templates']
exclude_patterns = ['_build']
source_suffix = '.rst'
master_doc = 'index'


### -- General build settings -- ###

pygments_style = 'trac'


### -- HTML output -- ##

# Only set RTD theme if we're building locally.
if os.environ.get('READTHEDOCS', None) != 'True':
    import sphinx_rtd_theme
    html_theme = "sphinx_rtd_theme"
    html_theme_path = [ sphinx_rtd_theme.get_html_theme_path() ]
html_show_sphinx = False
htmlhelp_basename = 'pydledoc'


### -- LaTeX output -- ##

latex_documents = [
    ('index', 'pydle.tex', 'pydle Documentation', 'Shiz', 'manual'),
]


### -- Manpage output -- ###

man_pages = [
    ('index', 'pydle', 'pydle Documentation', ['Shiz'], 1)
]


### -- Sphinx customization code -- ##

def skip(app, what, name, obj, skip, options):
    if skip:
        return True
    if name.startswith('_') and name != '__init__':
        return True
    if name.startswith('on_data'):
        return True
    if name.startswith('on_raw_'):
        return True
    if name.startswith('on_ctcp') and name not in ('on_ctcp', 'on_ctcp_reply'):
        return True
    if name.startswith('on_isupport_'):
        return True
    if name.startswith('on_capability_'):
        return True
    return False

def setup(app):
    app.connect('autodoc-skip-member', skip)
