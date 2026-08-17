from os.path import join
from datetime import datetime

import alabaster


# Alabaster theme + mini-extension
html_theme_path = [alabaster.get_path()]
extensions = ['alabaster']
# Paths relative to invoking conf.py - not this shared file
html_static_path = [join('..', '_shared_static')]
html_theme = 'alabaster'
html_theme_options = {
    'logo': 'logo.png',
    'logo_name': True,
    'logo_text_align': 'center',
    'description': "Pythonic remote execution",
    'github_user': 'fabric',
    'github_repo': 'fabric',
    'travis_button': True,
    'analytics_id': 'UA-18486793-1',

    'link': '#3782BE',
    'link_hover': '#3782BE',
}
html_sidebars = {
    '**': [
        'about.html',
        'navigation.html',
        'searchbox.html',
        'donate.html',
    ]
}

# Regular settings
project = 'Fabric'
year = datetime.now().year
copyright = '%d Jeff Forcier' % year
master_doc = 'index'
templates_path = ['_templates']
# NOTE: was `exclude_trees`, which Sphinx removed in 1.0 in favour of
# `exclude_patterns`. It had been silently ignored ever since, so the build
# tree was never actually excluded.
exclude_patterns = ['_build']
# The dict form is what Sphinx uses internally; the bare string form is
# accepted but converted (and announced) on every build.
source_suffix = {'.rst': 'restructuredtext'}
default_role = 'obj'
