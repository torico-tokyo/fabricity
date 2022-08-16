#!/usr/bin/env python

from __future__ import with_statement

from setuptools import setup, find_packages

from fabric.version import get_version


long_description = """
Fabric3 is a fork of `Fabric <http://fabfile.org>`_ to provide compatability
with Python 3.9+.

The goal is to stay 100% compatible with the original Fabric.  Any new releases
of Fabric will also be released here.  Please file issues for any differences
you find. Known differences are `documented on github
<https://github.com/torico-tokyo/fabricity>`.

To find out what's new in this version of Fabric, please see `the changelog
<http://fabfile.org/changelog.html>`_ of the original Fabric.

For more information, please see the Fabric website or execute ``fab --help``.
"""

install_requires=['paramiko>=2.0,<3.0', 'six>=1.10.0']


setup(
    name='fabricity',
    version=get_version('short'),
    description='[Fabric3 fork] Fabricity is a simple, Pythonic tool for remote execution and deployment.',
    long_description=long_description,
    author='Jeff Forcier',
    # author_email='',
    maintainer='torico',
    maintainer_email='developer+pypi@torico-tokyo.com',
    url='https://github.com/torico-tokyo/fabricity',
    packages=find_packages(),
    test_suite='nose.collector',
    tests_require=['nose<2.0', 'fudge<1.0', 'jinja2<3.0'],
    install_requires=install_requires,
    entry_points={
        'console_scripts': [
            'fab = fabric.main:main',
        ]
    },
    classifiers=[
          'Development Status :: 5 - Production/Stable',
          'Environment :: Console',
          'Intended Audience :: Developers',
          'Intended Audience :: System Administrators',
          'License :: OSI Approved :: BSD License',
          'Operating System :: MacOS :: MacOS X',
          'Operating System :: Unix',
          'Operating System :: POSIX',
          'Programming Language :: Python :: 3.9',
          'Programming Language :: Python :: 3.10',
          'Topic :: Software Development',
          'Topic :: Software Development :: Build Tools',
          'Topic :: Software Development :: Libraries',
          'Topic :: Software Development :: Libraries :: Python Modules',
          'Topic :: System :: Clustering',
          'Topic :: System :: Software Distribution',
          'Topic :: System :: Systems Administration',
    ],
)
