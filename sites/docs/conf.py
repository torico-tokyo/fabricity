# Obtain shared config values
import os, sys
from os.path import abspath, join, dirname
sys.path.append(abspath(join(dirname(__file__), '..')))
sys.path.append(abspath(join(dirname(__file__), '..', '..')))
from shared_conf import *

# Enable autodoc, intersphinx
extensions.extend(['sphinx.ext.autodoc', 'sphinx.ext.intersphinx'])

# NOTE: there used to be an `autodoc_default_flags` setting here. Sphinx
# removed it in 4.0 (superseded by `autodoc_default_options`), so it has been
# dead config for years. It is dropped rather than ported: every `automodule`
# under api/ already spells out the members it wants, and applying
# members/special-members globally would both dump `__dict__`/`__weakref__`
# into the API docs and make api/core/network duplicate `disconnect_all`
# (that page documents the single function on purpose).

# Default is 'local' building, but reference the public WWW site when building
# under RTD.
target = join(dirname(__file__), '..', 'www', '_build')
if os.environ.get('READTHEDOCS') == 'True':
    target = 'http://www.fabfile.org/'
# Intersphinx connection to stdlib + www site
intersphinx_mapping = {
    'python': ('https://docs.python.org/3/', None),
    'www': (target, None),
}

# Sister-site links to WWW
html_theme_options['extra_nav_links'] = {
    "Main website": 'http://www.fabfile.org',
}
