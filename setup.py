#!/usr/bin/env python

from setuptools import setup, find_packages
import os

detailed_description = '''
Project to demonstrate unit testing in python within a docker container.
Creates a mocked endpoint and runs pytest tests against it.
'''

version = "1.0.0"

requirements = [
]

if __name__ == '__main__':
    setup(
        name='python_unit_testing_in_docker',
        version=version,
        description='Pytest Configuration Example',
        long_description=detailed_description,
        author="Ruairi Mangan",
        packages=find_packages(
            exclude=[
                'tests',
            ],
            include=[
                'api'
            ],
        ),
        install_requires=requirements,
        classifiers=[
          'Development Status :: 1 - Planning',
          'Framework :: Pytest',
          'Intended Audience :: Developers',
          'Intended Audience :: Education',
          'License :: OSI Approved :: MIT License',
          'Programming Language :: Python :: 3',
          'Programming Language :: Python :: 3.6',
          'Programming Language :: Python :: 3.7',
          'Topic :: Software Development',
          'Topic :: Software Development :: Libraries',
          'Topic :: Software Development :: Libraries :: Python Modules'
      ],
    )




