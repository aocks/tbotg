"""A setuptools based setup module for tbotg

See LICENSE at the top-level of this distribution for more information.
"""

import os
from os import path

from setuptools import setup, find_packages

from tbotg import VERSION


def get_readme():
    'Get the long description from the README file'

    here = path.abspath(path.dirname(__file__))
    rfile = path.join(here, 'README.rst')
    if not os.path.exists(rfile):
        raise ValueError(
            'Could not find %s; did you run `make README.rst`?' % rfile)
    with open(rfile) as my_fd:
        result = my_fd.read()

    return result


setup(
    name='tbotg',
    version=VERSION,
    description='Tools for Telegram generic bots.',
    long_description=get_readme(),
    url='http://github.com/aocks/tbotg',
    author='Emin Martinian',
    author_email='emin.martinian@gmail.com',
    include_package_data=True,
    license='GPL3',
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Intended Audience :: Developers',
        'Programming Language :: Python :: 3',
    ],


    keywords='telegram generic bots',
    # You can just specify the packages manually here if your project is
    # simple. Or you can use find_packages().
    packages=find_packages(exclude=['contrib', 'docs', 'tests']),
    #
    # See discussion at link below on install_requires vs requirements.txt
    # https://packaging.python.org/discussions/install-requires-vs-requirements/
    install_requires=['click', 'ox-secrets', 'requests',
                      'python-telegram-bot'],
    # If there are data files included in your packages that need to be
    # installed, specify them here.
    package_data={
        'sample': ['package_data.dat'],
    },
    # See https://click.palletsprojects.com/en/master/setuptools/
    # for how entry_points and scripts work.
    entry_points={
        'console_scripts': [
            'tcli = tbotg.scripts.tcli:main',
        ],
    },
)
