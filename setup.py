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
    packages=['forest'],
    long_description=(""),
    py_modules=['forest'],
    classifiers=[
        "Development Status :: 2 - Pre-Alpha",
        "Topic :: Utilities",
        "License :: OSI Approved :: GNU Lesser General Public License v3 (LGPLv3)",
        "Environment :: Console"
    ],
    install_requires=[
        "simplejson",
        "bson",
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
