#!/usr/bin/env python3

"""setuptools installer script for passata."""

from setuptools import setup

setup(
    name='passata',
    version='0.1.0',
    description='A simple password manager, inspired by pass.',
    author='Panagiotis Ktistakis',
    author_email='panktist@gmail.com',
    url='https://github.com/forkbong/passata',
    license='GPLv3+',
    py_modules=['passata'],
    entry_points={'console_scripts': ['passata=passata:cli']},
    install_requires=['click', 'PyYAML'],
)
