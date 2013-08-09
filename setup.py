import distribute_setup
distribute_setup.use_setuptools()

from setuptools import setup,find_packages

setup(
    name = "experimentor_tools",
    version = "0.1",
    packages = find_packages(),

    install_requires = [
                "pyyaml",
                "lxml",
                "argparse"],

    entry_points = {
        'console_scripts': [
            "experimentor_tools = experimentor_tools:main",
            "allpairs = ValidatePathDistances:allpairs"
            ]
    },

    author = "Chris Wacek",
    author_email = "cwacek@cs.georgetown.edu",
    description = "Utilities for Experimentor",
    license = "LGPL"
)

