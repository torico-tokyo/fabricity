"""
pytest configuration for Fabric's test suite.

Puts the vendored third-party test dependencies on ``sys.path`` (see
``tests/_vendor/README.md`` for why ``fudge`` is vendored rather than
installed).
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '_vendor'))
