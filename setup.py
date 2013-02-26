<<<<<<< HEAD
from setuptools import setup, find_packages

setup(
    name = "shaper",
    version = "2.0",
    author = "Adam Strauch",
    author_email = "cx@initd.cz",
    description = ("Script that makes shaping easier"),
    license = "BSD",
    keywords = "shaper,shaping",
    url = "https://github.com/creckx/shaper",
    long_description="Script that makes shaping easier",
    packages = find_packages(exclude=['ez_setup', 'examples', 'tests']),
=======
#!/usr/bin/python

import os
import re
from setuptools import setup, find_packages


def read(fname):
    return open(os.path.join(os.path.dirname(__file__), fname)).read()


def parse_requirements(file_name):
    requirements = []
    for line in open(file_name, 'r').read().split('\n'):
        if re.match(r'(\s*#)|(\s*$)', line):
            continue
        if re.match(r'\s*-e\s+', line):
            requirements.append(re.sub(r'\s*-e\s+.*#egg=(.*)$', r'\1', line))
        elif re.match(r'\s*-f\s+', line):
            pass
        else:
            requirements.append(line)

    return requirements


def parse_dependency_links(file_name):
    dependency_links = []
    for line in open(file_name, 'r').read().split('\n'):
        if re.match(r'\s*-[ef]\s+', line):
            dependency_links.append(re.sub(r'\s*-[ef]\s+', '', line))

    return dependency_links


setup(
    name = "shaper",
    version = "0.1",
    author = "Adam Strauch",
    author_email = "cx@initd.cz",
    description = ("Shaper control script"),
    license = "BSD",
    keywords = "shaper",
    url = "https://github.com/creckx/shaper",
    packages=find_packages(exclude=['ez_setup', 'examples', 'tests']),
    long_description="Tool to create a great shaper",
>>>>>>> 5020ef605ea12a7dfb41803e4e2d0c0d79b08612
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Topic :: Utilities",
        "License :: OSI Approved :: BSD License",
        ],
<<<<<<< HEAD
    entry_points="""
    [console_scripts]
    shaper = shaper.shaper_proto:main
    """
)
=======
    install_requires = parse_requirements('requirements.txt'),
    dependency_links = parse_dependency_links('requirements.txt'),
    entry_points="""
    [console_scripts]
    shaper = shaper.shaperctl:main
    shaper_bh = shaper.bh:main
    shaper_ipv6sync = shaper.ipv6_sync:main
    """
)
>>>>>>> 5020ef605ea12a7dfb41803e4e2d0c0d79b08612
