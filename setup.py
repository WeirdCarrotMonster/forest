# coding=utf-8
from setuptools import setup

setup(
    name="Forest",
    version="0.4",
    author="Eugene Protozanov",
    author_email="weirdcarrotmonster@gmail.com",
    description=(""),
    license="LGPLv3",
    keywords="PaaS",
    url="https://github.com/WeirdCarrotMonster/forest",
    packages=[
        'forest',
        'forest.components',
        'forest.components.air',
        'forest.components.api',
        'forest.components.druid',
        'forest.components.roots',
        'forest.components.branch',
        'forest.components.exceptions',
        'forest.utils'
    ],
    long_description=(""),
    classifiers=[
        "Development Status :: 2 - Pre-Alpha",
        "Environment :: Console",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: GNU Lesser General Public License v3 (LGPLv3)",
        "Natural Language :: Russian",
        "Operating System :: POSIX :: Linux",
        "Programming Language :: Python",
        "Topic :: System :: Systems Administration",
        "Topic :: Utilities"
    ],
    install_requires=[
        "simplejson",
        "tornado",
        "psutil",
        "pymongo",
        "motor",
        "PyMySQL",
        "pyzmq",
        "dateutils",
        "virtualenv",
        "toro"
    ],
    entry_points={
        'console_scripts': [
            'forest = forest:main',
        ],
    },
)
