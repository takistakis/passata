#!/usr/bin/env python3

# Copyright 2017 Panagiotis Ktistakis <panktist@gmail.com>
#
# This file is part of passata.
#
# passata is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# passata is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with passata.  If not, see <http://www.gnu.org/licenses/>.

"""setuptools installer script for passata."""

from setuptools import setup

setup(
    name='passata',
    version='0.1.0',
    description='A simple password manager, inspired by pass.',
    long_description=open('README.md').read(),
    author='Panagiotis Ktistakis',
    author_email='panktist@gmail.com',
    url='https://github.com/forkbong/passata',
    license='GPLv3+',
    py_modules=['passata'],
    entry_points={'console_scripts': ['passata=passata:cli']},
    install_requires=['click', 'PyYAML', 'pyinotify'],
    python_requires='>=3.5',
    classifiers=[
        'Development Status :: 4 - Beta',
        'Environment :: Console',
        'License :: OSI Approved :: GNU General Public License v3 or later '
            '(GPLv3+)',
        'Operating System :: POSIX :: Linux',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.5',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: 3.9',
        'Topic :: Utilities',
    ],
    keywords='password',
    zip_safe=True,
)
