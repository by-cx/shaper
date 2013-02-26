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
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Topic :: Utilities",
        "License :: OSI Approved :: BSD License",
        ],
    entry_points="""
    [console_scripts]
    shaper = shaper.shaper_proto:main
    """
)
