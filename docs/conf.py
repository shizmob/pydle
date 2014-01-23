#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sys, os

# Make autodoc work.
sys.path.insert(0, os.path.abspath('..'))
# Ìmport pydle.
import pydle

extensions = [
    'sphinx.ext.autodoc',
    'sphinx.ext.doctest',
    'sphinx.ext.intersphinx',
    'sphinx.ext.todo',
    'sphinx.ext.coverage',
    'sphinx.ext.ifconfig',
    'sphinx.ext.viewcode'
]

templates_path = ['_templates']
exclude_patterns = ['_build']
source_suffix = '.rst'
master_doc = 'index'

# General information about the project.
project = pydle.__name__
copyright = '2013, Shiz'
version = release = pydle.__release__

# The name of the Pygments (syntax highlighting) style to use.
pygments_style = 'sphinx'

# -- Options for HTML output ---------------------------------------------------

# The theme to use for HTML and HTML Help pages.  See the documentation for
# a list of builtin themes.
html_theme = 'default'
html_static_path = ['_static']
html_show_sphinx = False
htmlhelp_basename = 'pydledoc'

# -- Options for LaTeX output --------------------------------------------------

latex_documents = [
    ('index', 'pydle.tex', 'pydle Documentation', 'Shiz', 'manual'),
]

# -- Options for manual page output --------------------------------------------

man_pages = [
    ('index', 'pydle', 'pydle Documentation', ['Shiz'], 1)
]

# Hooks.

def skip(app, what, name, obj, skip, options):
    if skip:
        return True
    if name.startswith('_') and name != '__init__':
        return True
    if name.startswith('on_raw_'):
        return True
    if name.startswith('on_ctcp_'):
        return True
    if name.startswith('on_isupport_'):
        return True
    if name.startswith('on_capability_'):
        return True
    return False

def setup(app):
    app.connect('autodoc-skip-member', skip)
