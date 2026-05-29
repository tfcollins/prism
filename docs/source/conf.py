# Configuration file for the Sphinx documentation builder.
#
# Prism documentation — uses Analog Devices' ``adi-doctools`` "cosmic" theme
# (the same theme used by pyadi-iio) and is organised along the Diátaxis
# framework (Tutorials / How-to / Reference / Explanation).

project = "Prism"
copyright = "2026, The Prism authors"
author = "The Prism authors"
release = "0.4"
version = "0.4"

# -- General configuration ---------------------------------------------------

extensions = [
    "myst_parser",
    "sphinxcontrib.mermaid",
    "adi_doctools",
    # Emits .nojekyll so GitHub Pages serves Sphinx's _static/ (underscore) dirs.
    "sphinx.ext.githubpages",
]

# adi-doctools treats docs as part of a multi-repo system by default; Prism is
# a single, self-contained repository, so build in monolithic mode.
monolithic = True
repository = "prism"

source_suffix = {
    ".md": "markdown",
    ".rst": "restructuredtext",
}

myst_enable_extensions = [
    "colon_fence",  # ::: fenced admonitions
    "deflist",
    "fieldlist",
    "linkify",
    "substitution",
    "tasklist",
]
myst_heading_anchors = 3

templates_path = ["_templates"]
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

# -- HTML output -------------------------------------------------------------

html_theme = "cosmic"
html_static_path = ["_static"]
html_css_files = ["css/custom.css"]
html_favicon = "_static/favicon.png"
html_title = "Prism"

# Logos are resolved relative to _static/ by the cosmic theme.
html_theme_options = {
    "light_logo": "logos/prism-logo-light.png",
    "dark_logo": "logos/prism-logo-dark.png",
}

# -- Link checking -----------------------------------------------------------

linkcheck_ignore = [
    r"http://localhost:\d+",
    r"https?://prism\.internal",
    r"https://github\.com/yourorg/.*",
]
linkcheck_timeout = 15
