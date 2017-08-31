#!/usr/bin/env python

from distutils.core import setup

setup(
        name='backstage',
        version='0.1.0',
        description='Intersenting new web framework',
        author='Chandrashekar Jayaraman',
        author_email='cs@alpanahub.com',
        url='',
        packages=['backstage', 'backstage/conf'],
        install_requires=[
                            'lxml==3.7.1',
                            'gunicorn==19.6.0',
        ],
        entry_points={
            'console_scripts': [
                'backstage_serve = backstage.serve:serve',
                ]
        },
     )
