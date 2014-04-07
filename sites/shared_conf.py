from datetime import datetime

import alabaster


# Alabaster theme + mini-extension
html_theme_path = [alabaster.get_path()]
extensions = ['alabaster']
# Paths relative to invoking conf.py - not this shared file
html_static_path = ['../_shared_static']
html_theme = 'alabaster'
html_theme_options = {
    'description': "Pythonic remote execution",
    'github_user': 'fabric',
    'github_repo': 'fabric',
    'gittip_user': 'bitprophet',
    'analytics_id': 'UA-18486793-1',
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
exclude_trees = ['_build']
source_suffix = '.rst'
default_role = 'obj'