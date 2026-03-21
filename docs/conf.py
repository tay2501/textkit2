"""Sphinx configuration for press documentation."""

# -- Project information -------------------------------------------------------
project = "press"
author = "press contributors"
copyright = "2026, press contributors"
release = "0.1.0"

# -- General configuration -----------------------------------------------------
extensions = [
    "myst_parser",           # Markdown support (MyST)
    "sphinx.ext.autodoc",    # Auto-generate API docs from docstrings
    "sphinx.ext.viewcode",   # Add "view source" links
    "sphinx.ext.napoleon",   # NumPy / Google style docstrings
    "sphinx_copybutton",     # Copy button on code blocks
]

# MyST options: enable useful extensions
myst_enable_extensions = [
    "colon_fence",    # ::: as an alternative to ```
    "deflist",        # Definition lists
    "tasklist",       # - [ ] / - [x] checkboxes
]

# File types
source_suffix = {
    ".rst": "restructuredtext",
    ".md": "markdown",
}

# -- HTML output ---------------------------------------------------------------
html_theme = "furo"
html_title = "press"
html_static_path = ["_static"]

# Furo theme options
html_theme_options = {
    "sidebar_hide_name": False,
    "navigation_with_keys": True,
}

# -- autodoc -------------------------------------------------------------------
autodoc_member_order = "bysource"
autodoc_typehints = "description"
add_module_names = False
